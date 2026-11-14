#SJL: OAuth 模板标签，只向前端暴露平台名称和登录 URL，不暴露 AppSecret。
from django import template
from django.urls import reverse

from oauth.oauthmanager import get_oauth_apps

register = template.Library()


@register.inclusion_tag('oauth/oauth_applications.html')
def load_oauth_applications(request):
    #SJL: 保留当前页面路径作为 next_url，登录后由服务端再次校验是否允许跳转。
    applications = get_oauth_apps()
    if applications:
        baseurl = reverse('oauth:oauthlogin')
        path = request.get_full_path()

        apps = list(map(lambda x: (x.ICON_NAME, '{baseurl}?type={type}&next_url={next}'.format(
            baseurl=baseurl, type=x.ICON_NAME, next=path)), applications))
    else:
        apps = []
    return {
        'apps': apps
    }
