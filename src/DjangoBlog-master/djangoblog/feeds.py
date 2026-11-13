# ZZC: 本模块生成博客 RSS 订阅源，向订阅者提供最近发布的文章摘要和链接。
from django.contrib.auth import get_user_model
from django.contrib.syndication.views import Feed
from django.utils import timezone
from django.utils.feedgenerator import Rss201rev2Feed

from blog.models import Article
from djangoblog.utils import CommonMarkdown


# ZZC: DjangoBlogFeed 继承 Django Feed，将已发布文章转换为标准 RSS 2.0 数据。
class DjangoBlogFeed(Feed):
    feed_type = Rss201rev2Feed

    description = '大巧无工,重剑无锋.'
    title = "且听风吟 大巧无工,重剑无锋. "
    link = "/feed/"

    # ZZC: 从用户模型读取首个用户的信息作为订阅源作者。
    def author_name(self):
        return get_user_model().objects.first().nickname

    # ZZC: 返回作者主页地址，供 RSS 阅读器展示作者入口。
    def author_link(self):
        return get_user_model().objects.first().get_absolute_url()

    # ZZC: 只选取类型为文章且状态为已发布的数据，并限制为最近五篇。
    def items(self):
        return Article.objects.filter(type='a', status='p').order_by('-pub_time')[:5]

    # ZZC: RSS 条目标题直接使用文章标题。
    def item_title(self, item):
        return item.title

    # ZZC: 将 Markdown 正文转换为 HTML 摘要，便于订阅阅读器统一展示。
    def item_description(self, item):
        return CommonMarkdown.get_markdown(item.body)

    # ZZC: 版权年份在每次生成订阅源时根据当前时间动态计算。
    def feed_copyright(self):
        now = timezone.now()
        return "Copyright© {year} 且听风吟".format(year=now.year)

    # ZZC: 每个 RSS 条目链接到文章的规范绝对地址。
    def item_link(self, item):
        return item.get_absolute_url()

    # ZZC: 当前实现不返回自定义 GUID，由 Feed 框架使用默认标识逻辑。
    def item_guid(self, item):
        return
