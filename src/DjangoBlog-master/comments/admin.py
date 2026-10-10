# ============================================================
# comments/admin.py —— 评论后台管理配置
# ============================================================
# Comment        ：评论审核工作台（批量启用/禁用 = 评论审核流程）
# CommentReaction：Emoji 反应记录（只读审计为主）
# ============================================================
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

from .models import Comment, CommentReaction


def disable_commentstatus(modeladmin, request, queryset):
    """批量动作：禁用(下架)选中评论 —— 审核不通过"""
    queryset.update(is_enable=False)


def enable_commentstatus(modeladmin, request, queryset):
    """批量动作：启用(通过)选中评论 —— 审核通过，前台立即可见"""
    queryset.update(is_enable=True)


disable_commentstatus.short_description = _('Disable comments')
enable_commentstatus.short_description = _('Enable comments')


class CommentAdmin(admin.ModelAdmin):
    """
    评论审核后台：
    - list_display 中的 link_to_* 为自定义跳转列，链接到关联用户/文章的编辑页
    - raw_id_fields 避免用户与文章的外键下拉全量加载（数据量大时的性能保护）
    - actions 批量审核对应模型 is_enable 字段（评论审核闭环）
    """
    list_per_page = 20
    list_display = (
        'id',
        'body',
        'link_to_userinfo',
        'link_to_article',
        'is_enable',
        'creation_time')
    list_display_links = ('id', 'body', 'is_enable')
    list_filter = ('is_enable',)
    # 时间字段不在表单编辑（由 default=now 自动维护）
    exclude = ('creation_time', 'last_modify_time')
    # 批量审核动作：通过/驳回
    actions = [disable_commentstatus, enable_commentstatus]
    # 外键以原始 id 输入框渲染，避免下拉列表全量加载
    raw_id_fields = ('author', 'article')
    search_fields = ('body',)

    def link_to_userinfo(self, obj):
        """评论列表中跳转到作者用户编辑页（昵称优先于邮箱展示）"""
        info = (obj.author._meta.app_label, obj.author._meta.model_name)
        link = reverse('admin:%s_%s_change' % info, args=(obj.author.id,))
        return format_html(
            u'<a href="%s">%s</a>' %
            (link, obj.author.nickname if obj.author.nickname else obj.author.email))

    def link_to_article(self, obj):
        """评论列表中跳转到所属文章编辑页"""
        info = (obj.article._meta.app_label, obj.article._meta.model_name)
        link = reverse('admin:%s_%s_change' % info, args=(obj.article.id,))
        return format_html(
            u'<a href="%s">%s</a>' % (link, obj.article.title))

    link_to_userinfo.short_description = _('User')
    link_to_article.short_description = _('Article')


class CommentReactionAdmin(admin.ModelAdmin):
    """
    Emoji 反应后台：
    - date_hierarchy 按 created_at 提供按时间下钻导航
    - 支持按评论正文/用户名搜索、按 emoji 类型与时间过滤
    """
    list_display = ('id', 'reaction_type', 'link_to_comment', 'link_to_user', 'created_at')
    list_display_links = ('id', 'reaction_type')
    list_filter = ('reaction_type', 'created_at')
    raw_id_fields = ('comment', 'user')
    # 跨关联字段搜索：定位某条评论/某个用户的全部反应
    search_fields = ('comment__body', 'user__username')
    date_hierarchy = 'created_at'

    def link_to_comment(self, obj):
        """反应列表中跳转到所属评论编辑页"""
        info = (obj.comment._meta.app_label, obj.comment._meta.model_name)
        link = reverse('admin:%s_%s_change' % info, args=(obj.comment.id,))
        return format_html(
            u'<a href="%s">Comment #%s</a>' % (link, obj.comment.id))

    def link_to_user(self, obj):
        """反应列表中跳转到发起用户编辑页"""
        info = (obj.user._meta.app_label, obj.user._meta.model_name)
        link = reverse('admin:%s_%s_change' % info, args=(obj.user.id,))
        return format_html(
            u'<a href="%s">%s</a>' %
            (link, obj.user.nickname if obj.user.nickname else obj.user.username))

    link_to_comment.short_description = _('Comment')
    link_to_user.short_description = _('User')


admin.site.register(Comment, CommentAdmin)
admin.site.register(CommentReaction, CommentReactionAdmin)
