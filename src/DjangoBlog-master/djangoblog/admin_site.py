# ZZC: 本模块组装项目自定义后台站点，并集中注册各业务 App 的管理模型。
from django.contrib.admin import AdminSite
from django.contrib.admin.models import LogEntry
from django.contrib.sites.admin import SiteAdmin
from django.contrib.sites.models import Site

from accounts.admin import *
from blog.admin import *
from blog.models import *
from comments.admin import *
from comments.models import *
from djangoblog.logentryadmin import LogEntryAdmin
from oauth.admin import *
from oauth.models import *
from servermanager.admin import *
from servermanager.models import *


# ZZC: DjangoBlogAdminSite 只允许超级管理员进入自定义后台。
class DjangoBlogAdminSite(AdminSite):
    site_header = 'djangoblog administration'
    site_title = 'djangoblog site admin'

    # ZZC: 保留父类初始化流程，同时使用固定后台名称隔离默认 AdminSite。
    def __init__(self, name='admin'):
        super().__init__(name)

    # ZZC: 权限判断直接要求 is_superuser，避免普通员工账号访问核心后台。
    def has_permission(self, request):
        return request.user.is_superuser

    # def get_urls(self):
    #     urls = super().get_urls()
    #     from django.urls import path
    #     from blog.views import refresh_memcache
    #
    #     my_urls = [
    #         path('refresh/', self.admin_view(refresh_memcache), name="refresh"),
    #     ]
    #     return urls + my_urls


# ZZC: 创建全局后台实例后，由 urls.py 把该实例挂载到 /admin/。
admin_site = DjangoBlogAdminSite(name='admin')

# ZZC: 以下注册把文章、分类、标签、用户、评论、OAuth 和运维模型加入自定义后台。
admin_site.register(Article, ArticlelAdmin)
admin_site.register(Category, CategoryAdmin)
admin_site.register(Tag, TagAdmin)
admin_site.register(Links, LinksAdmin)
admin_site.register(SideBar, SideBarAdmin)
admin_site.register(BlogSettings, BlogSettingsAdmin)

admin_site.register(commands, CommandsAdmin)
admin_site.register(EmailSendLog, EmailSendLogAdmin)

admin_site.register(BlogUser, BlogUserAdmin)

admin_site.register(Comment, CommentAdmin)

admin_site.register(OAuthUser, OAuthUserAdmin)
admin_site.register(OAuthConfig, OAuthConfigAdmin)

admin_site.register(Site, SiteAdmin)

admin_site.register(LogEntry, LogEntryAdmin)
