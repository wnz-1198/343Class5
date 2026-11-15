"""Create demo content for the DjangoBlog presentation environment.

Run from the DjangoBlog-master directory:
    python scripts/seed_demo.py
"""

import os
import sys
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "djangoblog.settings")

import django

django.setup()

from django.conf import settings

# Skip external search-engine notifications while seeding.
settings.TESTING = True

from django.utils import timezone

from accounts.models import BlogUser
from blog.models import Article, BlogSettings, Category, Tag
from comments.models import Comment

DEMO_TITLES = [
    "DjangoBlog 系统优化实践：从浏览量并发到健康检查",
    "Markdown 导出功能的设计与权限控制",
    "评论模块的缓存一致性与邮件通知",
    "Python 项目质量治理：SonarQube 与自动化测试",
    "Django 缓存装饰器的常见陷阱",
]
DEMO_COMMENTS = [
    "这篇内容很实用，健康检查的设计值得借鉴。",
    "导出功能正好解决了备份问题，权限控制也很清晰。",
]

Article.objects.filter(title__in=DEMO_TITLES).delete()
Comment.objects.filter(body__in=DEMO_COMMENTS).delete()
BlogUser.objects.filter(username__in=["demo_admin", "demo_reader"]).delete()
Tag.objects.filter(name__in=["Django", "Python", "软件工程", "性能优化", "测试"]).delete()
Category.objects.filter(name__in=["技术实践", "项目复盘", "学习笔记"]).delete()

admin = BlogUser.objects.create_superuser(
    username="demo_admin", email="demo@example.com", password="demo123456"
)
reader = BlogUser.objects.create_user(
    username="demo_reader", email="reader@example.com", password="demo123456"
)

settings_obj, _ = BlogSettings.objects.get_or_create(
    id=1, defaults={"site_name": "DjangoBlog", "comment_need_review": False}
)
settings_obj.comment_need_review = False
settings_obj.save()

tech = Category.objects.create(name="技术实践")
review = Category.objects.create(name="项目复盘")
notes = Category.objects.create(name="学习笔记")
tags = {
    name: Tag.objects.create(name=name)
    for name in ["Django", "Python", "软件工程", "性能优化", "测试"]
}

now = timezone.now()
articles = [
    {
        "title": DEMO_TITLES[0],
        "category": tech,
        "body": """# 优化背景

在并发访问下，原来的浏览量更新采用“读取后加一再写回”，可能丢失计数。本次维护把它改为数据库原子自增。

```python
Article.objects.filter(pk=self.pk).update(views=F('views') + 1)
```

# 健康检查

新的 `/health/` 接口会执行数据库 `SELECT 1`，并写入、读取缓存探针。任一关键依赖异常时返回 503。

# 结论

不修改数据模型，也能显著提升统计准确性和运行状态可见性。
""",
        "days": 0,
        "views": 128,
        "tags": ["Django", "性能优化"],
    },
    {
        "title": DEMO_TITLES[1],
        "category": tech,
        "body": """# 用户需求

读者希望把文章原文下载到本地，用于离线阅读和备份。

# 权限规则

- 游客可以导出已发布文章
- 草稿只有作者本人或超级管理员可以导出
- 中文标题通过 RFC 5987 编码保留

# 实现

导出视图在查询阶段就过滤可见文章，草稿对匿名用户返回 404，不暴露文章是否存在。
""",
        "days": 1,
        "views": 96,
        "tags": ["Django", "测试"],
    },
    {
        "title": DEMO_TITLES[2],
        "category": review,
        "body": """# 问题

评论审核通过后，文章详情页和侧边栏仍可能显示旧数据。

# 处理

评论保存信号统一清理文章详情、评论列表和侧边栏缓存，随后在后台线程发送通知邮件。

# 测试环境

测试模式使用共享内存 SQLite，后台线程会与测试连接争用数据库锁，因此测试中不启动邮件线程。
""",
        "days": 2,
        "views": 75,
        "tags": ["Django", "软件工程"],
    },
    {
        "title": DEMO_TITLES[3],
        "category": review,
        "body": """# 质量基线

先记录 SonarQube 修改前的问题数，再逐项判断是否修复，避免为了指标破坏业务语义。

# 本次修复

- 裸 `except` 改为明确异常类型
- 验证码改用 `secrets.choice`
- 百度通知增加 5 秒超时
- Whoosh 正则改用原始字符串

# 验证

完整测试套件 316 项通过，11 项功能冒烟检查全部通过。
""",
        "days": 3,
        "views": 64,
        "tags": ["Python", "软件工程", "测试"],
    },
    {
        "title": DEMO_TITLES[4],
        "category": notes,
        "body": """# 空列表不是未命中

缓存值为空列表时，应当直接返回空结果，而不是回源查询。

# 异常范围

不要用裸 `except` 吞掉所有异常，应只捕获可预期的类型，真实错误交给日志记录。
""",
        "days": 4,
        "views": 41,
        "tags": ["Django", "Python"],
    },
]

created = []
for item in articles:
    article = Article.objects.create(
        title=item["title"],
        body=item["body"],
        author=admin,
        category=item["category"],
        type="a",
        status="p",
        views=item["views"],
    )
    article.creation_time = now - timedelta(days=item["days"])
    article.save(update_fields=["creation_time"])
    article.tags.set([tags[name] for name in item["tags"]])
    created.append(article)

for body in DEMO_COMMENTS:
    Comment.objects.create(
        body=body, author=reader, article=created[0], is_enable=True
    )

print("Demo articles:", Article.objects.filter(status="p").count())
print("Demo comments:", Comment.objects.filter(is_enable=True).count())
print("Admin: demo_admin / demo123456")
print("Reader: demo_reader / demo123456")
