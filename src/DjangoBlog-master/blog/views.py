# blog 应用的前台视图
# ---------------------------------------------------------------------------
# 组织方式：以类视图（CBV）为主线，其中列表类视图通过 Mixin 组合复用逻辑。
# 相关 Mixin 的定义都在 djangoblog/mixins.py：
#   OptimizedArticleQueryMixin —— 提供 get_optimized_article_queryset()，
#                                 预取 author / category 外键与 tags 多对多
#   CachedListViewMixin        —— 提供 queryset 级缓存，要求子类实现
#                                 get_queryset_data() 与 get_queryset_cache_key()
#   PageNumberMixin            —— 从 URL kwargs 或 GET 参数解析页码，暴露 self.page_number
#   SlugCachedMixin            —— 按 slug 取对象并在本次请求内复用，暴露 get_slug_object()
#
# 注意：本文件各视图的实际 Mixin 组合并不相同，不能一概而论——
#   ArticleListView（列表基类）继承 CachedListViewMixin + PageNumberMixin + ListView；
#   IndexView / AuthorDetailView / ArchivesView 在其之上多混入 OptimizedArticleQueryMixin；
#   CategoryDetailView / TagDetailView 再多继承 SlugCachedMixin；
#   ArticleDetailView（DetailView）、LinkListView（ListView）、EsSearchView（SearchView）
#   完全没有使用上述任何 Mixin。
#
# 视图清单（9 个 CBV + 2 个 FBV）：
#   ArticleListView    —— 列表类视图基类，其余列表页都继承它
#   IndexView          —— 首页（含分页）
#   ArticleDetailView  —— 文章详情（含评论分页与 SEO）
#   CategoryDetailView —— 分类归档
#   AuthorDetailView   —— 作者归档
#   TagDetailView      —— 标签归档
#   ArchivesView       —— 文章归档（不分页，模板内按年月分组）
#   LinkListView       —— 友情链接页
#   EsSearchView       —— 全文搜索（基于 haystack）
#   fileupload         —— 图床上传接口（FBV）
#   clean_cache_view   —— 清缓存接口（FBV）
# ---------------------------------------------------------------------------
import logging
import os
import uuid

from django.conf import settings
from django.core.paginator import Paginator
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import render
from django.templatetags.static import static
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.csrf import csrf_exempt
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from haystack.views import SearchView

from blog.models import Article, Category, LinkShowType, Links, Tag
# 注意：CommentForm 来自 comments 应用，而不是 blog/forms.py
# （后者只定义了 BlogSearchForm）
from comments.forms import CommentForm
# 插件钩子：允许插件在文章详情渲染前后插入上下文或内容
from djangoblog.plugin_manage import hooks
from djangoblog.plugin_manage.hook_constants import ARTICLE_CONTENT_HOOK_NAME
from djangoblog.utils import cache, get_blog_setting, get_sha256
# 视图层的关键复用点，具体职责见文件头说明
from djangoblog.mixins import (
    SlugCachedMixin,
    ArticleListMixin,
    OptimizedArticleQueryMixin,
    CachedListViewMixin,
    PageNumberMixin
)

logger = logging.getLogger(__name__)


