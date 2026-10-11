# blog 应用的 URL 路由表
# ---------------------------------------------------------------------------
# 本文件把前台 URL 映射到 blog/views.py 中的视图，共 13 条路由。
# app_name = "blog" 定义了命名空间，因此模板/视图里反向解析必须写 'blog:xxx'
# （例如 {% url 'blog:index' %}、reverse('blog:detailbyid', ...)）。
#
# 路由形式：多数路径以 .html 结尾，文章详情还带有 year/month/day 层级段。
# 本注释只描述这一形式本身，不推断其设计动机。
# 本模块的 URL 由项目根路由 djangoblog/urls.py 引入——
# 已核对 djangoblog/urls.py 第 62 行，用的是 re_path 而非 path：
#     re_path(r'', include('blog.urls', namespace='blog'))
# 该 include 位于 i18n_patterns 内，因此支持多语言前缀。
#
# 注意：末尾的 upload 与 clean 两条接口访问控制不同，请分别看各自注释。
# ---------------------------------------------------------------------------
from django.urls import path
# cache_page：对整条路由的响应做页面级缓存
from django.views.decorators.cache import cache_page

from . import views

# 命名空间：所有反向解析均以此为前缀
app_name = "blog"
urlpatterns = [
    # 首页：/  →  IndexView（ArticleListView 的子类）
    # 查询 type='a' 且 status='p' 的文章，带分页与视图缓存
    path(
        r'',
        views.IndexView.as_view(),
        name='index'),
    # 首页分页：/page/<页码>/  →  复用同一个 IndexView
    # 页码经 page_kwarg 传入，由 PageNumberMixin 读取为 self.page_number
    path(
        r'page/<int:page>/',
        views.IndexView.as_view(),
        name='index_page'),
    # 文章详情：/article/年/月/日/<文章id>.html
    # 路径中的 year/month/day 由 Article.get_absolute_url() 依据 creation_time 生成；
    # 视图实际只用 article_id 取对象（pk_url_kwarg），年月日不参与任何查询条件
    path(
        r'article/<int:year>/<int:month>/<int:day>/<int:article_id>.html',
        views.ArticleDetailView.as_view(),
        name='detailbyid'),
    # 分类页：/category/<分类slug>.html
    # slug 来自 Category.slug，视图用 SlugCachedMixin 按 slug 取对象并缓存
    path(
        r'category/<slug:category_name>.html',
        views.CategoryDetailView.as_view(),
        name='category_detail'),
    # 分类页分页：/category/<分类slug>/<页码>.html
    path(
        r'category/<slug:category_name>/<int:page>.html',
        views.CategoryDetailView.as_view(),
        name='category_detail_page'),
    # 作者页：/author/<用户名>.html
    # 作者名通过 author__username 精确匹配，不做 slug 转换
    path(
        r'author/<author_name>.html',
        views.AuthorDetailView.as_view(),
        name='author_detail'),
    # 作者页分页：/author/<用户名>/<页码>.html
    path(
        r'author/<author_name>/<int:page>.html',
        views.AuthorDetailView.as_view(),
        name='author_detail_page'),
    # 标签页：/tag/<标签slug>.html
    path(
        r'tag/<slug:tag_name>.html',
        views.TagDetailView.as_view(),
        name='tag_detail'),
    # 标签页分页：/tag/<标签slug>/<页码>.html
    path(
        r'tag/<slug:tag_name>/<int:page>.html',
        views.TagDetailView.as_view(),
        name='tag_detail_page'),
    # 文章归档：/archives.html
    # 本文件中唯一包裹了 cache_page 的路由：整页响应缓存 1 小时，
    # 缓存命中时不会执行该视图。
    path(
        'archives.html',
        cache_page(
            60 * 60)(
            views.ArchivesView.as_view()),
        name='archives'),
    # 友情链接：/links.html，只展示 is_enable=True 的记录
    path(
        'links.html',
        views.LinkListView.as_view(),
        name='links'),
    # 图床上传接口：/upload。视图带 @csrf_exempt（不受 CSRF 保护），仅接受 POST；
    # 请求须在查询串中提供 sign 参数，且其值须等于 sha256(sha256(SECRET_KEY))，
    # 缺失或不匹配一律返回 403。详见 views.fileupload。
    path(
        r'upload',
        views.fileupload,
        name='upload'),
    # 清缓存接口：/clean。与 upload 不同，视图没有任何鉴权、也没有方法限制，
    # 收到请求即执行 cache.clear() 并返回 'ok'。
    path(
        r'clean',
        views.clean_cache_view,
        name='clean'),
]
