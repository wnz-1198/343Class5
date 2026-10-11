# blog 模块的数据模型定义
# ---------------------------------------------------------------------------
# 本文件包含 7 个模型类与 1 个 TextChoices 枚举，共 8 个类定义：
#   LinkShowType —— 友情链接展示位置枚举（TextChoices，不是模型，不建表）
#   BaseModel    —— 抽象模型基类：统一主键与时间戳，并封装 slug 自动生成（不建表）
#   Article      —— 文章（type 字段同时兼顾"独立页面"）
#   Category     —— 文章分类（通过 parent_category 自关联成树）
#   Tag          —— 文章标签
#   Links        —— 友情链接
#   SideBar      —— 侧边栏自定义 HTML 区块
#   BlogSettings —— 全站配置（全站预期只保留一行，约束方式见下文该类说明）
#
# 重要：本文件不含任何 signal，模型保存后的缓存失效逻辑统一放在
#      djangoblog/blog_signals.py，排查缓存行为时需到那边查看。
# 注意：本文件向外依赖 djangoblog 包（utils / constants）与 comments 应用
#      （Article.comment_list 使用反向关联 comment_set），改动前先确认影响面。
# ---------------------------------------------------------------------------
import logging
import re
from abc import abstractmethod

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.timezone import now
from django.utils.translation import gettext_lazy as _
# MDTextField 由第三方应用 django-mdeditor 提供，对应后台的 Markdown 编辑器
from mdeditor.fields import MDTextField
# uuslug 支持中文的 slug 生成，用于把标题/名称转成 URL 友好的字符串
from uuslug import slugify

# djangoblog.utils：项目级工具，提供缓存对象 cache 与带过期时间的 cache_decorator
from djangoblog.utils import cache_decorator, cache
from djangoblog.utils import get_current_site
# CacheTimeout / CacheKey 集中定义了缓存的过期秒数与键名模板
from djangoblog.constants import CacheTimeout, CacheKey

logger = logging.getLogger(__name__)


# 友情链接的展示位置枚举。
# 取值会被 Links.show_type 引用，前端据此决定一条链接显示在首页/列表/文章页等位置。
class LinkShowType(models.TextChoices):
    I = ('i', _('index'))
    L = ('l', _('list'))
    P = ('p', _('post'))
    A = ('a', _('all'))
    S = ('s', _('slide'))


# 抽象基类：Article / Category / Tag 三个核心模型都继承它。
# 三个子类各自建表，本类因 Meta.abstract = True 不会生成自己的数据库表。
class BaseModel(models.Model):
    # 显式指定自增主键字段，作为模型记录的唯一标识
    id = models.AutoField(primary_key=True)
    # 创建时间：默认取当前时间
    creation_time = models.DateTimeField(_('creation time'), default=now)
    # 修改时间：默认值同样是 now，并非 auto_now，因此不会随保存自动更新
    last_modify_time = models.DateTimeField(_('modify time'), default=now)

    # 统一入口的 save：在真正写库前做两件特殊处理
    def save(self, *args, **kwargs):
        # 判断本次保存是否只是为更新浏览数（由 Article.viewed() 触发）
        is_update_views = isinstance(
            self,
            Article) and 'update_fields' in kwargs and kwargs['update_fields'] == ['views']
        if is_update_views:
            # 浏览数 +1 是最高频的写操作，这里绕过完整 save 直接发一条 UPDATE，
            # 既避免覆盖其他字段，也避免触发下面的 slug 重算
            Article.objects.filter(pk=self.pk).update(views=self.views)
        else:
            # 若子类定义了 slug 字段，则按"标题优先、否则名称"自动生成，保证 URL 友好
            if 'slug' in self.__dict__:
                slug = getattr(
                    self, 'title') if 'title' in self.__dict__ else getattr(
                    self, 'name')
                setattr(self, 'slug', slugify(slug))
            super().save(*args, **kwargs)

    # 拼接带协议与域名的完整 URL，供后台"在站点上查看"及 SEO（canonical/分享）使用
    def get_full_url(self):
        site = get_current_site().domain
        url = "https://{site}{path}".format(site=site,
                                            path=self.get_absolute_url())
        return url

    class Meta:
        abstract = True

    # 抽象方法：要求每个子类必须实现自己的详情页 URL 规则
    @abstractmethod
    def get_absolute_url(self):
        pass


