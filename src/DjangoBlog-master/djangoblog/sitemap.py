# ZZC: 本模块定义站点地图数据源，帮助搜索引擎发现首页、文章、分类、标签和作者页面。
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from blog.models import Article, Category, Tag


# ZZC: 静态页面地图当前只收录博客首页，并声明较低的更新优先级。
class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'daily'

    # ZZC: items() 返回 URL 名称，随后由 location() 解析为实际地址。
    def items(self):
        return ['blog:index', ]

    # ZZC: 使用 reverse() 避免在路由变化后手动维护首页 URL。
    def location(self, item):
        return reverse(item)


# ZZC: 文章地图只收录已发布文章，最后修改时间用于提示搜索引擎重新抓取。
class ArticleSiteMap(Sitemap):
    changefreq = "monthly"
    priority = "0.6"

    # ZZC: 查询所有已发布文章作为站点地图条目。
    def items(self):
        return Article.objects.filter(status='p')

    # ZZC: 将文章最后修改时间写入站点地图的 lastmod 字段。
    def lastmod(self, obj):
        return obj.last_modify_time


# ZZC: 分类地图列出全部分类页面，并返回各分类的最后修改时间。
class CategorySiteMap(Sitemap):
    changefreq = "Weekly"
    priority = "0.6"

    # ZZC: 分类数量通常较少，直接查询全部记录。
    def items(self):
        return Category.objects.all()

    # ZZC: 使用分类模型维护的最后修改时间。
    def lastmod(self, obj):
        return obj.last_modify_time


# ZZC: 标签地图列出所有标签页面及其最后修改时间。
class TagSiteMap(Sitemap):
    changefreq = "Weekly"
    priority = "0.3"

    # ZZC: 查询所有标签对象。
    def items(self):
        return Tag.objects.all()

    # ZZC: 将标签最后修改时间提供给搜索引擎。
    def lastmod(self, obj):
        return obj.last_modify_time


# ZZC: 作者地图按作者去重，避免同一作者因多篇文章而重复出现在站点地图中。
class UserSiteMap(Sitemap):
    changefreq = "Weekly"
    priority = "0.3"

    # ZZC: set 负责去重，再由 list 恢复为站点地图需要的可迭代结构。
    def items(self):
        return list(set(map(lambda x: x.author, Article.objects.all())))

    # ZZC: 作者页面的最后修改时间使用账号注册时间。
    def lastmod(self, obj):
        return obj.date_joined
