# Create your views here.
from django.core.exceptions import ValidationError
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from accounts.models import BlogUser
from blog.models import Article
from djangoblog.base_views import AuthenticatedFormView
from .forms import CommentForm
from .models import Comment, CommentReaction


class CommentPostView(AuthenticatedFormView):
    """
    ============================================================
    CommentPostView —— 评论(回复)提交视图
    ============================================================
    路由: POST /article/<article_id>/postcomment  (comments/urls.py)
    表单: comments/forms.py CommentForm (字段仅 body, 隐藏域 parent_comment_id)
    模板: blog/article_detail.html (表单校验失败时回显文章详情页)

    使用 AuthenticatedFormView 基类，自动提供：
    - 登录验证（未登录用户会被重定向到登录页）
    - CSRF 保护（dispatch 上的 method_decorator）

    提交链路：
    前端表单 post_comment.html
      → (登录校验 + CSRF) CommentForm 校验 body 非空
      → form_valid: 校验文章评论开关 → 组装 Comment → 绑定父评论
      → comment.save() → post_save 信号(djangoblog/blog_signals.py)
          ├─ 免审核(is_enable=True): 清缓存 + 异步发通知邮件
          └─ 需审核: 仅落库, 管理员后台 enable_commentstatus 后生效
      → 302 回跳到新评论锚点 #div-comment-<id>
    """
    form_class = CommentForm
    template_name = 'blog/article_detail.html'

    def get(self, request, *args, **kwargs):
        # GET 不展示发表表单，统一重定向回文章详情页评论区
        article_id = self.kwargs['article_id']
        article = get_object_or_404(Article, pk=article_id)
        url = article.get_absolute_url()
        return HttpResponseRedirect(url + "#comments")

    def form_invalid(self, form):
        # 表单校验失败(如正文为空)：带着错误信息重新渲染文章详情页
        article_id = self.kwargs['article_id']
        article = get_object_or_404(Article, pk=article_id)

        return self.render_to_response({
            'form': form,
            'article': article
        })

    def form_valid(self, form):
        """提交的数据验证合法后的逻辑"""
        user = self.request.user
        author = BlogUser.objects.get(pk=user.pk)
        article_id = self.kwargs['article_id']
        article = get_object_or_404(Article, pk=article_id)

        # 文章级开关：comment_status='c' 评论关闭；文章被下架(status='c')也禁止评论
        if article.comment_status == 'c' or article.status == 'c':
            raise ValidationError("该文章评论已关闭.")
        # commit=False：先不入库，补全外键后统一保存
        comment = form.save(False)
        comment.article = article
        from djangoblog.utils import get_blog_setting
        settings = get_blog_setting()
        # 站点配置"评论无需审核"时直接上架；否则默认 is_enable=False 等待后台审核
        if not settings.comment_need_review:
            comment.is_enable = True
        comment.author = author

        # 楼中楼回复：隐藏域携带被回复评论 id，挂上自关联父评论
        if form.cleaned_data['parent_comment_id']:
            parent_comment = Comment.objects.get(
                pk=form.cleaned_data['parent_comment_id'])
            comment.parent_comment = parent_comment

        comment.save(True)
        # PRG 模式：保存后重定向，避免刷新重复提交
        return HttpResponseRedirect(
            "%s#div-comment-%d" %
            (article.get_absolute_url(), comment.pk))


class CommentReactionView(View):
    """
    ============================================================
    CommentReactionView —— 评论 Emoji 反应 API (JSON 接口)
    ============================================================
    路由: comments/urls.py
      GET  /comment/<comment_id>/react - 获取 reactions 统计（公开，前端 SSR 降级用）
      POST /comment/<comment_id>/react - 切换 reaction（需要登录 + CSRF）

    前端配套：frontend/src/components/reactionPicker.js
      - 初始数据优先读 DOM data-reactions (服务端渲染)，失败再降级 GET 本接口
      - POST 以 FormData 携带 reaction_type 与 csrfmiddlewaretoken
      - 401 时弹窗引导登录

    安全约定：
      - GET 公开，但只返回 is_enable=True 的评论
      - POST 手工校验登录态 (继承原生 View, 无 login_required)
      - 合法性校验：reaction_type 必须在 REACTION_CHOICES 8 种 emoji 内
    """

    def get(self, request, comment_id):
        """获取评论的 reactions 数据（公开访问）"""
        # 不存在或未启用评论一律 404，避免泄漏未审核内容
        comment = get_object_or_404(Comment, id=comment_id, is_enable=True)

        # 传递用户信息，如果未登录则传递 None（has_reacted 全部为 False）
        user = request.user if request.user.is_authenticated else None
        reactions_data = comment.get_reactions_summary(user)

        return JsonResponse({
            'success': True,
            'reactions': reactions_data
        })

    def post(self, request, comment_id):
        # POST 需要登录验证（未登录返回 401，由前端弹出登录引导）
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'error': 'Authentication required'
            }, status=401)
        # 获取评论（只有已启用的评论才能点赞）
        comment = get_object_or_404(Comment, id=comment_id, is_enable=True)

        # 获取 reaction 类型
        reaction_type = request.POST.get('reaction_type')

        # 验证 reaction_type 是否合法（白名单校验，拒绝任意字符串入库）
        valid_reactions = [choice[0] for choice in CommentReaction.REACTION_CHOICES]
        if reaction_type not in valid_reactions:
            return JsonResponse({
                'error': 'Invalid reaction type'
            }, status=400)

        # 切换 reaction（toggle 语义：已存在则删除=取消，否则创建=点赞）
        # unique_together(comment, user, reaction_type) 保证 get_or_create 唯一
        reaction, created = CommentReaction.objects.get_or_create(
            comment=comment,
            user=request.user,
            reaction_type=reaction_type
        )

        if not created:
            # 已存在，删除它（取消点赞）
            reaction.delete()
            action = 'removed'
        else:
            action = 'added'

        # 返回该评论的所有 reactions 统计（含当前用户最新的 has_reacted 状态）
        reactions_data = comment.get_reactions_summary(request.user)

        return JsonResponse({
            'success': True,
            'action': action,
            'reactions': reactions_data
        })