# 列表类视图的基类：首页、分类、作者、标签、归档都继承它。
# 它把"缓存 + 分页"交给 Mixin，自身只约定模板与上下文变量名。
class ArticleListView(CachedListViewMixin, PageNumberMixin, ListView):
    """
    文章列表视图基类（重构版）

    使用 Mixin 简化代码，消除重复逻辑
    子类只需实现 get_queryset_data() 和 get_queryset_cache_key() 方法
    """
    # template_name属性用于指定使用哪个模板进行渲染
    # 注意：首页/分类页/标签页/作者页共用这一个模板，靠 page_type 变量在模板内分支
    template_name = 'blog/article_index.html'

    # context_object_name属性用于给上下文变量取名（在模板中使用该名字）
    # 对应模板里的 {% for article in article_list %}
    context_object_name = 'article_list'

    # 页面类型，分类目录或标签列表等
    # 子类会覆写它（如 '分类目录归档'），模板据此决定页面标题与面包屑
    page_type = ''
    # 每页条数，取自项目配置 settings.PAGINATE_BY
    paginate_by = settings.PAGINATE_BY
    # 分页参数的 URL 关键字，即 ?page=N
    page_kwarg = 'page'
    # 友情链接展示位类型，默认"列表页"；首页会覆写为 LinkShowType.I
    link_type = LinkShowType.L

    # 【待核实】本方法定义于此，但在本文件中未被覆写、也未被调用。
    # 核对情况：
    #   - djangoblog/mixins.py 中 CachedListViewMixin 实际调用的是
    #     get_queryset_cache_key()（见其 get_queryset()），不是本方法；
    #   - 全仓库检索 get_view_cache_key 只命中此处这一行定义，没有任何调用点。
    # 但这只能说明"静态检索不到调用方"，无法排除运行期动态调用
    # （如外部插件、模板或 getattr），因此这里不下"绝不会被执行"的结论。
    #
    # 另需注意方法体写的是 self.request.get['pages']：这里的 get 是**小写属性名**，
    # 而 Django 的 HttpRequest 只提供大写的 .GET（以及 .POST 等），并没有小写的 .get，
    # 所以该表达式在运行时会先抛出 AttributeError（WSGIRequest 无 get 属性），
    # 而不是取到分页参数——即便被调用也无法正常返回。
    # 以上均属既有问题，本次仅在注释中记录，不修改业务代码。
    def get_view_cache_key(self):
        return self.request.get['pages']

    # 把 linktype 放进上下文，供模板中的侧边栏/友情链接组件判断展示位置
    def get_context_data(self, **kwargs):
        kwargs['linktype'] = self.link_type
        return super(ArticleListView, self).get_context_data(**kwargs)


# 首页。对应 URL name='index'（/）与 name='index_page'（/page/<n>/），两者共用本视图。
class IndexView(OptimizedArticleQueryMixin, ArticleListView):
    """
    首页视图（重构版）

    继承 OptimizedArticleQueryMixin 获得优化的查询方法
    """
    # 友情链接类型
    # 覆写基类的 LinkShowType.L：首页展示的是"首页位"的友情链接
    link_type = LinkShowType.I

    # 钩子①：首页只列出普通文章（type='a'）中已发布（status='p'）的
    def get_queryset_data(self):
        # 使用 Mixin 提供的优化查询方法
        return self.get_optimized_article_queryset().filter(
            type='a', status='p'
        )

    # 钩子②：缓存键按页码区分，因此第 1 页与第 2 页各自独立缓存
    def get_queryset_cache_key(self):
        return f'index_{self.page_number}'

    # 追加首页 SEO 数据（由模板的 {% block header %} 消费）
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        blog_setting = get_blog_setting()
        # 提供基础SEO数据
        context['seo_title'] = f"{blog_setting.site_name} | {blog_setting.site_description}"
        context['seo_description'] = blog_setting.site_seo_description
        context['seo_keywords'] = blog_setting.site_keywords
        return context


