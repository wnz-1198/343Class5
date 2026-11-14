# DjangoBlog blog 模块泛读报告

> **软件工程大作业 · 第 5–6 周实践任务（泛读报告）**
>
> **项目名称**：DjangoBlog 博客系统
>
> **负责模块**：blog（内容发布与浏览）
>
> **成员分支**：`XLT_branch`
>
> **日期**：2026-11-14

源码链接均指向仓库内的 `src/DjangoBlog-master/`，行号以本次读取的工作区为准。本报告沿用 [comments 模块报告](comments模块泛读报告.md) 的梳理方式，涉及模型或行为的结论以源码和迁移为依据。

---

## 1. 模块定位与职责

blog 是 DjangoBlog 的内容子系统。它提供文章、独立页面及其组织方式，为读者生成浏览界面，也为管理者提供内容和站点配置入口。

| 职责 | 当前实现 | 源码 |
|---|---|---|
| 内容管理 | 文章与独立页面共用 `Article`；后台可编辑 Markdown 正文、发布状态、评论开关、分类和标签 | [blog/models.py:97–166](../src/DjangoBlog-master/blog/models.py#L97-L166)、[blog/admin.py:22–100](../src/DjangoBlog-master/blog/admin.py#L22-L100) |
| 内容浏览 | 首页、分类、标签、作者列表复用列表基类；另有文章详情、归档与友情链接页 | [blog/urls.py:23–89](../src/DjangoBlog-master/blog/urls.py#L23-L89)、[blog/views.py:71–160](../src/DjangoBlog-master/blog/views.py#L71-L160) |
| 页面展示 | 提供站点 SEO、导航、摘要、侧栏与主题配置；搜索入口挂在项目根路由，视图由 blog 提供 | [blog/context_processors.py:11–53](../src/DjangoBlog-master/blog/context_processors.py#L11-L53)、[blog/templatetags/blog_tags.py:76–134](../src/DjangoBlog-master/blog/templatetags/blog_tags.py#L76-L134)、[djangoblog/urls.py:60–74](../src/DjangoBlog-master/djangoblog/urls.py#L60-L74) |
| 跨应用协作 | accounts 提供作者身份；blog 在详情页读取 comments 的评论数据和表单，评论提交由 comments 处理 | [djangoblog/settings.py:271](../src/DjangoBlog-master/djangoblog/settings.py#L271)、[blog/views.py:153–224](../src/DjangoBlog-master/blog/views.py#L153-L224)、[comments/views.py:56–86](../src/DjangoBlog-master/comments/views.py#L56-L86) |

---

## 2. 系统分层架构模型（MVT）

```text
浏览器
  → 根路由 djangoblog/urls.py（i18n_patterns）
    → blog/urls.py → 列表 / 详情 / 归档 / 友链视图
    → 根路由的 search → EsSearchView
  → View：查询、分页、SEO、评论上下文、插件钩子
    ↔ Model：Article / Category / Tag / Links / SideBar / BlogSettings
    → Template：share_layout/base.html + 页面模板 + 模板标签
  ← 服务端渲染的 HTML
```

- **Model**：模型定义内容、站点配置与关系，视图经 ORM 查询；列表查询预加载作者和分类外键以及标签多对多关系。[blog/models.py:97–195](../src/DjangoBlog-master/blog/models.py#L97-L195)、[djangoblog/mixins.py:118–152](../src/DjangoBlog-master/djangoblog/mixins.py#L118-L152)
- **View**：根路由在 `i18n_patterns` 中挂载 blog、comments 与 admin；默认语言不加前缀。文章列表采用 `ListView` 与缓存、页码混入类，详情采用 `DetailView`。[djangoblog/urls.py:60–74](../src/DjangoBlog-master/djangoblog/urls.py#L60-L74)、[blog/views.py:71–115](../src/DjangoBlog-master/blog/views.py#L71-L115)、[blog/views.py:153–165](../src/DjangoBlog-master/blog/views.py#L153-L165)
- **Template**：基础布局负责站点导航与页脚；内容模板使用 `blog_tags` 生成卡片、分页、正文和侧栏。全站上下文处理器从配置和内容模型提供站名、栏目、公开独立页面和评论开关。[templates/share_layout/base.html:173–190](../src/DjangoBlog-master/templates/share_layout/base.html#L173-L190)、[templates/blog/article_index.html:11–78](../src/DjangoBlog-master/templates/blog/article_index.html#L11-L78)、[blog/context_processors.py:11–53](../src/DjangoBlog-master/blog/context_processors.py#L11-L53)

应用间存在双向协作：`comments.Comment` 指向 `blog.Article`；详情视图又在构造上下文时局部导入 `Comment`。模型关系与视图调用应分开理解。[comments/models.py:49–65](../src/DjangoBlog-master/comments/models.py#L49-L65)、[blog/views.py:165–184](../src/DjangoBlog-master/blog/views.py#L165-L184)

---

## 3. 核心功能调用链

### 3.1 首页与内容聚合列表

```text
首页、分类、作者或标签路由
  → 对应列表子类生成查询缓存键与筛选条件
  → CachedListViewMixin：读取缓存，未命中才执行子类取数逻辑
  → ORM 预加载 author、category 与 tags
  → ListView 分页 → article_index.html 渲染卡片与翻页
```

| 入口 | 筛选与呈现 | 源码 |
|---|---|---|
| 首页 | `type='a', status='p'`；通过 `page/<int:page>/` 翻页 | [blog/urls.py:24–36](../src/DjangoBlog-master/blog/urls.py#L24-L36)、[blog/views.py:119–148](../src/DjangoBlog-master/blog/views.py#L119-L148) |
| 分类 | 按 slug 找分类，递归取得本分类及后代；筛选 `status='p'`，因此包含归入这些分类的已发布独立页面 | [blog/views.py:279–307](../src/DjangoBlog-master/blog/views.py#L279-L307)、[blog/models.py:327–346](../src/DjangoBlog-master/blog/models.py#L327-L346)、[djangoblog/mixins.py:93–113](../src/DjangoBlog-master/djangoblog/mixins.py#L93-L113) |
| 作者、标签 | 作者按用户名精确匹配；标签按 slug 找对象，再按标签名筛选；两者都限定普通文章和已发布状态 | [blog/views.py:336–355](../src/DjangoBlog-master/blog/views.py#L336-L355)、[blog/views.py:374–400](../src/DjangoBlog-master/blog/views.py#L374-L400) |
| 归档 | 只筛选已发布状态，不限类型、不分页；模板按发布时间的年、月分组；路由另有一小时整页缓存 | [blog/views.py:419–439](../src/DjangoBlog-master/blog/views.py#L419-L439)、[blog/urls.py:76–84](../src/DjangoBlog-master/blog/urls.py#L76-L84)、[templates/blog/article_archives.html:29–65](../src/DjangoBlog-master/templates/blog/article_archives.html#L29-L65) |

列表缓存实现见 [djangoblog/mixins.py:199–230](../src/DjangoBlog-master/djangoblog/mixins.py#L199-L230)。通用列表按 `PAGINATE_BY=10` 分页，模型默认按置顶权重和发布时间依次降序。[blog/views.py:80–94](../src/DjangoBlog-master/blog/views.py#L80-L94)、[djangoblog/settings.py:283](../src/DjangoBlog-master/djangoblog/settings.py#L283)、[blog/models.py:176–195](../src/DjangoBlog-master/blog/models.py#L176-L195)

### 3.2 文章详情、评论与浏览量

1. `Article.get_absolute_url()` 用创建日期和文章 ID 反向生成详情路径；详情视图以 `article_id` 查对象，路径年月日不参与查找。[blog/models.py:197–205](../src/DjangoBlog-master/blog/models.py#L197-L205)、[blog/urls.py:37–43](../src/DjangoBlog-master/blog/urls.py#L37-L43)、[blog/views.py:153–165](../src/DjangoBlog-master/blog/views.py#L153-L165)
2. 详情视图查询当前文章已启用的顶级评论，按站点配置分页，并生成带 `?comment_page=N#commentlist-container` 的翻页链接；评论总数来自 `Article.comment_list()`，包含已启用回复。视图同时准备 SEO 与上一篇、下一篇上下文。[blog/views.py:165–255](../src/DjangoBlog-master/blog/views.py#L165-L255)、[blog/models.py:226–239](../src/DjangoBlog-master/blog/models.py#L226-L239)
3. 视图运行 `ARTICLE_DETAIL_LOAD` 与 `after_article_body_get` 钩子。启用的 `view_count` 插件监听后者，调用 `Article.viewed()`；`BaseModel.save()` 对仅写浏览数的调用执行单字段 `UPDATE`。[blog/views.py:264–275](../src/DjangoBlog-master/blog/views.py#L264-L275)、[djangoblog/settings.py:450–460](../src/DjangoBlog-master/djangoblog/settings.py#L450-L460)、[plugins/view_count/plugin.py:5–15](../src/DjangoBlog-master/plugins/view_count/plugin.py#L5-L15)、[blog/models.py:62–79](../src/DjangoBlog-master/blog/models.py#L62-L79)、[blog/models.py:220–224](../src/DjangoBlog-master/blog/models.py#L220-L224)
4. 模板把 Markdown 转成 HTML，再经内容插件过滤；打开目录选项时单独生成目录。评论区按文章和全站开关显示，登录后才展示评论表单；评论写入在 comments 应用完成。[blog/templatetags/blog_tags.py:76–134](../src/DjangoBlog-master/blog/templatetags/blog_tags.py#L76-L134)、[templates/blog/article_detail.html:67–85](../src/DjangoBlog-master/templates/blog/article_detail.html#L67-L85)、[templates/blog/article_detail.html:144–170](../src/DjangoBlog-master/templates/blog/article_detail.html#L144-L170)、[comments/views.py:56–86](../src/DjangoBlog-master/comments/views.py#L56-L86)

### 3.3 后台编辑、缓存与其他入口

- **后台编辑**：项目自定义管理站注册六个 blog 模型。普通文章保存后的 `post_save` 处理器尝试清理首页首屏、当前分类、标签与作者首屏、归档查询、侧栏和 SEO 等缓存键；`BlogSettings.save()` 另行调用 `cache.clear()`。[djangoblog/admin_site.py:41–46](../src/DjangoBlog-master/djangoblog/admin_site.py#L41-L46)、[djangoblog/blog_signals.py:118–169](../src/DjangoBlog-master/djangoblog/blog_signals.py#L118-L169)、[blog/models.py:544–552](../src/DjangoBlog-master/blog/models.py#L544-L552)
- **搜索**：导航 GET 表单提交到根路由 `search`，由 Haystack 的 `search_view_factory` 组合 `EsSearchView` 与 `ElasticSearchModelSearchForm`。视图请求开启高亮，结果模板把查询词交给文章卡片标签。[templates/share_layout/nav.html:114–125](../src/DjangoBlog-master/templates/share_layout/nav.html#L114-L125)、[djangoblog/urls.py:69–74](../src/DjangoBlog-master/djangoblog/urls.py#L69-L74)、[blog/views.py:457–489](../src/DjangoBlog-master/blog/views.py#L457-L489)、[templates/search/search.html:33–46](../src/DjangoBlog-master/templates/search/search.html#L33-L46)
- **友情链接与侧栏**：友情链接页查询所有启用记录并沿用 `sequence` 排序；侧栏的友情链接额外按传入位置和 `all` 筛选。侧栏还聚合最新文章、热门文章、最新评论、标签和自定义区块。[blog/views.py:442–449](../src/DjangoBlog-master/blog/views.py#L442-L449)、[blog/models.py:382–403](../src/DjangoBlog-master/blog/models.py#L382-L403)、[blog/templatetags/blog_tags.py:251–323](../src/DjangoBlog-master/blog/templatetags/blog_tags.py#L251-L323)

---

## 4. 数据模型摘要

| 模型或表 | 关键字段、约束与用途 | 源码 |
|---|---|---|
| Article | 标题唯一；正文为 `MDTextField`；`status` 为草稿/已发布，默认已发布；`type` 为普通文章/独立页面，默认普通文章；作者和分类必填，标签可不选 | [blog/models.py:97–195](../src/DjangoBlog-master/blog/models.py#L97-L195) |
| Category | 名称唯一；`parent_category` 可空，根分类无父级；保存时按名称生成 slug，按 `-index` 排序 | [blog/models.py:62–79](../src/DjangoBlog-master/blog/models.py#L62-L79)、[blog/models.py:274–302](../src/DjangoBlog-master/blog/models.py#L274-L302) |
| Tag | 名称唯一；保存时按名称生成 slug；标签计数查询按标签名关联文章并去重，未限定发布状态 | [blog/models.py:62–79](../src/DjangoBlog-master/blog/models.py#L62-L79)、[blog/models.py:349–373](../src/DjangoBlog-master/blog/models.py#L349-L373) |
| Article_Tag | `Article.tags` 自动生成的 `blog_article_tags`；图中只列 `article_id`、`tag_id` 两个关系字段 | [blog/models.py:164–166](../src/DjangoBlog-master/blog/models.py#L164-L166)、[blog/migrations/0001_initial.py:111–129](../src/DjangoBlog-master/blog/migrations/0001_initial.py#L111-L129) |
| Links | 名称和顺序分别唯一；URL、启用状态、位置枚举；修改时间字段名是 `last_mod_time` | [blog/models.py:42–49](../src/DjangoBlog-master/blog/models.py#L42-L49)、[blog/models.py:378–406](../src/DjangoBlog-master/blog/models.py#L378-L406) |
| SideBar | 标题、HTML 内容、启用状态和唯一顺序；修改时间字段名是 `last_mod_time` | [blog/models.py:411–430](../src/DjangoBlog-master/blog/models.py#L411-L430) |
| BlogSettings | 保存站名、SEO、展示条数、主题、评论、广告与备案等配置；单行限制由 `clean()` 校验；配置读取入口无记录时会写入一条默认配置 | [blog/models.py:439–552](../src/DjangoBlog-master/blog/models.py#L439-L552)、[djangoblog/utils.py:150–175](../src/DjangoBlog-master/djangoblog/utils.py#L150-L175) |

`BaseModel` 是抽象类，无独立表；Article、Category、Tag 继承显式 `AutoField` 及两个默认取当前时间的字段。Links、SideBar、BlogSettings 的主键由初始迁移声明为 `BigAutoField`。[blog/models.py:52–94](../src/DjangoBlog-master/blog/models.py#L52-L94)、[blog/migrations/0001_initial.py:19–78](../src/DjangoBlog-master/blog/migrations/0001_initial.py#L19-L78)

| 关系 | 基数与字段 | 源码 |
|---|---|---|
| BlogUser → Article | 每篇文章有一个作者；一个用户可有零到多篇文章，`author_id` | [blog/models.py:142–150](../src/DjangoBlog-master/blog/models.py#L142-L150)、[djangoblog/settings.py:271](../src/DjangoBlog-master/djangoblog/settings.py#L271)、[accounts/models.py:11–59](../src/DjangoBlog-master/accounts/models.py#L11-L59) |
| Category → Article | 每篇文章有一个分类；一个分类可有零到多篇文章，`category_id` | [blog/models.py:156–163](../src/DjangoBlog-master/blog/models.py#L156-L163) |
| Category → Category | 每个分类最多一个父分类，可有零到多个子分类，`parent_category_id` | [blog/models.py:278–286](../src/DjangoBlog-master/blog/models.py#L278-L286) |
| Article、Tag → Article_Tag | 一行关联记录对应一篇文章和一个标签；文章与标签各自可有零到多条关联记录 | [blog/models.py:164–166](../src/DjangoBlog-master/blog/models.py#L164-L166) |
| Article、BlogUser → Comment | 每条评论属于一篇文章和一个用户；文章或用户均可关联零到多条评论 | [comments/models.py:49–58](../src/DjangoBlog-master/comments/models.py#L49-L58) |
| Comment → Comment | 每条评论最多一个父评论，可有零到多条直接回复，`parent_comment_id` | [comments/models.py:59–65](../src/DjangoBlog-master/comments/models.py#L59-L65) |

上述显式外键均设置 `on_delete=models.CASCADE`。Links、SideBar、BlogSettings 与其他实体的联动发生在应用层，图中没有为它们添加外键。与旧 [系统 E-R 图](ER_Diagram.puml) 及 [数据模型设计说明书](数据模型设计说明书.md) 不同，[本模块 E-R 图](blog_ER_Diagram.puml) 只经关联表表达一次文章与标签的多对多关系；字段定义和迁移未声明以两个外键组成复合主键，图中不作该标注。

Article 声明四个组合索引：`idx_type_status_pub(type, status, -pub_time)`、`idx_status_views(status, -views)`、`idx_author_status_type(author, status, type)`、`idx_category_status(category, status)`。它们对应列表、热门、作者和分类的常用筛选字段；实际是否使用索引须看数据库执行计划。[blog/models.py:176–195](../src/DjangoBlog-master/blog/models.py#L176-L195)

---

## 5. 模块文件清单与代码标注

以下为本次泛读的主要入口及已有注释的索引；本轮仅生成报告与 E-R 图。

| 文件 | 阅读重点 |
|---|---|
| [blog/models.py:1–16](../src/DjangoBlog-master/blog/models.py#L1-L16)、[54–195](../src/DjangoBlog-master/blog/models.py#L54-L195) | 文件头列明模型和跨应用依赖；从字段、`Meta` 和迁移核对表结构 |
| [blog/urls.py:1–103](../src/DjangoBlog-master/blog/urls.py#L1-L103)、[blog/views.py:71–275](../src/DjangoBlog-master/blog/views.py#L71-L275) | 路由注释标记路径和访问条件；视图区分查询缓存、评论分页和详情钩子 |
| [blog/admin.py:22–122](../src/DjangoBlog-master/blog/admin.py#L22-L122)、[168–202](../src/DjangoBlog-master/blog/admin.py#L168-L202) | 表单、文章批量动作、配置管理；注册位置另见项目管理站 |
| [blog/templatetags/blog_tags.py:76–134](../src/DjangoBlog-master/blog/templatetags/blog_tags.py#L76-L134)、[251–323](../src/DjangoBlog-master/blog/templatetags/blog_tags.py#L251-L323)、[340–429](../src/DjangoBlog-master/blog/templatetags/blog_tags.py#L340-L429) | 正文与摘要、侧栏组装、翻页和卡片的模板标签 |
| [blog/context_processors.py:11–53](../src/DjangoBlog-master/blog/context_processors.py#L11-L53)、[blog/middleware.py:12–42](../src/DjangoBlog-master/blog/middleware.py#L12-L42) | 共享模板变量；记录非流式响应耗时，启用 Elasticsearch 时另写耗时文档 |
| [blog/apps.py:7–55](../src/DjangoBlog-master/blog/apps.py#L7-L55)、[blog/documents.py:174–252](../src/DjangoBlog-master/blog/documents.py#L174-L252) | 应用启动时检查搜索索引；文章 Elasticsearch 文档及索引维护 |
| [blog/test_views.py:11–110](../src/DjangoBlog-master/blog/test_views.py#L11-L110)、[blog/test_article_business_logic.py:13–133](../src/DjangoBlog-master/blog/test_article_business_logic.py#L13-L133) | 现有测试提供详情、列表、分页与文章状态场景；此处只记录测试入口 |

---

## 6. 泛读结论与已知问题

模块通过通用列表视图与模板标签复用取数和展示，通过外键、树形分类与自动关联表组织内容。阅读时应分别追踪前台筛选条件、后台写入方式和缓存刷新逻辑；同一状态字段在这些入口里的处理不完全一致。以下是源码可见的差异和待验证影响。

| 观察 | 依据与影响 |
|---|---|
| 详情没有显式发布状态过滤 | 列表排除草稿，但 `ArticleDetailView` 只声明模型与主键参数，未覆写查询来限制 `status='p'`。知道 ID 的请求可尝试直接访问草稿，建议后续做匿名访问回归。[blog/views.py:130–135](../src/DjangoBlog-master/blog/views.py#L130-L135)、[blog/views.py:153–165](../src/DjangoBlog-master/blog/views.py#L153-L165) |
| 前台评论开关与提交检查有差异 | 模板判断全站开关；提交视图只判断文章评论关闭或 `status='c'`，而模型发布状态只有 `d/p`。需要验证关闭全站评论或直接向草稿提交时的服务端行为。[templates/blog/article_detail.html:144–148](../src/DjangoBlog-master/templates/blog/article_detail.html#L144-L148)、[comments/views.py:56–74](../src/DjangoBlog-master/comments/views.py#L56-L74)、[blog/models.py:97–107](../src/DjangoBlog-master/blog/models.py#L97-L107) |
| 批量动作与分页缓存失效不完全对应 | 四个后台批量动作直接 `queryset.update()`，绕过模型保存信号；常规文章保存时也只显式删除列表的第一页键。非首页分页或已缓存列表可能暂时展示旧状态。[blog/admin.py:33–49](../src/DjangoBlog-master/blog/admin.py#L33-L49)、[blog/views.py:137–138](../src/DjangoBlog-master/blog/views.py#L137-L138)、[djangoblog/blog_signals.py:121–152](../src/DjangoBlog-master/djangoblog/blog_signals.py#L121-L152) |
| 分类递归会执行子查询 | `get_sub_categorys()` 在递归体内对 `Category.objects.all()` 的 QuerySet 继续 `filter()` 并迭代，已有注释称在内存筛选，与实现不符；应按实际 SQL 评估分类树变大后的成本。[blog/models.py:324–346](../src/DjangoBlog-master/blog/models.py#L324-L346) |
| 浏览量递增与上一篇语义 | 浏览量按对象当前值加一后回写，存在并发丢增量的可能；上一篇没有显式按 ID 降序，实际受置顶权重和发布时间影响。[blog/models.py:62–71](../src/DjangoBlog-master/blog/models.py#L62-L71)、[blog/models.py:176–178](../src/DjangoBlog-master/blog/models.py#L176-L178)、[blog/models.py:220–224](../src/DjangoBlog-master/blog/models.py#L220-L224)、[blog/models.py:246–260](../src/DjangoBlog-master/blog/models.py#L246-L260) |
| 运维路由与上传校验边界 | `/clean` 的路由和视图未检查身份或请求方法；`/upload` 使用查询串签名，按文件名片段识别图片。是否受部署层保护需另查，当前只记录应用代码行为。[blog/urls.py:90–102](../src/DjangoBlog-master/blog/urls.py#L90-L102)、[blog/views.py:492–547](../src/DjangoBlog-master/blog/views.py#L492-L547)、[blog/views.py:567–571](../src/DjangoBlog-master/blog/views.py#L567-L571) |

---

## 7. 界面设计

以下为现有模板的界面梳理。首页和详情页在宽屏使用主内容加 300px 侧栏；窄屏侧栏移到主内容之后并可折叠。公共布局保留站点导航与页脚。[templates/blog/article_index.html:11–78](../src/DjangoBlog-master/templates/blog/article_index.html#L11-L78)、[templates/blog/article_detail.html:14–20](../src/DjangoBlog-master/templates/blog/article_detail.html#L14-L20)、[templates/blog/article_detail.html:174–195](../src/DjangoBlog-master/templates/blog/article_detail.html#L174-L195)、[templates/share_layout/base.html:173–190](../src/DjangoBlog-master/templates/share_layout/base.html#L173-L190)

| 界面 | 布局与主要操作 | 模板或管理定义 |
|---|---|---|
| 首页、分类、标签、作者 | 列表主区呈现文章卡片，包含标题链接、摘要和标签；聚合页按条件显示页头，分页位于卡片下方。顶部导航提供分类、归档、独立页面和搜索 | [templates/blog/article_index.html:16–56](../src/DjangoBlog-master/templates/blog/article_index.html#L16-L56)、[templates/blog/tags/article_info.html:9–66](../src/DjangoBlog-master/templates/blog/tags/article_info.html#L9-L66)、[templates/share_layout/nav.html:32–125](../src/DjangoBlog-master/templates/share_layout/nav.html#L32-L125) |
| 文章详情 | 主区为文章、可选目录、正文和相邻文章链接；允许评论时在正文后展示评论，未登录时提供登录入口 | [templates/blog/article_detail.html:20–85](../src/DjangoBlog-master/templates/blog/article_detail.html#L20-L85)、[templates/blog/article_detail.html:100–170](../src/DjangoBlog-master/templates/blog/article_detail.html#L100-L170) |
| 归档、友链与搜索 | 归档按年、月列文章链接；友链以响应式网格列出启用链接；搜索结果复用文章卡片并传入查询词 | [templates/blog/article_archives.html:29–78](../src/DjangoBlog-master/templates/blog/article_archives.html#L29-L78)、[templates/blog/links_list.html:19–49](../src/DjangoBlog-master/templates/blog/links_list.html#L19-L49)、[templates/search/search.html:23–57](../src/DjangoBlog-master/templates/search/search.html#L23-L57) |
| 后台文章管理 | 列表支持标题/正文搜索、按状态/类型/分类过滤和批量操作；编辑使用 Markdown 字段、标签选择器，作者和分类使用 ID 选择控件 | [blog/admin.py:61–114](../src/DjangoBlog-master/blog/admin.py#L61-L114)、[blog/models.py:119–122](../src/DjangoBlog-master/blog/models.py#L119-L122) |
