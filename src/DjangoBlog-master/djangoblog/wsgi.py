"""
WSGI config for djangoblog project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/1.10/howto/deployment/wsgi/
"""

# ZZC: 本模块创建 WSGI 应用对象，供 Gunicorn 等生产服务器调用。
import os

from django.core.wsgi import get_wsgi_application

# ZZC: 指定默认配置模块；调用方可通过该环境变量切换到其他部署配置。
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoblog.settings")

# ZZC: WSGI 服务器通过 application 这个模块级变量获取 Django 应用。
application = get_wsgi_application()
