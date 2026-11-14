"""文章 Markdown 导出的功能与权限测试。"""

from django.test import TestCase
from django.urls import reverse

from blog.models import Article
from djangoblog.test_base import BaseTestCase


class ArticleExportViewTest(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse('blog:export_markdown', kwargs={
            'year': self.article.creation_time.year,
            'month': self.article.creation_time.month,
            'day': self.article.creation_time.day,
            'article_id': self.article.pk,
        })

    def test_published_article_can_be_exported_anonymously(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('text/markdown'))
        self.assertIn('attachment;', response['Content-Disposition'])
        self.assertIn(self.article.title, response.content.decode('utf-8'))

    def test_draft_is_hidden_from_anonymous_user(self):
        self.article.status = Article.STATUS_CHOICES[0][0]
        self.article.save(update_fields=['status'])

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 404)

    def test_author_can_export_own_draft(self):
        self.article.status = Article.STATUS_CHOICES[0][0]
        self.article.save(update_fields=['status'])
        self.client.force_login(self.article.author)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn('测试内容', response.content.decode('utf-8'))

    def test_superuser_can_export_any_article(self):
        self.article.status = Article.STATUS_CHOICES[0][0]
        self.article.save(update_fields=['status'])
        self.client.force_login(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)


class ArticleExportContentTest(TestCase):
    def test_non_ascii_filename_uses_rfc_5987_form(self):
        from blog.services import markdown_attachment_header

        class Stub:
            pk = 7
            title = '中文标题'

        header = markdown_attachment_header(Stub())
        self.assertIn('filename="article-7.md"', header)
        self.assertIn("filename*=UTF-8''", header)
