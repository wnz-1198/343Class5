from django import forms
from django.forms import ModelForm

from .models import Comment


class CommentForm(ModelForm):
    """
    ============================================================
    CommentForm —— 评论提交表单
    ============================================================
    用于 CommentPostView，渲染于 templates/comments/tags/post_comment.html

    字段策略：
    - body             : 唯一暴露给用户填写的字段 (对应 Comment.body)
                         ModelForm 自动套用模型层 max_length=300 约束
    - parent_comment_id: 隐藏域，不直接暴露外键对象，
                         仅携带被回复评论的主键，由视图层 form_valid 中
                         自行查询并绑定 comment.parent_comment

    作者(author)/文章(article)/is_enable 等均由视图与站点配置补全，
    不允许前端表单直接写入，防止越权伪造。
    """
    # 楼中楼回复目标评论 id；普通顶级评论提交时为空
    parent_comment_id = forms.IntegerField(
        widget=forms.HiddenInput, required=False)

    class Meta:
        model = Comment
        # 白名单：表单只接收正文字段，其余字段一律由服务端控制
        fields = ['body']
