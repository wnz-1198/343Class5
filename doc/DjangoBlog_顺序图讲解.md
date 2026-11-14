# 第 6 周顺序图补充与讲解

[顺序图 PlantUML 源文件](DjangoBlog_顺序图_首页详情发布.puml)包含三张图。首页和详情对应已有 `blog_sequence_diagrams.drawio` 的 UC-01、UC-02。发布文章对应 [发布文章用例说明](DjangoBlog_发布文章用例说明.md) 的 UC-BLOG-01。其余用例的覆盖情况见 [课程作业核对清单](DjangoBlog_课程作业核对与补做清单.md)。源码路径相对于 `src/DjangoBlog-master/`。

| 图 | 上台讲解要点 | 源码定位 |
|---|---|---|
| UC-01 首页 | 首页只查普通且已发布的文章。页码参与缓存键，命中就复用结果，未命中才取数。作者和分类使用 `select_related`，标签使用 `prefetch_related`。 | `blog/urls.py:24–36`、`blog/views.py:71–148`、`djangoblog/mixins.py:131–152,199–229` |
| UC-02 详情 | URL 带日期，但详情视图按 ID 查文章。这里预加载的是评论作者。分页只切分顶级评论，评论总数另取文章下已启用的评论。浏览量由插件通过钩子更新。 | `blog/views.py:153–224,264–275`、`blog/models.py:220–239`、`plugins/view_count/plugin.py:5–15`、`templates/blog/article_detail.html:144–148` |
| UC-BLOG-01 发布 | 单篇发布走表单校验和模型保存，触发保存信号。批量发布直接更新状态，保留原发布时间，也绕过保存信号。这能解释后台已显示发布、首页缓存却暂时未更新的情况。 | `djangoblog/admin_site.py:25–26,39–46`、`blog/admin.py:22–34,94–119`、`djangoblog/blog_signals.py:118–152` |

演示时可以先在首页翻页，再打开详情说明评论分页。最后进入后台选一篇草稿发布，对比单篇编辑发布和列表批量发布。实际页面、状态码和缓存效果以现场环境为准。
