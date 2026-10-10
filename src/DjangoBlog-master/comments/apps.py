# comments 应用配置：在 INSTALLED_APPS 中以 'comments' 注册
# 评论的缓存清理与通知邮件由 djangoblog.blog_signals 中的全局 post_save 接收者统一处理，
# 本应用自身不挂信号，故无需重写 AppConfig.ready()
from django.apps import AppConfig


class CommentsConfig(AppConfig):
    name = 'comments'
