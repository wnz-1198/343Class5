#SJL: OAuth 后台管理模块，用于查看绑定用户和配置各平台接入参数。
import logging

from django.contrib import admin
# Register your models here.
from django.urls import reverse
from django.utils.html import format_html

logger = logging.getLogger(__name__)


class OAuthUserAdmin(admin.ModelAdmin):
    #SJL: OAuth 绑定记录只读，避免管理员误改 openid 或 token 造成账户错绑。
    search_fields = ('nickname', 'email')
    list_per_page = 20
    list_display = (
        'id',
        'nickname',
        'link_to_usermodel',
        'show_user_image',
        'type',
        'email',
    )
    list_display_links = ('id', 'nickname')
    list_filter = ('author', 'type',)
    readonly_fields = []

    def get_readonly_fields(self, request, obj=None):
        return list(self.readonly_fields) + \
               [field.name for field in obj._meta.fields] + \
               [field.name for field in obj._meta.many_to_many]

    def has_add_permission(self, request):
        return False

    def link_to_usermodel(self, obj):
        if obj.author:
            info = (obj.author._meta.app_label, obj.author._meta.model_name)
            link = reverse('admin:%s_%s_change' % info, args=(obj.author.id,))
            return format_html(
                u'<a href="%s">%s</a>' %
                (link, obj.author.nickname if obj.author.nickname else obj.author.email))

    def show_user_image(self, obj):
        img = obj.picture
        return format_html(
            u'<img src="%s" style="width:50px;height:50px"></img>' %
            (img))

    link_to_usermodel.short_description = '用户'
    show_user_image.short_description = '用户头像'


class OAuthConfigAdmin(admin.ModelAdmin):
    #SJL: AppKey/AppSecret 由管理员在后台维护，普通用户不可访问。
    list_display = ('type', 'appkey', 'appsecret', 'is_enable')
    list_filter = ('type',)