class Article(BaseModel):
    """文章"""
    # 文章状态：d = 草稿（不进前台列表），p = 已发布
    STATUS_CHOICES = (
        ('d', _('Draft')),
        ('p', _('Published')),
    )
    # 评论开关：o = 开放评论，c = 关闭评论
    COMMENT_STATUS = (
        ('o', _('Open')),
        ('c', _('Close')),
    )
    # 内容类型：a = 普通文章，p = 独立页面（如"关于我们"这类固定页面）。
    # 注意：不能笼统地说独立页面不进列表——是否被列出取决于各视图自己的查询条件。
    # 以 blog/views.py 为例（已逐条核对）：
    #   IndexView、TagDetailView、AuthorDetailView 显式加了 type='a'，会排除独立页面；
    #   ArchivesView 只过滤 status='p'，CategoryDetailView 只按分类名与 status='p' 过滤，
    #   二者都没有 type 条件，因此独立页面会出现在归档页与分类页中。
    TYPE = (
        ('a', _('Article')),
        ('p', _('Page')),
    )
    # 标题：全站唯一，因此不允许出现两篇同名文章
    title = models.CharField(_('title'), max_length=200, unique=True)
    # 正文：使用 django-mdeditor 提供的 Markdown 字段，后台带可视化编辑器
    body = MDTextField(_('body'))
    # 发布时间：与 creation_time 不同，它可由作者指定（如补发/定时），列表排序依赖它
    pub_time = models.DateTimeField(
        _('publish time'), blank=False, null=False, default=now)
    # 发布状态，默认为"已发布"
    status = models.CharField(
        _('status'),
        max_length=1,
        choices=STATUS_CHOICES,
        default='p')
    # 单篇的评论开关，默认开放
    comment_status = models.CharField(
        _('comment status'),
        max_length=1,
        choices=COMMENT_STATUS,
        default='o')
    # 内容类型，默认为普通文章
    type = models.CharField(_('type'), max_length=1, choices=TYPE, default='a')
    # 浏览次数：由 Article.viewed() 自增，也是"热门文章"的排序依据
    views = models.PositiveIntegerField(_('views'), default=0)
    # 作者：经 settings.AUTH_USER_MODEL 间接指向自定义用户模型 accounts.BlogUser
    # 未声明 related_name，因此反向访问器是默认的 article_set
    # on_delete=CASCADE：用户被删除时其文章一并删除
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name=_('author'),
        blank=False,
        null=False,
        on_delete=models.CASCADE)
    # 排序权重：数值越大越靠前（Meta.ordering 以 -article_order 优先），用于人工置顶
    article_order = models.IntegerField(
        _('order'), blank=False, null=False, default=0)
    # 是否在详情页显示文章目录（TOC）
    show_toc = models.BooleanField(_('show toc'), blank=False, null=False, default=False)
    # 所属分类：多对一。未声明 related_name，反向访问器为 category.article_set
    # on_delete=CASCADE：分类被删除时其下文章一并删除
    category = models.ForeignKey(
        'Category',
        verbose_name=_('category'),
        on_delete=models.CASCADE,
        blank=False,
        null=False)
    # 标签：多对多，未使用 through 自定义中间表，由 Django 自动生成关联表
    # blank=True 表示可以不选标签；反向访问器为 tag.article_set
    tags = models.ManyToManyField('Tag', verbose_name=_('tag'), blank=True)

    # 返回正文原文，供需要字符串形式的调用方（如搜索索引、外部接口）使用
    def body_to_string(self):
        return self.body

    # 后台与调试时展示文章标题
    def __str__(self):
        return self.title

    class Meta:
        # 默认排序：先按人工权重 article_order 降序，再按发布时间降序
        ordering = ['-article_order', '-pub_time']
        verbose_name = _('article')
        verbose_name_plural = verbose_name
        # 支持 Article.objects.latest()，以 id 作为"最新"依据
        get_latest_by = 'id'
        # 四条复合索引，每条针对一组字段组合（逐条说明见下）。
        # 这里只声明"建了哪些索引"；具体某条查询能否命中索引、
        # 是否退化为全表扫描，取决于数据库优化器的执行计划，不能一概而论。
        indexes = [
            # 优化列表查询：type + status + pub_time组合索引
            models.Index(fields=['type', 'status', '-pub_time'], name='idx_type_status_pub'),
            # 优化热门文章查询：status + views组合索引
            models.Index(fields=['status', '-views'], name='idx_status_views'),
            # 优化作者文章查询：author + status + type组合索引
            models.Index(fields=['author', 'status', 'type'], name='idx_author_status_type'),
            # 优化分类查询：category + status组合索引
            models.Index(fields=['category', 'status'], name='idx_category_status'),
        ]

    # 文章详情页 URL：形如 /article/2026/10/11/123.html（路径含年月日与 .html 后缀）
    # 注意路径里的年月日取自 creation_time 而非 pub_time，两者不一致时以 creation_time 为准
    def get_absolute_url(self):
        return reverse('blog:detailbyid', kwargs={
            'article_id': self.id,
            'year': self.creation_time.year,
            'month': self.creation_time.month,
            'day': self.creation_time.day
        })

    # 返回从当前分类上溯到根的 (名称, URL) 列表，供面包屑导航使用；结果缓存 10 小时
    @cache_decorator(CacheTimeout.HOUR_10)
    def get_category_tree(self):
        tree = self.category.get_category_tree()
        names = list(map(lambda c: (c.name, c.get_absolute_url()), tree))

        return names

    # 覆写 save：方法体只有一句 super().save()，没有附加任何逻辑，
    # 因此实际行为完全由父类 BaseModel.save 决定（含其中的 views 特判与 slug 生成）。
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    # 浏览数自增。只传 update_fields=['views']，
    # 会被 BaseModel.save 识别为"仅更新浏览数"并走轻量 UPDATE 分支
    def viewed(self):
        self.views += 1
        self.save(update_fields=['views'])

    # 取本文的有效评论列表，带手写缓存（键按文章 id 区分，过期 10 小时）
    def comment_list(self):
        cache_key = CacheKey.ARTICLE_COMMENTS.format(article_id=self.id)
        value = cache.get(cache_key)
        if value:
            logger.info(f'Cache HIT: article comments (id={self.id})')
            return value
        else:
            # comment_set 是反向关联：外键其实定义在 comments 应用的 Comment 模型上
            # is_enable=True 用于过滤掉待审核/已禁用的评论
            comments = self.comment_set.filter(is_enable=True).order_by('-id')
            cache.set(cache_key, comments, CacheTimeout.HOUR_10)
            logger.info(f'Cache MISS: article comments (id={self.id})')
            return comments

    # 生成该文章在自定义 admin 站点中的编辑页地址
    def get_admin_url(self):
        info = (self._meta.app_label, self._meta.model_name)
        return reverse('admin:%s_%s_change' % info, args=(self.pk,))

    # 取"下一篇"：id 更大且已发布的第一篇（按 id 升序）
    @cache_decorator(expiration=CacheTimeout.HOUR_10)
    def next_article(self):
        # 下一篇
        return Article.objects.filter(
            id__gt=self.id, status='p').order_by('id').first()

    # 从"id 小于当前文章且已发布"的集合中取 first()。
    # 这里没有显式 order_by，所以 first() 依据的是模型 Meta.ordering
    # （['-article_order', '-pub_time']）：返回该集合中 article_order 最大、
    # 同权重时 pub_time 最新的那一篇，不保证是 id 相邻的上一篇文章。
    @cache_decorator(expiration=CacheTimeout.HOUR_10)
    def prev_article(self):
        # 前一篇
        return Article.objects.filter(id__lt=self.id, status='p').first()

    # 用正则从 Markdown 正文里提取第一张图片的地址，供列表页缩略图使用
    def get_first_image_url(self):
        """
        Get the first image url from article.body.
        :return:
        """
        match = re.search(r'!\[.*?\]\((.+?)\)', self.body)
        if match:
            return match.group(1)
        return ""


