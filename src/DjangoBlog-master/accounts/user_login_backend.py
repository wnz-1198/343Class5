# WNZ: accounts.user_login_backend —— 自定义认证后端：支持用户名或邮箱双模式登录，
# WNZ: 由 settings.AUTHENTICATION_BACKENDS 注册到 Django 认证链。
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class EmailOrUsernameModelBackend(ModelBackend):
    """
    允许使用用户名或邮箱登录
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        # WNZ: 防御 username/password 为 None（Django 对空凭据也会调认证链），直接拒绝。
        if not username or not password:
            return None
        if '@' in username:
            kwargs = {'email': username}
        else:
            kwargs = {'username': username}
        try:
            user = get_user_model().objects.get(**kwargs)
            if user.check_password(password):
                return user
        except get_user_model().DoesNotExist:
            return None

    def get_user(self, username):
        try:
            return get_user_model().objects.get(pk=username)
        except get_user_model().DoesNotExist:
            return None
