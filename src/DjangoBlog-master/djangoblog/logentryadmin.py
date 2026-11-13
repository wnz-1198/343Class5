# ZZC: 本模块定制 Django 管理操作日志的展示、权限、查询优化和禁用删除行为。
from django.contrib import admin
from django.contrib.admin.models import DELETION
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse, NoReverseMatch
from django.utils.encoding import force_str
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _


# ZZC: LogEntryAdmin 将后台操作日志以只读方式展示，防止篡改审计记录。
class LogEntryAdmin(admin.ModelAdmin):
    list_filter = [
        'content_type'
    ]

    search_fields = [
        'object_repr',
        'change_message'
    ]

    list_display_links = [
        'action_time',
        'get_change_message',
    ]
    list_display = [
        'action_time',
        'user_link',
        'content_type',
        'object_link',
        'get_change_message',
    ]

    # ZZC: 审核日志属于审计数据，必须禁止手动新增。
    def has_add_permission(self, request):
        return False

    # ZZC: 允许有权限的用户查看日志，但通过 POST 修改时仍返回拒绝。
    def has_change_permission(self, request, obj=None):
        return (
                request.user.is_superuser or
                request.user.has_perm('admin.change_logentry')
        ) and request.method != 'POST'

    # ZZC: 禁止删除历史操作记录，确保审计链完整。
    def has_delete_permission(self, request, obj=None):
        return False

    # ZZC: 尽量把日志中的对象名称转换为对应后台详情页链接。
    def object_link(self, obj):
        object_link = escape(obj.object_repr)
        content_type = obj.content_type

    # ZZC: 只对非删除操作生成对象链接；删除后的对象通常已经没有详情页。
        if obj.action_flag != DELETION and content_type is not None:
            # try returning an actual link instead of object repr string
            try:
                url = reverse(
                    'admin:{}_{}_change'.format(content_type.app_label,
                                                content_type.model),
                    args=[obj.object_id]
                )
                object_link = '<a href="{}">{}</a>'.format(url, object_link)
            except NoReverseMatch:
                pass
        return mark_safe(object_link)

    object_link.admin_order_field = 'object_repr'
    object_link.short_description = _('object')

    # ZZC: 用户列展示用户名，并尝试链接到对应用户的后台详情页。
    def user_link(self, obj):
        content_type = ContentType.objects.get_for_model(type(obj.user))
        user_link = escape(force_str(obj.user))
        try:
            # try returning an actual link instead of object repr string
            url = reverse(
                'admin:{}_{}_change'.format(content_type.app_label,
                                            content_type.model),
                args=[obj.user.pk]
            )
            user_link = '<a href="{}">{}</a>'.format(url, user_link)
        except NoReverseMatch:
            pass
        return mark_safe(user_link)

    user_link.admin_order_field = 'user'
    user_link.short_description = _('user')

    # ZZC: 预取 content_type，避免后台列表逐行查询内容类型产生 N+1 问题。
    def get_queryset(self, request):
        queryset = super(LogEntryAdmin, self).get_queryset(request)
        return queryset.prefetch_related('content_type')

    # ZZC: 移除批量删除操作，防止管理员误删审计日志。
    def get_actions(self, request):
        actions = super(LogEntryAdmin, self).get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
