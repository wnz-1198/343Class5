from django.conf import settings
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _

from blog.models import Article


# Create your models here.

class Comment(models.Model):
    """
    ============================================================
    Comment —— 评论模型 (树形评论 / 楼中楼回复的核心实体)
    ============================================================

    【设计方式】：直接继承 models.Model (不继承 blog.BaseModel)
        字段命名与 BaseModel 保持一致 (creation_time / last_modify_time)，
        但未抽取公共基类 —— 评论不参与 slug 体系，无需 get_full_url。

    【树形结构】：通过 parent_comment 自关联实现"无限层级回复"
        parent_comment = None  → 顶级评论 (挂在文章下, 参与顶级分页)
        parent_comment = 某评论 → 子回复 (楼中楼, 由模板标签递归渲染)
        渲染入口: templatetags/comments_tags.py 的 parse_commenttree
        删除策略: on_delete=CASCADE，父评论删除时所有子孙评论级联删除

    【审核机制】：is_enable 控制前台可见性
        - 默认 False：新评论默认不展示 (需管理员后台审核)
        - 例外：BlogSettings.comment_need_review=False 时，
          CommentPostView.form_valid 中会直接置为 True (免审核即时显示)
        - 后台批量审核: comments/admin.py 的 enable/disable_commentstatus

    【关联关系】：
        ├── N:1 → BlogUser (author)   评论作者, CASCADE
        ├── N:1 → Article (article)   所属文章, CASCADE
        ├── N:1 → Comment (self)      父评论 (自关联, 可空), CASCADE
        └── 1:N → CommentReaction     Emoji 反应列表 (related_name=reactions)

    【缓存联动】：见 djangoblog/blog_signals.py
        评论启用后清理文章详情页缓存 + article_comments_{id} 缓存，
        并异步发送评论通知邮件 (comments/utils.send_comment_email)
    """
    # 评论正文：最长 300 字符；支持 Markdown 渲染 (模板过滤器 comment_markdown)
    body = models.TextField('正文', max_length=300)
    # 创建时间：评论提交时刻，用于前台展示与排序
    creation_time = models.DateTimeField(_('creation time'), default=now)
    # 最近修改时间：后台编辑审核状态时刷新
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)
    # 评论作者：关联自定义用户模型 (accounts.BlogUser)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('author'),
        on_delete=models.CASCADE)
    # 所属文章：一篇文章下有多条评论
    article = models.ForeignKey(
        Article,
        verbose_name=_('article'),
        on_delete=models.CASCADE)
    # 父评论：自关联外键；为空表示顶级评论，非空表示对某条评论的回复
    parent_comment = models.ForeignKey(
        'self',
        verbose_name=_('parent comment'),
        blank=True,
        null=True,
        on_delete=models.CASCADE)
    # 是否启用(通过审核)：只有 True 的评论才会在前台展示与参与反应
    is_enable = models.BooleanField(_('enable'),
                                    default=False, blank=False, null=False)

    class Meta:
        # 默认按 id 倒序：新评论在前 (后台列表 / 顶级评论查询)
        ordering = ['-id']
        verbose_name = _('comment')
        verbose_name_plural = verbose_name
        # 后台"最新评论"取数依据
        get_latest_by = 'id'
        indexes = [
            # 优化评论列表查询：article + parent_comment + is_enable组合索引
            # 覆盖场景：文章详情页"取顶级评论 + 过滤启用状态"
            models.Index(fields=['article', 'parent_comment', 'is_enable'], name='idx_art_parent_enable'),
            # 优化侧边栏评论查询：is_enable + id组合索引
            # 覆盖场景：全站最新评论侧栏按启用状态倒序取数
            models.Index(fields=['is_enable', '-id'], name='idx_enable_id'),
        ]

    def __str__(self):
        return self.body

    def get_reactions_summary(self, user=None):
        """
        获取评论的 reactions 统计信息
        返回格式: {
            '👍': {
                'count': 5,
                'has_reacted': True,
                'users': ['Alice', 'Bob', 'Charlie']
            },
            '❤️': {'count': 3, 'has_reacted': False, 'users': [...]},
            ...
        }

        调用方：
        - CommentReactionView.get  : GET  /comment/<id>/react 公开返回统计
        - CommentReactionView.post : POST /comment/<id>/react 切换后回传最新统计

        【查询结构】(共 1 + 2N 次查询, N=该评论出现过的 emoji 种类)：
        ① 一次 GROUP BY 聚合查询拿到每种 emoji 的计数
        ② 每种 emoji 再查一次最多 10 名点赞用户
        ③ 已登录用户对每种 emoji 再做一次 exists 判定
        单条评论最多 8 种 emoji (见 REACTION_CHOICES)，查询次数有上界。
        """
        from django.db.models import Count

        # ① 按反应类型分组聚合计数
        reactions = CommentReaction.objects.filter(
            comment=self
        ).values('reaction_type').annotate(count=Count('id'))

        result = {}
        for reaction in reactions:
            emoji = reaction['reaction_type']

            # 获取该 emoji 的所有点赞用户（② 每类一次查询，最多显示10个用户）
            reaction_users = CommentReaction.objects.filter(
                comment=self,
                reaction_type=emoji
            ).select_related('user')[:10]  # 最多显示10个用户

            # 昵称优先于用户名展示
            user_names = [r.user.nickname or r.user.username for r in reaction_users]

            result[emoji] = {
                'count': reaction['count'],
                'has_reacted': False,
                'users': user_names
            }

            # ③ 标记当前登录用户是否已点过该 emoji (用于前端高亮/切换态)
            if user and user.is_authenticated:
                result[emoji]['has_reacted'] = CommentReaction.objects.filter(
                    comment=self,
                    user=user,
                    reaction_type=emoji
                ).exists()

        return result


class CommentReaction(models.Model):
    """
    评论的 Emoji 反应/点赞
    """
    REACTION_CHOICES = [
        ('👍', 'thumbs_up'),
        ('👎', 'thumbs_down'),
        ('❤️', 'heart'),
        ('😄', 'laugh'),
        ('🎉', 'hooray'),
        ('😕', 'confused'),
        ('🚀', 'rocket'),
        ('👀', 'eyes'),
    ]

    # 所属评论：related_name='reactions'，可通过 comment.reactions 反查全部反应
    comment = models.ForeignKey(
        Comment,
        verbose_name=_('comment'),
        on_delete=models.CASCADE,
        related_name='reactions'
    )
    # 反应发起用户
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('user'),
        on_delete=models.CASCADE
    )
    # 反应类型：8 种 emoji 之一 (见上方 REACTION_CHOICES)
    reaction_type = models.CharField(
        _('reaction type'),
        max_length=10,
        choices=REACTION_CHOICES
    )
    # 反应时间：auto_now_add 仅在插入时写入，后续不更新
    created_at = models.DateTimeField(_('created at'), auto_now_add=True)

    class Meta:
        verbose_name = _('comment reaction')
        verbose_name_plural = _('comment reactions')
        # 每个用户对同一评论的同一种 emoji 只能点一次
        unique_together = ['comment', 'user', 'reaction_type']
        indexes = [
            models.Index(fields=['comment', 'reaction_type'], name='idx_comment_reaction'),
        ]

    def __str__(self):
        return f'{self.user.username} - {self.reaction_type} on comment {self.comment.id}'
