# ZZC: 本模块测试 djangoblog 的工具函数，覆盖签名、Markdown 和 URL 参数转换。
from django.test import TestCase

from djangoblog.utils import *


# ZZC: 工具测试类不依赖额外测试数据，直接验证公开函数的输出。
class DjangoBlogTest(TestCase):
    # ZZC: 当前没有公共初始化数据，保留 setUp 以匹配测试类结构。
    def setUp(self):
        pass

    # ZZC: 验证摘要、Markdown 渲染和查询字符串转换均能返回有效结果。
    def test_utils(self):
        md5 = get_sha256('test')
        self.assertIsNotNone(md5)
        c = CommonMarkdown.get_markdown('''
        # Title1

        ```python
        import os
        ```

        [url](https://www.lylinux.net/)

        [ddd](http://www.baidu.com)


        ''')
        self.assertIsNotNone(c)
        d = {
            'd': 'key1',
            'd2': 'key2'
        }
        data = parse_dict_to_url(d)
        self.assertIsNotNone(data)
