# ============================================================
# comments/utils.py —— 评论通知邮件
# ============================================================
# 触发方式：djangoblog/blog_signals.py 的 post_save 信号中，
# 评论启用(is_enable=True)后通过 _thread.start_new_thread 异步调用本函数。
# 邮件内容由 djangoblog/utils.send_email 实际投递，并写 EmailSendLog 日志。
# ============================================================
import logging

from django.utils.translation import gettext_lazy as _

from djangoblog.utils import get_current_site
from djangoblog.utils import send_email

logger = logging.getLogger(__name__)


def send_comment_email(comment):
    """
    发送评论通知邮件（两封）：
    ① 发给文章作者(comment.author.email)："你的文章收到了新评论"
    ② 若为楼中楼回复，再发给被回复者(parent_comment.author.email)："你的评论收到了回复"
    """
    site = get_current_site().domain
    subject = _('Thanks for your comment')
    article_url = f"https://{site}{comment.article.get_absolute_url()}"
    html_content = _("""<p>Thank you very much for your comments on this site</p>
                    You can visit <a href="%(article_url)s" rel="bookmark">%(article_title)s</a>
                    to review your comments,
                    Thank you again!
                    <br />
                    If the link above cannot be opened, please copy this link to your browser.
                    %(article_url)s""") % {'article_url': article_url, 'article_title': comment.article.title}
    # ① 通知文章作者
    tomail = comment.author.email
    send_email([tomail], subject, html_content)
    try:
        # ② 楼中楼回复：通知被回复的评论作者
        if comment.parent_comment:
            html_content = _("""Your comment on <a href="%(article_url)s" rel="bookmark">%(article_title)s</a><br/> has 
                   received a reply. <br/> %(comment_body)s
                    <br/>   
                    go check it out!
                     <br/>
                     If the link above cannot be opened, please copy this link to your browser.
                     %(article_url)s
                    """) % {'article_url': article_url, 'article_title': comment.article.title,
                            'comment_body': comment.parent_comment.body}
            tomail = comment.parent_comment.author.email
            send_email([tomail], subject, html_content)
    except Exception as e:
        # 注意：仅"回复通知"失败被捕获记录；文章作者邮件(①)若抛异常会直接上抛到线程
        logger.error(e)
