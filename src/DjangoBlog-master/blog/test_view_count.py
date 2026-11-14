"""浏览量并发安全的回归测试。"""

from blog.models import Article
from djangoblog.test_base import BaseTestCase


class ArticleViewCountTest(BaseTestCase):
    def test_stale_instances_do_not_lose_view_increments(self):
        first = Article.objects.get(pk=self.article.pk)
        second = Article.objects.get(pk=self.article.pk)

        first.viewed()
        second.viewed()

        self.article.refresh_from_db(fields=['views'])
        self.assertEqual(self.article.views, 2)