class Category(BaseModel):
    """文章分类"""
    # 分类名称：唯一，同时是 Article.category 的关联依据
    name = models.CharField(_('category name'), max_length=30, unique=True)
    # 父分类：自关联外键，构成任意层级的分类树；顶级分类该字段为 NULL
    # 未声明 related_name，反向访问器为 category_set
    # on_delete=CASCADE：删除父分类会级联删除其所有子分类
    parent_category = models.ForeignKey(
        'self',
        verbose_name=_('parent category'),
        blank=True,
        null=True,
        on_delete=models.CASCADE)
    # URL 友好标识：由 BaseModel.save 依据 name 自动生成，前台按 slug 访问
    slug = models.SlugField(default='no-slug', max_length=60, blank=True)
    # 排序权重：数值越大越靠前（Meta.ordering 为 -index）
    index = models.IntegerField(default=0, verbose_name=_('index'))

    class Meta:
        # 默认按人工权重降序
        ordering = ['-index']
        verbose_name = _('category')
        verbose_name_plural = verbose_name

    # 分类页 URL：/category/<slug>.html，用 slug 而非主键
    def get_absolute_url(self):
        return reverse(
            'blog:category_detail', kwargs={
                'category_name': self.slug})

    def __str__(self):
        return self.name

    # 向上递归：返回 [自身, 父分类, 祖父分类, ...] 直到顶级分类，用于面包屑导航
    @cache_decorator(CacheTimeout.HOUR_10)
    def get_category_tree(self):
        """
        递归获得分类目录的父级
        :return:
        """
        categorys = []

        def parse(category):
            categorys.append(category)
            if category.parent_category:
                parse(category.parent_category)

        parse(self)
        return categorys

    # 向下递归：返回 [自身] + 全部子孙分类，结果缓存 10 小时。
    # 实现上先用 all() 一次性取出全部分类再在内存中筛选，避免逐层查库。
    # 分类列表视图正是靠它把查询范围从"该分类"扩展到"该分类及其所有子分类"。
    @cache_decorator(CacheTimeout.HOUR_10)
    def get_sub_categorys(self):
        """
        获得当前分类目录所有子集
        :return:
        """
        categorys = []
        all_categorys = Category.objects.all()

        def parse(category):
            if category not in categorys:
                categorys.append(category)
            childs = all_categorys.filter(parent_category=category)
            for child in childs:
                if category not in categorys:
                    categorys.append(child)
                parse(child)

        parse(self)
        return categorys


