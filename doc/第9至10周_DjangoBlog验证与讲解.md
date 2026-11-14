# DjangoBlog 第 9–10 周验证与讲解

第 21 组。朱梓诚、孙金龙、杜彬、吴念祖、徐力艇。本文记录徐力艇负责的维护与验证。

| 应用 | 通过 | 检查内容 |
| --- | ---: | --- |
| blog | 6 | 草稿可见性、清理缓存的权限与请求方法、浏览量 |
| accounts | 8 | 注册、账户验证、登录和重置密码 |
| comments | 1 | 发表、审核和回复评论 |
| oauth | 9 | 配置和使用模拟响应验证各登录流程 |
| servermanager | 1 | 机器人搜索、分类和近期文章 |
| djangoblog | 1 | Markdown 渲染和工具方法 |
| 合计 | 26 | Django 系统检查没有发现问题 |

测试使用 Django 5.2.17、独立的 SQLite 文件、内存邮件和缓存，外部 OAuth 调用由测试模拟。Django 测试的搜索配置使用 Haystack SimpleEngine，未验证外部搜索服务或线上部署。前端使用项目锁定依赖构建成功。

在本地复现实测时，同一草稿的公开链接返回 HTTP 404，改为已发布后返回 200。普通用户 POST 返回 403，管理员 GET 返回 405，管理员缺少 CSRF 校验信息的 POST 返回 403。这三次均保留原缓存项。管理员带有效 CSRF 信息的 POST 返回 200 并清除缓存。分别从同一行读取两个文章对象并各记一次浏览，最终读数从 1 增至 3。

| 修改 | 源码索引 | 原因 |
| --- | --- | --- |
| 限制公开详情 | [blog/views.py](../src/DjangoBlog-master/blog/views.py) 中的 ArticleDetailView.get_queryset | 让详情查询与列表的发布可见性一致 |
| 限制清缓存 | [blog/views.py](../src/DjangoBlog-master/blog/views.py) 中的 clean_cache_view | 清缓存属于写操作，验证请求方法、来源和管理员身份 |
| 防止丢计数 | [blog/models.py](../src/DjangoBlog-master/blog/models.py) 中的 Article.viewed | 在数据库使用当前值加一 |
| 恢复注册用例 | [accounts/tests.py](../src/DjangoBlog-master/accounts/tests.py) 中的 test_validate_register | 修正 Python 3.12 已移除的断言别名及旧路由命名空间 |

演示 MP4 使用本地 Django 响应截图和测试数据说明结果，开头显示组号和五名组员。现场讲解可按三个验证段落复述问题、修改位置和结果，再说明为什么用已读取两次的对象模拟旧值写回冲突。
