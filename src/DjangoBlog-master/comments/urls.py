# ============================================================
# comments 应用路由表
# 挂载方式：djangoblog/urls.py 中 include('comments.urls')
# 反向解析统一带命名空间前缀 'comments:'（模板中 {% url 'comments:postcomment' ... %}）
# ============================================================
from django.urls import path

from . import views

app_name = "comments"
urlpatterns = [
    # 发表评论/楼中楼回复（需登录）
    # 模板表单 action：{% url 'comments:postcomment' article.pk %}
    path(
        'article/<int:article_id>/postcomment',
        views.CommentPostView.as_view(),
        name='postcomment'),
    # 评论 Emoji 反应：GET 查询统计 / POST 切换点赞（见 views.CommentReactionView）
    path(
        'comment/<int:comment_id>/react',
        views.CommentReactionView.as_view(),
        name='comment_react'),
]
