"""博客领域服务函数。"""

from urllib.parse import quote


def article_to_markdown(article):
    """把文章对象转换为可下载的 Markdown 文本。

    只读取文章字段，不修改数据库。标题、分类、作者、发布时间、标签和原始
    Markdown 正文按固定顺序输出，便于用户存档或再次导入其他 Markdown 工具。
    """
    #SJL: 标签按名称稳定排序，保证同一篇文章多次导出的内容一致。
    tag_names = sorted(tag.name for tag in article.tags.all())
    tags = ', '.join(tag_names) if tag_names else '无'
    author_name = article.author.nickname or article.author.username
    published_at = article.pub_time.strftime('%Y-%m-%d %H:%M:%S')

    metadata = [
        f'> 分类：{article.category.name}',
        f'> 作者：{author_name}',
        f'> 发布时间：{published_at}',
        f'> 标签：{tags}',
        f'> 原文：{article.get_full_url()}',
    ]
    return '\n'.join([
        f'# {article.title}',
        '',
        *metadata,
        '',
        '---',
        '',
        article.body,
        '',
    ])


def markdown_attachment_header(article):
    """生成兼容中文文件名的 Content-Disposition 响应头。"""
    #SJL: filename 提供 ASCII 回退，filename* 使用 UTF-8 百分号编码保留中文标题。
    encoded = quote(f'{article.title}.md', safe='')
    return (
        f'attachment; filename="article-{article.pk}.md"; '
        f"filename*=UTF-8''{encoded}"
    )
