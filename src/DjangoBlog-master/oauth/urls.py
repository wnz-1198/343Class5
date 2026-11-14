#SJL: OAuth 路由模块，覆盖授权跳转、邮箱补充、邮件确认和绑定成功页。
from django.urls import path

from . import views

app_name = "oauth"
urlpatterns = [
    #SJL: 命名空间 oauth 用于模板和视图反向解析，避免与其他 App 路由冲突。
    path(
        r'oauth/authorize',
        views.authorize),
    path(
        r'oauth/requireemail/<int:oauthid>.html',
        views.RequireEmailView.as_view(),
        name='require_email'),
    path(
        r'oauth/emailconfirm/<int:id>/<sign>.html',
        views.emailconfirm,
        name='email_confirm'),
    path(
        r'oauth/bindsuccess/<int:oauthid>.html',
        views.bindsuccess,
        name='bindsuccess'),
    path(
        r'oauth/oauthlogin',
        views.oauthlogin,
        name='oauthlogin')]
