# ZZC: 本模块封装搜索引擎通知请求，目前实现百度站长平台主动推送。
import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)


# ZZC: 静态工具类用于把新增或修改内容的 URL 主动通知搜索引擎。
class SpiderNotify():
    # ZZC: 将 URL 列表逐行拼接后发送；异常只记录日志，避免影响主业务流程。
    @staticmethod
    def baidu_notify(urls):
        try:
            data = '\n'.join(urls)
            result = requests.post(settings.BAIDU_NOTIFY_URL, data=data)
            logger.info(result.text)
        except Exception as e:
            logger.error(e)

    # ZZC: notify() 是统一调用入口，后续可在这里扩展其他搜索引擎。
    @staticmethod
    def notify(url):
        SpiderNotify.baidu_notify(url)
