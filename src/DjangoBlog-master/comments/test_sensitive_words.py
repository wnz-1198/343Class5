# DB ============================================================

# DB comments/test_sensitive_words.py —— 敏感词过滤测试

# DB ============================================================

# DB 对应《comments敏感词过滤设计方案.md》第 4 节测试计划：

# DB - 单元测试：check_sensitive_words 纯函数（命中/大小写归一化/空输入）

# DB - 视图测试：提交拦截、正常评论回归、楼中楼回复拦截

# DB 基类复用 djangoblog.test_base.BaseTestCase（呼应质量报告 Q9：

# DB 避免 test_views.py 中 setUp 复制粘贴的测试改进方向）

# DB ============================================================

from unittest.mock import patch

from django.urls import reverse

from comments.models import Comment
from comments.sensitive_words import check_sensitive_words
from djangoblog.test_base import BaseTestCase


class SensitiveWordsFunctionTest(BaseTestCase):
    """单元测试：check_sensitive_words 纯函数"""

    def test_clean_text_returns_empty(self):
        """纯净文本：无命中，返回空列表"""
        self.assertEqual(check_sensitive_words('这篇文章写得很好，值得一读'), [])

    def test_single_hit(self):
        """命中单个敏感词：返回包含该词的列表"""
        hits = check_sensitive_words('这里可以代开发票吗')
        self.assertEqual(hits, ['代开发票'])

    def test_multiple_hits_keep_library_order(self):
        """命中多个敏感词：全部返回且保持词库顺序"""
        hits = check_sensitive_words('赌博和刷单都在正文里')
        self.assertEqual(hits, ['赌博', '刷单'])

    def test_empty_text_returns_empty(self):
        """空输入：直接返回空列表，不做匹配"""
        self.assertEqual(check_sensitive_words(''), [])
        self.assertEqual(check_sensitive_words(None), [])

    def test_case_insensitive_for_english_words(self):
        """英文词大小写归一化：'SPAM' 等价 'spam'"""
        # DB 用 patch 注入英文词库，验证归一化逻辑（不改生产词库）

        with patch('comments.sensitive_words.load_sensitive_words',
                   return_value=['spam']):
            self.assertEqual(check_sensitive_words('this is SPAM content'), ['spam'])
            self.assertEqual(check_sensitive_words('this is not'), [])

    def test_empty_word_in_library_never_matches(self):
        """词库含空串时的边界：不应对所有文本都命中"""
        with patch('comments.sensitive_words.load_sensitive_words',
                   return_value=['']):
            self.assertEqual(check_sensitive_words('任意内容'), [])


class SensitiveWordsViewTest(BaseTestCase):
    """视图测试：CommentPostView 集成敏感词过滤"""

    def setUp(self):
        super().setUp()
        self.post_url = reverse(
            'comments:postcomment', kwargs={'article_id': self.article.id})
        self.login_user()

    def test_clean_comment_still_passes(self):
        """回归保护：正常评论仍走原流程（302 重定向 + 入库）"""
        response = self.client.post(self.post_url, {'body': '写得不错，学到了'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Comment.objects.filter(article=self.article, body='写得不错，学到了').exists())

    def test_sensitive_comment_rejected(self):
        """含敏感词的评论：拒绝入库并回显错误提示"""
        response = self.client.post(self.post_url, {'body': '专业赌博网站推荐'})
        # DB 命中后走 form_invalid，重渲染文章详情页（200）而非重定向

        self.assertEqual(response.status_code, 200)
        # DB 错误提示中包含命中词

        self.assertContains(response, '敏感词')
        self.assertContains(response, '赌博')
        # DB 数据库不产生任何评论记录

        self.assertFalse(Comment.objects.filter(article=self.article).exists())

    def test_multiple_hits_all_reported(self):
        """命中多个敏感词：错误提示列出全部命中词"""
        response = self.client.post(
            self.post_url, {'body': '赌博加刷单一条龙'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '赌博')
        self.assertContains(response, '刷单')
        self.assertFalse(Comment.objects.filter(article=self.article).exists())

    def test_sensitive_reply_rejected(self):
        """楼中楼回复含敏感词：同样被拦截，不产生子评论"""
        parent = self.create_comment(article=self.article, body='父评论')
        parent.is_enable = True
        parent.save()

        before = Comment.objects.count()
        response = self.client.post(self.post_url, {
            'body': '回复内容带博彩链接',
            'parent_comment_id': parent.id,
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Comment.objects.count(), before)

    def test_filter_runs_before_moderation(self):
        """过滤先于审核：需审核模式下命中词依旧被拒绝（而非进入待审）"""
        self.blog_settings.comment_need_review = True
        self.blog_settings.save()

        response = self.client.post(self.post_url, {'body': '代开发票联系我'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Comment.objects.filter(article=self.article).exists())
