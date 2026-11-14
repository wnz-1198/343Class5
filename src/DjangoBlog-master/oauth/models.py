#SJL: OAuth 领域模型模块，保存第三方身份绑定和每种平台的授权配置。
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _


class OAuthUser(models.Model):
    #SJL: author 可空用于首次第三方登录尚未绑定本地用户；绑定后形成持久关联。
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('author'),
        blank=True,
        null=True,
        on_delete=models.CASCADE)
    openid = models.CharField(max_length=50)
    nickname = models.CharField(max_length=50, verbose_name=_('nick name'))
    token = models.CharField(max_length=150, null=True, blank=True)
    picture = models.CharField(max_length=350, blank=True, null=True)
    type = models.CharField(blank=False, null=False, max_length=50)
    email = models.CharField(max_length=50, null=True, blank=True)
    metadata = models.TextField(null=True, blank=True)
    creation_time = models.DateTimeField(_('creation time'), default=now)
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)

    def __str__(self):
        #SJL: 后台和日志显示昵称，避免直接展示 access token。
        return self.nickname

    class Meta:
        verbose_name = _('oauth user')
        verbose_name_plural = verbose_name
        ordering = ['-creation_time']


class OAuthConfig(models.Model):
    #SJL: 配置表只保存平台接入参数，真正的第三方令牌保存在 OAuthUser。
    TYPE = (
        ('weibo', _('weibo')),
        ('google', _('google')),
        ('github', 'GitHub'),
        ('facebook', 'FaceBook'),
        ('qq', 'QQ'),
    )
    type = models.CharField(_('type'), max_length=10, choices=TYPE, default='a')
    appkey = models.CharField(max_length=200, verbose_name='AppKey')
    appsecret = models.CharField(max_length=200, verbose_name='AppSecret')
    callback_url = models.CharField(
        max_length=200,
        verbose_name=_('callback url'),
        blank=False,
        default='')
    is_enable = models.BooleanField(
        _('is enable'), default=True, blank=False, null=False)
    creation_time = models.DateTimeField(_('creation time'), default=now)
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)

    def clean(self):
        #SJL: 同一平台只能存在一条配置，避免回调地址和 AppKey 加载不确定。
        if OAuthConfig.objects.filter(
                type=self.type).exclude(id=self.id).count():
            raise ValidationError(_(self.type + _('already exists')))

    def __str__(self):
        return self.type

    class Meta:
        verbose_name = 'oauth配置'
        verbose_name_plural = verbose_name
        ordering = ['-creation_time']
