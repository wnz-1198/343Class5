#SJL: OAuth 应用配置，声明 App 名称并交由 Django 注册。
from django.apps import AppConfig


class OauthConfig(AppConfig):
    name = 'oauth'
