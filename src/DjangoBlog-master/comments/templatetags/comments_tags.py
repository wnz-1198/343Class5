# ============================================================
# comments_tags —— 评论模板标签库
# 加载方式：模板中 {% load comments_tags %}
# ============================================================
from django import template

register = template.Library()


@register.simple_tag
def parse_commenttree(commentlist, comment):
    """
    获得当前评论的全部子孙评论（楼中楼递归拍平）

    用法: {% parse_commenttree article_comments comment as childcomments %}
    原理: 对传入的"某篇文章全部启用评论"集合按 parent_comment 做深度优先递归，
          将该评论的所有层级后代按渲染顺序收集为一维列表。
    注意: commentlist 需为已预取(select_related/prefetch_related)的 QuerySet，
          此处 .filter() 在预取缓存上执行，避免递归中的 N+1 查询。
    """
    datas = []

    def parse(c):
        childs = commentlist.filter(parent_comment=c, is_enable=True)
        for child in childs:
            datas.append(child)
            parse(child)

    parse(comment)
    return datas


@register.inclusion_tag('comments/tags/comment_item.html')
def show_comment_item(comment, ischild):
    """
    单条评论渲染（inclusion_tag）
    - ischild=True  → depth=1 一级缩进
    - ischild=False → depth=2 多级缩进
    实际递归主模板为 comment_item_tree.html（内部 include 本标签对应模板）
    """
    depth = 1 if ischild else 2
    return {
        'comment_item': comment,
        'depth': depth
    }
