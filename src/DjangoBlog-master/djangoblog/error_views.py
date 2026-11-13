#!/usr/bin/env python
# encoding: utf-8

"""
Django Blog 统一错误处理视图
提供统一的错误页面渲染，减少重复代码
"""
# ZZC: 本模块把 400、403、404、500 等错误集中渲染为统一模板。

import logging
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)


# ZZC: 通用错误渲染函数会在存在异常时记录堆栈，并用状态码设置正确响应。
def render_error_page(request, status_code, message, exception=None):
    """
    通用错误页面渲染函数

    统一处理各种 HTTP 错误，提供一致的错误页面展示

    Args:
        request: HTTP 请求对象
        status_code: HTTP 状态码（404, 403, 500等）
        message: 错误消息（支持国际化）
        exception: 异常对象（可选），会被记录到日志

    Returns:
        HttpResponse: 渲染后的错误页面

    Usage:
        def my_error_handler(request, exception):
            return render_error_page(request, 404, "Page not found", exception)
    """
    # ZZC: 记录异常堆栈并把请求与状态码放入日志上下文，便于定位问题来源。
    if exception:
        logger.error(
            f'HTTP {status_code} Error: {exception}',
            exc_info=True,
            extra={
                'request': request,
                'status_code': status_code
            }
        )

    return render(
        request,
        'blog/error_page.html',
        {
            'message': message,
            'statuscode': str(status_code)
        },
        status=status_code
    )


# ZZC: 404 处理器复用通用渲染逻辑，并传入国际化后的提示信息。
def page_not_found_view(request, exception, template_name='blog/error_page.html'):
    """
    404 错误页面处理器

    当用户访问不存在的页面时显示

    Args:
        request: HTTP 请求对象
        exception: 异常对象
        template_name: 模板名称（保留参数以兼容 Django 标准）

    Returns:
        HttpResponse: 404 错误页面
    """
    return render_error_page(
        request,
        404,
        _('Sorry, the page you requested is not found, please click the home page to see other?'),
        exception
    )


# ZZC: 500 处理器不向用户暴露内部异常，只记录日志并展示通用提示。
def server_error_view(request, template_name='blog/error_page.html'):
    """
    500 错误页面处理器

    当服务器内部错误时显示

    Args:
        request: HTTP 请求对象
        template_name: 模板名称（保留参数以兼容 Django 标准）

    Returns:
        HttpResponse: 500 错误页面
    """
    return render_error_page(
        request,
        500,
        _('Sorry, the server is busy, please click the home page to see other?')
    )


# ZZC: 403 处理器用于当前用户缺乏页面访问权限的场景。
def permission_denied_view(request, exception, template_name='blog/error_page.html'):
    """
    403 错误页面处理器

    当用户无权限访问时显示

    Args:
        request: HTTP 请求对象
        exception: 异常对象
        template_name: 模板名称（保留参数以兼容 Django 标准）

    Returns:
        HttpResponse: 403 错误页面
    """
    return render_error_page(
        request,
        403,
        _('Sorry, you do not have permission to access this page?'),
        exception
    )


# ZZC: 400 处理器用于请求参数或请求格式非法的场景。
def bad_request_view(request, exception, template_name='blog/error_page.html'):
    """
    400 错误页面处理器

    当请求格式错误时显示

    Args:
        request: HTTP 请求对象
        exception: 异常对象
        template_name: 模板名称（保留参数以兼容 Django 标准）

    Returns:
        HttpResponse: 400 错误页面
    """
    return render_error_page(
        request,
        400,
        _('Sorry, the request was invalid?'),
        exception
    )