class Tag(BaseModel):
    """文章标签"""
    # 标签名称：唯一，与 Article.tags 多对多关联
    name = models.CharField(_('tag name'), max_length=30, unique=True)
    # URL 友好标识：由 BaseModel.save 依据 name 自动生成
    slug = models.SlugField(default='no-slug', max_length=60, blank=True)

    def __str__(self):
        return self.name

    # 标签页 URL：/tag/<slug>.html
    def get_absolute_url(self):
        return reverse('blog:tag_detail', kwargs={'tag_name': self.slug})

    # 统计该标签下的文章数。用 tags__name 反向穿透多对多关联表，
    # 加 distinct() 是因为联表查询可能产生重复行；结果缓存 10 小时
    @cache_decorator(CacheTimeout.HOUR_10)
    def get_article_count(self):
        return Article.objects.filter(tags__name=self.name).distinct().count()

    class Meta:
        # 标签数量通常较多，按名称字典序排列便于查找
        ordering = ['name']
        verbose_name = _('tag')
        verbose_name_plural = verbose_name


# 友情链接。注意：它直接继承 models.Model 而非 BaseModel，
# 因此没有 slug 字段，且修改时间字段名叫 last_mod_time（与 BaseModel 的 last_modify_time 不同）。
class Links(models.Model):
    """友情链接"""

    # 链接名称：唯一
    name = models.CharField(_('link name'), max_length=30, unique=True)
    # 目标地址
    link = models.URLField(_('link'))
    # 展示顺序：唯一，避免出现次序并列
    sequence = models.IntegerField(_('order'), unique=True)
    # 是否在前台展示
    is_enable = models.BooleanField(
        _('is show'), default=True, blank=False, null=False)
    # 展示位置，取值来自 LinkShowType；LinkShowType.I 表示"首页"
    show_type = models.CharField(
        _('show type'),
        max_length=1,
        choices=LinkShowType.choices,
        default=LinkShowType.I)
    # 两个时间字段为普通 DateTimeField（无 auto_now），不会自动更新
    creation_time = models.DateTimeField(_('creation time'), default=now)
    last_mod_time = models.DateTimeField(_('modify time'), default=now)

    class Meta:
        ordering = ['sequence']
        verbose_name = _('link')
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


# 侧边栏自定义区块：允许管理员填入任意 HTML（如公告、统计代码）。
# 同样直接继承 models.Model，时间字段名为 last_mod_time。
class SideBar(models.Model):
    """侧边栏,可以展示一些html内容"""
    # 区块标题
    name = models.CharField(_('title'), max_length=100)
    # 区块内容：文本/HTML，由模板决定是否按 safe 方式输出
    content = models.TextField(_('content'))
    # 展示顺序：唯一
    sequence = models.IntegerField(_('order'), unique=True)
    # 是否启用该区块
    is_enable = models.BooleanField(_('is enable'), default=True)
    creation_time = models.DateTimeField(_('creation time'), default=now)
    last_mod_time = models.DateTimeField(_('modify time'), default=now)

    class Meta:
        ordering = ['sequence']
        verbose_name = _('sidebar')
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