# 文章详情页。对应 URL name='detailbyid'，地址形如 /article/年/月/日/<id>.html。
# 这是唯一不继承 ArticleListView 的页面视图——它是单对象页，直接继承 DetailView。
class ArticleDetailView(DetailView):
    '''
    文章详情页面
    '''
    template_name = 'blog/article_detail.html'
    model = Article
    # URL 中的主键参数名，对应 urls.py 里的 <int:article_id>
    pk_url_kwarg = 'article_id'
    # 模板中通过 {{ article }} 访问当前文章
    context_object_name = "article"

    # 详情页需要额外准备：评论表单、顶级评论分页、上下篇导航、SEO 元数据与插件钩子
    def get_context_data(self, **kwargs):
        # 评论提交表单（字段定义在 comments 应用，而非 blog/forms.py）
        comment_form = CommentForm()

        # 优化：直接查询父评论，减少数据库查询
        from comments.models import Comment
        # 只取顶级评论（parent_comment=None）且有效（is_enable=True）的记录；
        # 子评论由 prefetch_related('comment_set__author') 一次性预加载，
        # 模板递归渲染回复时不再逐条查库，从而避免 N+1 查询
        parent_comments = Comment.objects.filter(
            article=self.object,
            parent_comment=None,
            is_enable=True
        ).select_related('author').prefetch_related(
            'comment_set__author'  # 预加载子评论及其作者
        ).order_by('-id')

        # 获取所有评论用于总数显示
        # 走 Article.comment_list()，该方法自带 10 小时缓存（键按文章 id 区分）
        article_comments = self.object.comment_list()

        # 顶级评论分页：每页条数由后台配置 article_comment_count 决定，
        # 页码来自 ?comment_page=N，与文章列表的 ?page= 相互独立
        blog_setting = get_blog_setting()
        paginator = Paginator(parent_comments, blog_setting.article_comment_count)
        page = self.request.GET.get('comment_page', '1')
        # 页码容错，源码在此确实覆盖了三种情况：
        #   a) page.isnumeric() 为假 —— 回退为 1（isnumeric() 不接受负号，
        #      因此 '-1' 这类带负号的字符串也走这一支）；
        #   b) 数字小于 1 —— 夹到 1；
        #   c) 数字大于 paginator.num_pages —— 夹到总页数。
        if not page.isnumeric():
            page = 1
        else:
            page = int(page)
            if page < 1:
                page = 1
            if page > paginator.num_pages:
                page = paginator.num_pages

        p_comments = paginator.page(page)
        next_page = p_comments.next_page_number() if p_comments.has_next() else None
        prev_page = p_comments.previous_page_number() if p_comments.has_previous() else None

        # 评论翻页链接直接拼在文章地址之后，并带 #commentlist-container 锚点，
        # 让翻页后浏览器自动定位回评论区
        if next_page:
            kwargs[
                'comment_next_page_url'] = self.object.get_absolute_url() + f'?comment_page={next_page}#commentlist-container'
        if prev_page:
            kwargs[
                'comment_prev_page_url'] = self.object.get_absolute_url() + f'?comment_page={prev_page}#commentlist-container'
        # form             —— 评论提交表单
        # article_comments —— 全部有效评论（模板用它显示评论总数）
        # p_comments       —— 当前页的顶级评论
        kwargs['form'] = comment_form
        kwargs['article_comments'] = article_comments
        kwargs['p_comments'] = p_comments
        kwargs['comment_count'] = len(
            article_comments) if article_comments else 0

        # 上下篇导航（是模型上的属性方法，自带 10 小时缓存）
        kwargs['next_article'] = self.object.next_article
        kwargs['prev_article'] = self.object.prev_article

        # 交给父类组装出最终上下文，之后再补充 SEO 数据与插件钩子
        context = super(ArticleDetailView, self).get_context_data(**kwargs)
        article = self.object
        
        # 添加基础SEO数据
        blog_setting = get_blog_setting()
        from django.utils.html import strip_tags
        from django.utils.text import Truncator
        from djangoblog.utils import CommonMarkdown
        
        # SEO 描述的处理思路：Markdown 正文 → HTML → 去标签 → 压缩空白 → 截断 150 字
        # 处理description：markdown -> HTML -> 纯文本，彻底去除格式
        html_content = CommonMarkdown.get_markdown(article.body)
        description = strip_tags(html_content)
        description = ' '.join(description.split())  # 规范化空白字符
        description = Truncator(description).chars(150, truncate='...')
        
        # 关键词取本文全部标签名；若文章没有标签，则回退到站点配置的 site_keywords
        # 处理keywords：去除空格，用逗号分隔
        tags = [tag.name.strip() for tag in article.tags.all()]
        keywords = ", ".join(tags) if tags else blog_setting.site_keywords
        
        # 写入三项 SEO 数据，供模板的 {% block header %} 输出 meta 标签
        context['seo_title'] = f"{article.title} | {blog_setting.site_name}"
        context['seo_description'] = description
        context['seo_keywords'] = keywords
        
        # 插件钩子①：动作名为常量 ARTICLE_DETAIL_LOAD，其值为 'article_detail_load'
        # （定义在 djangoblog/plugin_manage/hook_constants.py）。
        # 调用参数：article=文章对象、context=当前上下文 dict、request=请求对象。
        # 已注册的监听者：plugins/article_recommendation/plugin.py 中的
        #   ArticleRecommendationPlugin.on_article_detail_load(article, context, request, ...)，
        #   用途是向 context 写入 'article_recommendations'（文章底部推荐数据）。
        # 触发文章详情加载钩子，让插件可以添加额外的上下文数据
        from djangoblog.plugin_manage.hook_constants import ARTICLE_DETAIL_LOAD
        hooks.run_action(ARTICLE_DETAIL_LOAD, article=article, context=context, request=self.request)
        
        # 插件钩子②：动作名是字符串字面量 'after_article_body_get'，
        # 该名称未在 hook_constants.py 中定义成常量。
        # 调用参数只有 article= 与 request=，不传 context；
        # 因此它与钩子①既不是同一动作，也不具有相同效果。
        # 已注册的监听者：plugins/view_count/plugin.py 中的
        #   ViewCountPlugin.record_view(article, ...)，用途是调用 article.viewed() 累加浏览数。
        # Action Hook, 通知插件"文章详情已获取"
        hooks.run_action('after_article_body_get', article=article, request=self.request)
        return context


