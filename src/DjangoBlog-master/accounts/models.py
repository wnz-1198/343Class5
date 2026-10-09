from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
from djangoblog.utils import get_current_site


# Create your models here.

class BlogUser(AbstractUser):
    """
    ============================================================
    BlogUser —— 系统用户模型 (作者 / 管理员 / 评论者通用)
    ============================================================

    【设计方式】：继承 Django 内置 AbstractUser，扩展 4 个业务字段
        AbstractUser 已提供的字段 (来自 Django auth 模块)：
        ┌───────────────┬──────────────────────────────────────────┐
        │ password      │ PBKDF2 哈希加密后的密码                 │
        │ last_login    │ 最近登录时间                             │
        │ is_superuser  │ 超级管理员标志 (可登录 admin 所有权限)   │
        │ username      │ 登录用户名 (UNIQUE)                     │
        │ first_name    │ 名 (本项目未使用)                       │
        │ last_name     │ 姓 (本项目未使用)                       │
        │ email         │ 邮箱 (EmailOrUsernameModelBackend 支持  │
        │               │        邮箱登录)                        │
        │ is_staff      │ 是否允许登录 Django Admin 后台          │
        │ is_active     │ 账户是否被启用 (False=禁用=无法登录)    │
        │ date_joined   │ 注册时间 (Django 原生)                  │
        └───────────────┴──────────────────────────────────────────┘

    【扩展的 4 个业务字段】(见下方字段定义)：
        ① nickname          —— 前台展示昵称 (评论、作者页显示)
        ② creation_time     —— 账户创建时间 (与 BaseModel 对齐)
        ③ last_modify_time  —— 账户修改时间 (与 BaseModel 对齐)
        ④ source            —— 注册来源标记 (如 'weibo'/'qq'/'native')

    【关联关系】：
        ├── 1:N → Article           (用户发文章，CASCADE 删除)
        ├── 1:N → Comment           (用户发评论)
        ├── 1:N → CommentReaction   (用户点 Emoji 反应)
        └── 1:N → OAuthUser         (用户绑定第三方平台账户)

    【登录后端】：accounts.user_login_backend.EmailOrUsernameModelBackend
        支持 用户名 或 邮箱 双模式登录
    """
    # 昵称：评论区、作者卡片、文章署名展示名
    nickname = models.CharField(_('nick name'), max_length=100, blank=True)

    # 创建时间：与 blog.BaseModel 统一命名，区别于 date_joined (Django 原生注册时间)
    creation_time = models.DateTimeField(_('creation time'), default=now)

    # 最近修改时间：资料变更时刷新
    last_modify_time = models.DateTimeField(_('last modify time'), default=now)

    # 注册来源：区分是原生注册 / OAuth 首次登录绑定 / 后台创建
    #   例：'native' | 'weibo' | 'github' | 'qq' | 'admin_created'
    source = models.CharField(_('create source'), max_length=100, blank=True)

    def get_absolute_url(self):
        """
        作者主页 URL：/author/{username}/
        展示该作者的所有已发布文章分页列表
        """
        return reverse(
            'blog:author_detail', kwargs={
                'author_name': self.username})

    def __str__(self):
        """
        对象字符串表示：使用邮箱，方便后台 / 日志定位
        (不使用 username 是因为邮箱在 OAuth 场景下更具备可识别性)
        """
        return self.email

    def get_full_url(self):
        """
        完整站点 URL (含 https://域名)，用于：
        - 作者页 分享链接
        - 邮件通知 (新评论 / 审核通过) 中跳转作者主页
        """
        site = get_current_site().domain
        url = "https://{site}{path}".format(site=site,
                                            path=self.get_absolute_url())
        return url

    class Meta:
        # 默认倒序展示：新注册用户在前 (后台 / 用户列表页)
        ordering = ['-id']
        verbose_name = _('user')
        verbose_name_plural = verbose_name
        # 默认取最新 id 作为 "最后加入的用户"
        get_latest_by = 'id'
