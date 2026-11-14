# ZZC: 本模块用 Django Signal 处理邮件、OAuth 头像和模型保存后的缓存失效。
import threading
import logging

import django.dispatch
from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.core.mail import EmailMultiAlternatives
from django.db.models.signals import post_save
from django.dispatch import receiver

from comments.models import Comment
from comments.utils import send_comment_email
from djangoblog.spider_notify import SpiderNotify
from djangoblog.utils import cache, expire_view_cache, delete_sidebar_cache, delete_view_cache
from djangoblog.utils import get_current_site
from oauth.models import OAuthUser

logger = logging.getLogger(__name__)

# ZZC: 自定义登录信号只传递 OAuth 用户主键，避免在信号层暴露完整用户对象。
oauth_user_login_signal = django.dispatch.Signal(['id'])
send_email_signal = django.dispatch.Signal(
    ['emailto', 'title', 'content'])


# ZZC: 邮件信号处理器发送 HTML 邮件，并把成功或失败结果写入邮件日志。
@receiver(send_email_signal)
def send_email_signal_handler(sender, **kwargs):
    emailto = kwargs['emailto']
    title = kwargs['title']
    content = kwargs['content']

    msg = EmailMultiAlternatives(
        title,
        content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=emailto)
    msg.content_subtype = "html"

    from servermanager.models import EmailSendLog
    log = EmailSendLog()
    log.title = title
    log.content = content
    log.emailto = ','.join(emailto)

    try:
        result = msg.send()
        log.send_result = result > 0
    except Exception as e:
        logger.error(f"失败邮箱号: {emailto}, {e}")
        log.send_result = False
    log.save()


# ZZC: OAuth 登录后把外部头像转存到本地，并清除可能过期的侧边栏缓存。
@receiver(oauth_user_login_signal)
def oauth_user_login_signal_handler(sender, **kwargs):
    id = kwargs['id']
    oauthuser = OAuthUser.objects.get(id=id)
    site = get_current_site().domain
    if oauthuser.picture and not oauthuser.picture.find(site) >= 0:
        from djangoblog.utils import save_user_avatar
        oauthuser.picture = save_user_avatar(oauthuser.picture)
        oauthuser.save()

    delete_sidebar_cache()


# ZZC: 模型保存后通知搜索引擎，并根据对象类型精准清理受影响的页面缓存。
@receiver(post_save)
def model_post_save_callback(
        sender,
        instance,
        created,
        raw,
        using,
        update_fields,
        **kwargs):
    # ZZC: 后台日志不属于博客内容，无需触发搜索通知或页面缓存清理。
    if isinstance(instance, LogEntry):
        return

    # ZZC: 浏览量更新频繁且不影响主要页面内容，跳过整条信号处理链。
    is_update_views = update_fields == {'views'}
    if is_update_views:
        return  # 浏览量更新不需要清理缓存

    # ZZC: 具备 get_full_url() 的内容对象才适合主动提交给搜索引擎。
    if 'get_full_url' in dir(instance):
        if not settings.TESTING:
            try:
                notify_url = instance.get_full_url()
                SpiderNotify.baidu_notify([notify_url])
            except Exception as ex:
                logger.error("notify sipder", ex)

    # ZZC: 已启用评论会改变文章详情、评论列表和侧边栏，因此需要联动清理缓存。
    if isinstance(instance, Comment):
        if instance.is_enable:
            path = instance.article.get_absolute_url()
            site = get_current_site().domain
            if site.find(':') > 0:
                site = site[0:site.find(':')]

            expire_view_cache(
                path,
                servername=site,
                serverport=80,
                key_prefix='blogdetail')

            # 清理评论相关缓存
            comment_cache_key = 'article_comments_{id}'.format(
                id=instance.article.id)
            cache.delete(comment_cache_key)
            delete_view_cache('article_comments', [str(instance.article.pk)])
            delete_sidebar_cache()
            cache.delete('seo_processor')

            # ZZC: 邮件发送放入守护线程，避免 SMTP 延迟阻塞评论保存请求。
            threading.Thread(
                target=send_comment_email,
                args=(instance,),
                daemon=True,
            ).start()

    # ZZC: 文章、分类和标签分别影响不同页面，使用最小范围删除以保留其他缓存。
    elif 'get_full_url' in dir(instance):
        from blog.models import Article, Category, Tag

        if isinstance(instance, Article):
            # 清理文章列表首页缓存
            cache.delete('index_1')

            # 清理文章详情缓存
            article_cache_key = f'article_comments_{instance.id}'
            cache.delete(article_cache_key)

            # 清理分类相关缓存
            if instance.category:
                category_name = instance.category.name
                cache.delete(f'category_list_{category_name}_1')

            # 清理标签相关缓存
            try:
                for tag in instance.tags.all():
                    cache.delete(f'tag_{tag.name}_1')
            except Exception:
                pass  # 可能在创建时tags还未关联

            # 清理作者相关缓存
            if instance.author:
                from uuslug import slugify
                author_slug = slugify(instance.author.username)
                cache.delete(f'author_{author_slug}_1')

            # 清理归档缓存
            cache.delete('archives')

            # 清理侧边栏和上下文处理器缓存
            delete_sidebar_cache()
            cache.delete('seo_processor')

        elif isinstance(instance, Category):
            # 清理分类相关缓存
            cache.delete(f'category_list_{instance.name}_1')
            delete_sidebar_cache()
            cache.delete('seo_processor')

        elif isinstance(instance, Tag):
            # 清理标签相关缓存
            cache.delete(f'tag_{instance.name}_1')
            delete_sidebar_cache()

        # 其他模型的缓存清理
        else:
            # 对于其他有get_full_url的模型，清理基础缓存
            delete_sidebar_cache()
            cache.delete('seo_processor')


# ZZC: 用户登录或登出会改变头部信息，因此同步清除侧边栏缓存。
@receiver(user_logged_in)
@receiver(user_logged_out)
def user_auth_callback(sender, request, user, **kwargs):
    if user and user.username:
        logger.info(user)
        delete_sidebar_cache()
        # cache.clear()