# 分类归档页。对应 URL name='category_detail' 与 'category_detail_page'。
class CategoryDetailView(SlugCachedMixin, OptimizedArticleQueryMixin, ArticleListView):
    """
    分类目录列表（重构版）

    使用 SlugCachedMixin 避免重复查询 Category
    使用 OptimizedArticleQueryMixin 优化文章查询
    """
    # 页面类型写死为"分类目录归档"，模板据此外显为分类页样式
    page_type = "分类目录归档"
    # URL 中分类标识的参数名，对应 urls.py 里的 <slug:category_name>
    slug_url_kwarg = 'category_name'
    # 告诉 SlugCachedMixin 该按哪个模型去取对象
    slug_model = Category

    # 钩子①：不只查该分类下的文章，还包含它全部子孙分类的文章
    def get_queryset_data(self):
        # 使用 Mixin 缓存的对象，只查询一次
        category = self.get_slug_object()
        categorynames = [c.name for c in category.get_sub_categorys()]

        return self.get_optimized_article_queryset().filter(
            category__name__in=categorynames, status='p'
        )

    # 钩子②：缓存键带上分类名与页码
    def get_queryset_cache_key(self):
        # 复用缓存的对象，不再重复查询数据库
        category = self.get_slug_object()
        return f'category_list_{category.name}_{self.page_number}'

    # 组装模板所需的 page_type / tag_name 与 SEO 数据
    def get_context_data(self, **kwargs):
        category = self.get_slug_object()
        categoryname = category.name

        # 分类名若带层级分隔符，则只取最后一段作为展示名
        try:
            categoryname = categoryname.split('/')[-1]
        except BaseException:
            pass

        # 模板用 page_type 判断当前是哪类归档页，用 tag_name 显示当前分类/标签/作者名
        kwargs['page_type'] = CategoryDetailView.page_type
        kwargs['tag_name'] = categoryname
        
        # 添加基础SEO数据
        blog_setting = get_blog_setting()
        article_count = self.get_queryset().count()
        kwargs['seo_title'] = f"{categoryname} | {blog_setting.site_name}"
        kwargs['seo_description'] = f"浏览 {categoryname} 分类下的所有文章，共 {article_count} 篇文章。"
        kwargs['seo_keywords'] = f"{categoryname}, {blog_setting.site_keywords}"
        
        return super(CategoryDetailView, self).get_context_data(**kwargs)


# 作者归档页。对应 URL name='author_detail' 与 'author_detail_page'。
# 注意它没有继承 SlugCachedMixin——作者名直接来自 URL kwargs，无需按 slug 查对象。
class AuthorDetailView(OptimizedArticleQueryMixin, ArticleListView):
    """
    作者详情页（重构版）

    使用 OptimizedArticleQueryMixin 优化文章查询
    """
    page_type = '作者文章归档'

    # 钩子②：缓存键里对作者名做 slugify，避免中文用户名直接进缓存键
    def get_queryset_cache_key(self):
        from uuslug import slugify
        author_name = slugify(self.kwargs['author_name'])
        return f'author_{author_name}_{self.page_number}'

    # 钩子①：按用户名精确匹配，且限定普通文章与已发布
    def get_queryset_data(self):
        author_name = self.kwargs['author_name']
        return self.get_optimized_article_queryset().filter(
            author__username=author_name, type='a', status='p'
        )

    # 组装模板所需的 page_type / tag_name 与 SEO 数据
    def get_context_data(self, **kwargs):
        author_name = self.kwargs['author_name']
        kwargs['page_type'] = AuthorDetailView.page_type
        kwargs['tag_name'] = author_name
        
        # 添加基础SEO数据
        blog_setting = get_blog_setting()
        article_count = self.get_queryset().count()
        kwargs['seo_title'] = f"{author_name} 的文章 | {blog_setting.site_name}"
        kwargs['seo_description'] = f"浏览 {author_name} 发表的所有文章，共 {article_count} 篇。"
        kwargs['seo_keywords'] = f"{author_name}, {blog_setting.site_keywords}"
        
        return super(AuthorDetailView, self).get_context_data(**kwargs)


