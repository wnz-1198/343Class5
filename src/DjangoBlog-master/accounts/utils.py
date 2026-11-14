# WNZ: accounts.utils —— 找回密码验证码的存取工具模块。
# WNZ: 验证码以邮箱为键存入 Django 缓存，TTL 5 分钟；send_verify_email 负责发码邮件。
import typing
import secrets
from datetime import timedelta

from django.core.cache import cache
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from djangoblog.utils import send_email

_code_ttl = timedelta(minutes=5)


def send_verify_email(to_mail: str, code: str, subject: str = _("Verify Email")):
    """发送重设密码验证码
    Args:
        to_mail: 接受邮箱
        subject: 邮件主题
        code: 验证码
    """
    html_content = _(
        "You are resetting the password, the verification code is：%(code)s, valid within 5 minutes, please keep it "
        "properly") % {'code': code}
    send_email([to_mail], subject, html_content)


def verify(email: str, code: str) -> typing.Optional[str]:
    """验证code是否有效
    Args:
        email: 请求邮箱
        code: 验证码
    Return:
        如果有错误就返回错误str
    Node:
        这里的错误处理不太合理，应该采用raise抛出
        否测调用方也需要对error进行处理
    """
    cache_code = get_code(email)
    # WNZ: compare_digest 恒定时间比较，避免逐字符比对泄露时序信息。
    if cache_code is None or not secrets.compare_digest(cache_code, code):
        return gettext("Verification code error")
    # WNZ: 验证通过后立即作废验证码，防止 5 分钟窗口内重放同一验证码反复改密。
    cache.delete(email)
    return None


def set_code(email: str, code: str):
    """设置code"""
    cache.set(email, code, _code_ttl.seconds)


def get_code(email: str) -> typing.Optional[str]:
    """获取code"""
    return cache.get(email)
