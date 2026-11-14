# WNZ: accounts.apps —— accounts 应用配置，声明应用名称并交由 Django 注册。
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'
