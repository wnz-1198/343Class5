"""djangoblog URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.10/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
# ZZC: 本模块集中注册项目级 URL，并把各业务 App 的路由挂载到同一入口。
from django.conf import settings
from django.conf.urls.i18n import i18n_patterns
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.urls import re_path
from haystack.views import search_view_factory
from django.http import JsonResponse
import time

from blog.views import EsSearchView
from djangoblog.admin_site import admin_site
from djangoblog.elasticsearch_backend import ElasticSearchModelSearchForm
from djangoblog.feeds import DjangoBlogFeed
from djangoblog.sitemap import ArticleSiteMap, CategorySiteMap, StaticViewSitemap, TagSiteMap, UserSiteMap

# ZZC: 站点地图需同时覆盖文章、分类、标签、作者和静态首页，便于搜索引擎发现内容。
sitemaps = {

    'blog': ArticleSiteMap,
    'Category': CategorySiteMap,
    'Tag': TagSiteMap,
    'User': UserSiteMap,
    'static': StaticViewSitemap
}

# ZZC: 指定 Django 在常见 HTTP 错误发生时调用的统一处理视图。
handler404 = 'blog.views.page_not_found_view'
handler500 = 'blog.views.server_error_view'
handle403 = 'blog.views.permission_denied_view'


# ZZC: 健康检查只返回服务状态和服务器时间，供部署平台判断应用是否存活。
def health_check(request):
    """
    健康检查接口
    简单返回服务健康状态
    """
    return JsonResponse({
        'status': 'healthy',
        'timestamp': time.time()
    })

# ZZC: 不参与国际化前缀的接口入口，适合健康检查等基础设施路由。
urlpatterns = [
    path('i18n/', include('django.conf.urls.i18n')),
    path('health/', health_check, name='health_check'),
]
# ZZC: 业务页面统一放入 i18n_patterns，使后台、博客和评论等 URL 支持语言前缀。
urlpatterns += i18n_patterns(
    re_path(r'^admin/', admin_site.urls),
    re_path(r'', include('blog.urls', namespace='blog')),
    re_path(r'mdeditor/', include('mdeditor.urls')),
    re_path(r'', include('comments.urls', namespace='comment')),
    re_path(r'', include('accounts.urls', namespace='account')),
    re_path(r'', include('oauth.urls', namespace='oauth')),
    re_path(r'^sitemap\.xml$', sitemap, {'sitemaps': sitemaps},
            name='django.contrib.sitemaps.views.sitemap'),
    re_path(r'^feed/$', DjangoBlogFeed()),
    re_path(r'^rss/$', DjangoBlogFeed()),
    re_path('^search', search_view_factory(view_class=EsSearchView, form_class=ElasticSearchModelSearchForm),
            name='search'),
    re_path(r'', include('servermanager.urls', namespace='servermanager'))
    , prefix_default_language=False) + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
# ZZC: 开发环境额外暴露上传文件目录；生产环境应由 Web 服务器或对象存储处理媒体文件。
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
