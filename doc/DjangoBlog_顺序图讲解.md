# 第 6 周顺序图补充与讲解

这里汇总成员 B 负责的 Blog 核心用例。[首页、详情、发布源图](DjangoBlog_顺序图_首页详情发布.puml) · [归档、分类标签与作者源图](DjangoBlog_顺序图_归档分类标签作者.puml) · [发布文章用例说明](DjangoBlog_发布文章用例说明.md)。源码路径相对于 `src/DjangoBlog-master/`。

查看图片：[首页](DjangoBlog_顺序图_首页详情发布.png) · [详情](DjangoBlog_顺序图_首页详情发布_001.png) · [发布文章](DjangoBlog_顺序图_首页详情发布_002.png)。仓库的 Draw.io 文件保留早期演进记录，答辩使用此页链接的更新版。

| 图 | 上台讲解要点 | 源码定位 |
|---|---|---|
| UC-01 首页 | 首页只查普通且已发布的文章。页码参与缓存键，命中就复用结果，未命中才取数。作者和分类使用 `select_related`，标签使用 `prefetch_related`。 | `blog/urls.py:24–36`、`blog/views.py:71–148`、`djangoblog/mixins.py:131–152,199–229` |
| UC-02 详情 | URL 带日期，视图按 ID 查询已发布文章，草稿返回 404。评论分页只切分顶级评论，浏览量由插件钩子更新。 | `blog/views.py:154–224`、`blog/models.py:220–239`、`plugins/view_count/plugin.py` |
| [归档](blog_sequence_archives.png) | 先判断整页缓存，再判断归档结果缓存。模板按年月分组，整页不分页。 | `blog/urls.py:76–84`、`blog/views.py:424–444`、`templates/blog/article_archives.html:29–65` |
| [分类与标签](blog_sequence_category_tag.png) | 分类包含子孙分类。标签通过多对多关系只筛选已发布普通文章。不存在的 slug 返回 404。 | `blog/views.py:284–321,379–419`、`djangoblog/mixins.py:70–109` |
| [作者列表](blog_sequence_author.png) | 按用户名精确筛选已发布普通文章。无匹配文章时显示空列表。 | `blog/views.py:341–375` |
| UC-BLOG-01 发布 | 单篇发布走表单校验和模型保存，触发保存信号。批量发布直接更新状态，保留原发布时间，也绕过保存信号。这能解释后台已显示发布、首页缓存却暂时未更新的情况。 | `djangoblog/admin_site.py:25–26,39–46`、`blog/admin.py:22–34,94–119`、`djangoblog/blog_signals.py:118–152` |

演示时可以先在首页翻页，再打开详情说明评论分页。最后进入后台选一篇草稿发布，对比单篇编辑发布和列表批量发布。实际页面、状态码和缓存效果以现场环境为准。