# 标签归档页。对应 URL name='tag_detail' 与 'tag_detail_page'。
class TagDetailView(SlugCachedMixin, OptimizedArticleQueryMixin, ArticleListView):
    """
    标签列表页面（重构版）

    使用 SlugCachedMixin 避免重复查询 Tag
    使用 OptimizedArticleQueryMixin 优化文章查询
    """
    # 页面类型写死为"分类标签归档"（这是既有的文案写法）
    page_type = '分类标签归档'
    # URL 中标签标识的参数名，对应 urls.py 里的 <slug:tag_name>
    slug_url_kwarg = 'tag_name'
    # 告诉 SlugCachedMixin 该按哪个模型去取对象
    slug_model = Tag

    # 钩子①：按标签名穿透多对多关联表筛选文章
    def get_queryset_data(self):
        # 使用 Mixin 缓存的对象，只查询一次
        tag = self.get_slug_object()
        return self.get_optimized_article_queryset().filter(
            tags__name=tag.name, type='a', status='p'
        )

    # 钩子②：缓存键带上标签名与页码
    def get_queryset_cache_key(self):
        # 复用缓存的对象，不再重复查询数据库
        tag = self.get_slug_object()
        return f'tag_{tag.name}_{self.page_number}'

    # 组装模板所需的 page_type / tag_name 与 SEO 数据
    def get_context_data(self, **kwargs):
        tag = self.get_slug_object()
        kwargs['page_type'] = TagDetailView.page_type
        kwargs['tag_name'] = tag.name
        
        # 添加基础SEO数据
        blog_setting = get_blog_setting()
        article_count = self.get_queryset().count()
        kwargs['seo_title'] = f"{tag.name} | {blog_setting.site_name}"
        kwargs['seo_description'] = f"浏览所有关于 {tag.name} 的文章，共 {article_count} 篇内容。"
        kwargs['seo_keywords'] = f"{tag.name}, {blog_setting.site_keywords}"
        
        return super(TagDetailView, self).get_context_data(**kwargs)


# 文章归档页。对应 URL name='archives'（/archives.html），该路由额外做了整页响应缓存。
class ArchivesView(OptimizedArticleQueryMixin, ArticleListView):
    """
    文章归档页面（重构版）

    使用 OptimizedArticleQueryMixin 优化文章查询
    """
    page_type = '文章归档'
    # 关闭分页：归档页要一次展示全部文章，由模板按年月分组渲染
    paginate_by = None
    # 关闭页码解析：本页不接受 ?page= 参数
    page_kwarg = None
    # 覆写基类模板，改用归档专用模板
    template_name = 'blog/article_archives.html'

    # 钩子①：只按发布状态筛选，不限内容类型（独立页面也会出现在归档里）
    def get_queryset_data(self):
        return self.get_optimized_article_queryset().filter(status='p')

    # 钩子②：归档只有一页，缓存键是常量
    def get_queryset_cache_key(self):
        return 'archives'


# 友情链接页。对应 URL name='links'（/links.html）。
class LinkListView(ListView):
    model = Links
    template_name = 'blog/links_list.html'

    # 只展示启用中的链接，排序沿用模型 Meta 中的 sequence
    def get_queryset(self):
        return Links.objects.filter(is_enable=True)


# 全文搜索视图（基于 haystack）。
# 注意：它不在 blog/urls.py 中，而是在项目根路由 djangoblog/urls.py 里通过
#   search_view_factory(view_class=EsSearchView, form_class=...)
# 挂到 '^search' 上，URL name 为 'search'；
# 它也没有指定 template_name，使用 haystack 默认的 search/search.html。
class EsSearchView(SearchView):
    # 覆写表单构建，为搜索结果开启关键词高亮（模板端配合 highlight 过滤器使用）
    def build_form(self, form_kwargs=None):
        """Override to enable highlighting"""
        if form_kwargs is None:
            form_kwargs = {}

        # Enable highlighting for search results
        from haystack.query import SearchQuerySet
        if self.searchqueryset is None:
            sqs = SearchQuerySet().highlight()
        else:
            sqs = self.searchqueryset.highlight()

        form_kwargs['searchqueryset'] = sqs
        return super().build_form(form_kwargs=form_kwargs)

    # 组装搜索页上下文：查询词、表单、分页对象与拼写建议
    def get_context(self):
        paginator, page = self.build_page()
        context = {
            "query": self.query,
            "form": self.form,
            "page": page,
            "paginator": paginator,
            "suggestion": None,
        }
        # 若搜索后端支持拼写纠错，则给出"你是不是想搜 xxx"的建议
        if hasattr(self.results, "query") and self.results.query.backend.include_spelling:
            context["suggestion"] = self.results.query.get_spelling_suggestion()
        context.update(self.extra_context())

        return context