# 全站配置。预期全站只保留一行，但该约束不是数据库层面的：
#   后台由 BlogSettingsAdmin.has_add_permission / has_delete_permission 限制新增与删除；
#   模型由下面的 clean() 在表单校验阶段报错。
# 数据库本身没有唯一约束，所以绕过表单的直接 save()、bulk_create()、原生 SQL
# 等写入路径仍可能写入第二行。
# 同样直接继承 models.Model，时间字段名为 last_mod_time。
class BlogSettings(models.Model):
    """blog的配置"""

    # 可选的主题配色方案。取值由下面的 color_scheme 字段使用，
    # 最终会输出到 base.html 的 <body data-color-scheme="...">，驱动前端主题色。
    COLOR_SCHEMES = (
        ('purple', _('紫色主题 - Purple Dream')),
        ('blue', _('蓝色主题 - Ocean Blue')),
        ('green', _('绿色主题 - Forest Green')),
        ('orange', _('橙色主题 - Sunset Orange')),
        ('pink', _('粉色主题 - Cherry Blossom')),
        ('red', _('红色主题 - Ruby Red')),
        ('indigo', _('靛蓝主题 - Midnight Indigo')),
        ('teal', _('青色主题 - Teal Wave')),
    )

    # 站点名称：显示在导航栏与页面标题
    site_name = models.CharField(
        _('site name'),
        max_length=200,
        null=False,
        blank=False,
        default='')
    # 站点简介
    site_description = models.TextField(
        _('site description'),
        max_length=1000,
        null=False,
        blank=False,
        default='')
    # SEO 描述：写入页面 meta description
    site_seo_description = models.TextField(
        _('site seo description'), max_length=1000, null=False, blank=False, default='')
    # SEO 关键词：写入 meta keywords，也作为文章没有标签时的兜底关键词
    site_keywords = models.TextField(
        _('site keywords'),
        max_length=1000,
        null=False,
        blank=False,
        default='')
    # 列表页文章摘要的截断长度（字符数）
    article_sub_length = models.IntegerField(_('article sub length'), default=300)
    # 侧边栏"最新文章"显示条数
    sidebar_article_count = models.IntegerField(_('sidebar article count'), default=10)
    # 侧边栏"最新评论"显示条数
    sidebar_comment_count = models.IntegerField(_('sidebar comment count'), default=5)
    # 文章详情页每页显示的顶级评论条数（ArticleDetailView 用它作为 Paginator 的每页大小）
    article_comment_count = models.IntegerField(_('article comment count'), default=5)
    # 是否展示 Google AdSense 广告
    show_google_adsense = models.BooleanField(_('show adsense'), default=False)
    # AdSense 广告代码片段
    google_adsense_codes = models.TextField(
        _('adsense code'), max_length=2000, null=True, blank=True, default='')
    # 全站评论总开关：与文章的 comment_status 共同决定评论区是否显示
    open_site_comment = models.BooleanField(_('open site comment'), default=True)
    # 主题配色，取值来自上面的 COLOR_SCHEMES
    color_scheme = models.CharField(
        _('配色方案'),
        max_length=20,
        choices=COLOR_SCHEMES,
        default='purple',
        help_text=_('选择网站的主题配色方案'))
    # 公共头部：会被原样注入每个页面的 <head>，内容需可信（相当于可配置的模板代码）
    global_header = models.TextField("公共头部", null=True, blank=True, default='')
    # 公共尾部：会被原样注入每个页面底部，内容需可信
    global_footer = models.TextField("公共尾部", null=True, blank=True, default='')
    # ICP 备案号
    beian_code = models.CharField(
        '备案号',
        max_length=2000,
        null=True,
        blank=True,
        default='')
    # 网站统计代码（如百度统计）
    analytics_code = models.TextField(
        "网站统计代码",
        max_length=1000,
        null=False,
        blank=False,
        default='')
    # 是否显示公安备案号
    show_gongan_code = models.BooleanField(
        '是否显示公安备案号', default=False, null=False)
    # 公安备案号
    gongan_beiancode = models.TextField(
        '公安备案号',
        max_length=2000,
        null=True,
        blank=True,
        default='')
    # 新评论是否需要审核后才展示（最终体现为模板里的 COMMENT_NEED_REVIEW）
    comment_need_review = models.BooleanField(
        '评论是否需要审核', default=False, null=False)

    class Meta:
        verbose_name = _('Website configuration')
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.site_name

    # 模型校验：除自身外若已存在其他配置行，则抛出 ValidationError。
    # clean() 由 full_clean() 调用，而 ModelForm 校验会触发 full_clean()，
    # 因此经后台表单保存会走到这里；但直接调用 save() 不会触发 clean()。
    # 这是"表单/模型校验"层面的限制，不等同于数据库唯一约束。
    def clean(self):
        if BlogSettings.objects.exclude(id=self.id).count():
            raise ValidationError(_('There can only be one configuration'))

    # 保存后清空全部缓存：站点配置影响导航、SEO、配色等全站渲染，必须立即失效
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        from djangoblog.utils import cache
        cache.clear()
