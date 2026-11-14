# WNZ: accounts.urls —— 账号模块路由：登录/注册/登出/验证结果/找回密码/发验证码，
# WNZ: 命名空间 app_name="accounts"，模板中以 'accounts:xxx' 反向解析。
from django.urls import path
from django.urls import re_path

from . import views
from .forms import LoginForm

app_name = "accounts"

urlpatterns = [re_path(r'^login/$',
                       views.LoginView.as_view(success_url='/'),
                       name='login',
                       kwargs={'authentication_form': LoginForm}),
               re_path(r'^register/$',
                       views.RegisterView.as_view(success_url="/"),
                       name='register'),
               re_path(r'^logout/$',
                       views.LogoutView.as_view(),
                       name='logout'),
               path(r'account/result.html',
                    views.account_result,
                    name='result'),
               re_path(r'^forget_password/$',
                       views.ForgetPasswordView.as_view(),
                       name='forget_password'),
               re_path(r'^forget_password_code/$',
                       views.ForgetPasswordEmailCode.as_view(),
                       name='forget_password_code'),
               ]