# 图床上传接口（仅接受 POST）。
# csrf_exempt 表示不受 Django CSRF 保护，改用 URL 上的 sign 参数做校验；
# 调用方需自行实现（例如后台的 Markdown 编辑器插入图片时调用）。
@csrf_exempt
def fileupload(request):
    """
    该方法需自己写调用端来上传图片，该方法仅提供图床功能
    :param request:
    :return:
    """
    if request.method == 'POST':
        # 鉴权：URL 必须带 sign，且 sign 等于 SECRET_KEY 的二次 sha256，
        # 否则直接返回 403。注意这里用普通字符串比较，非恒定时间比较。
        sign = request.GET.get('sign', None)
        if not sign:
            return HttpResponseForbidden()
        if not sign == get_sha256(get_sha256(settings.SECRET_KEY)):
            return HttpResponseForbidden()
        # 逐个处理上传的文件，返回各文件的访问 URL 列表
        response = []
        for filename in request.FILES:
            # 按 年/月/日 分目录存放
            timestr = timezone.now().strftime('%Y/%m/%d')
            imgextensions = ['jpg', 'png', 'jpeg', 'bmp']
            fname = u''.join(str(filename))
            # 判断是否图片：对文件名做子串包含检查（fname.find(i) >= 0），
            # 只要文件名中出现 jpg/png/jpeg/bmp 任一片段即判为图片。
            # 这不是严格的扩展名校验——真正写入时用的扩展名由下面的
            # os.path.splitext 取用，而像 "photo.jpg.txt" 这类文件名同样会被判为图片。
            isimage = len([i for i in imgextensions if fname.find(i) >= 0]) > 0
            base_dir = os.path.join(settings.STATICFILES, "files" if not isimage else "image", timestr)
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
            # 用 uuid 重命名，避免同名覆盖与路径猜测
            savepath = os.path.normpath(os.path.join(base_dir, f"{uuid.uuid4().hex}{os.path.splitext(filename)[-1]}"))
            # 这里是对路径做字符串前缀检查：若规范化后的 savepath 不以 base_dir 开头则拒绝。
            # 注意它只是字符串层面的前缀比较，并不构成完整的目录穿越防护——
            # 未做 realpath 解析、也不处理符号链接等情况；且被拒绝时返回的文案
            # "only for post" 与实际语义（路径校验失败）并不相符。
            if not savepath.startswith(base_dir):
                return HttpResponse("only for post")
            with open(savepath, 'wb+') as wfile:
                for chunk in request.FILES[filename].chunks():
                    wfile.write(chunk)
            # 图片再做一次有损压缩（quality=20），显著减小体积
            if isimage:
                from PIL import Image
                image = Image.open(savepath)
                image.save(savepath, quality=20, optimize=True)
            url = static(savepath)
            response.append(url)
        return HttpResponse(response)

    else:
        # 非 POST 请求一律拒绝
        return HttpResponse("only for post")


# ===== 错误处理视图 =====
# 注意：这些函数保留是为了向后兼容
# 实际实现已经移动到 djangoblog.error_views
# 可以在 urls.py 中直接引用新的实现
# 这三个视图由项目根路由 djangoblog/urls.py 绑定：
#   handler404 = 'blog.views.page_not_found_view'
#   handler500 = 'blog.views.server_error_view'
# 另外那里写的是一个 handle403（少了字母 r），Django 并不会识别它，
# 因此 403 页面实际走 Django 默认实现——属既有问题，本文件保持原样不改。

from djangoblog.error_views import (
    page_not_found_view,
    server_error_view,
    permission_denied_view
)


# 清缓存接口。对应 URL name='clean'（/clean）。
# 调用即清空整站缓存，且没有任何鉴权，仅适合内部运维使用，切勿对外暴露。
def clean_cache_view(request):
    cache.clear()
    return HttpResponse('ok')
