# djangoblog 模块质量分析记录

> 说明：本文是质量分析工作底稿，最终提交时仍需按课程提供的质量分析报告模板整理。

## 1. 分析范围

- App：`djangoblog`
- 分析对象：`src/DjangoBlog-master/djangoblog/` 下的 Python 源码
- 分析工具：SonarQube for IDE 6.3.0、Python `compileall`、Python AST 静态检查、人工代码审查
- 分析分支：`zzc_branch`

SonarQube for IDE 的本地模式每次扫描当前打开文件。本次使用它完成了 `settings.py` 和 `utils.py` 的修改前后对比，其余文件使用本地静态检查和人工审查补足。

## 2. 修改前基线

### `settings.py`

SonarQube 共报告 3 个问题：

1. 第 37 行存在被注释掉的旧代码。
2. 第 185 行附近存在被注释掉的配置代码。
3. 百度主动推送地址使用不安全的 HTTP 协议。

### `utils.py`

SonarQube 共报告 6 个问题：

1. 使用裸 `except`，没有指定异常类型。
2. 局部变量 `toc` 未被使用。
3. 验证码使用普通伪随机数生成器。
4. 捕获异常后使用 `logger.error`，没有记录完整堆栈。
5. 静态资源回退地址使用 HTTP。
6. `style` 属性清理正则存在进一步简化提示。

### 人工审查发现

1. `SpiderNotify.notify()` 把单个 URL 字符串直接传给按“列表”处理的 `baidu_notify()`，会导致 URL 被逐字符拼接。
2. 百度通知请求没有设置超时，外部接口异常时可能长时间占用请求。
3. 评论邮件使用低层 `_thread.start_new_thread()`，线程缺少统一的生命周期管理。
4. 列表缓存把空列表当作未命中，可能造成重复查询。
5. Whoosh 时间正则使用普通字符串，产生 `\d` 无效转义警告。

## 3. 已完成的修改

| 文件 | 修改内容 | 目的 |
|---|---|---|
| `settings.py` | 删除旧调试代码注释，百度通知地址改为 HTTPS | 减少代码异味和不安全协议 |
| `utils.py` | 明确异常类型、删除未使用变量、验证码改用 `secrets.choice`、异常改用 `logger.exception`、静态资源地址改为 HTTPS、简化正则 | 提升安全性和可维护性 |
| `spider_notify.py` | 单个 URL 包装为列表；请求增加 5 秒超时 | 修正参数类型，避免阻塞 |
| `mixins.py` | 缓存命中判断由真值判断改为 `is not None` | 正确缓存空列表结果 |
| `blog_signals.py` | 使用带名称的守护线程替代低层 `_thread` | 改善线程生命周期和可维护性 |
| `whoosh_cn_backend.py` | 时间正则改用原始字符串 | 消除无效转义警告 |

## 4. 保留项与理由

1. `settings.py` 中的 Elasticsearch 配置示例保留。该项被 SonarQube 识别为注释代码，但实际是开发环境配置说明，删除会降低文档价值。
2. `utils.py` 中清理空 `style` 属性的正则保留。进一步改写可能改变 HTML 清理行为，风险高于当前性能收益。
3. `settings.py` 中 `localhost`、示例域名等 HTTP 地址属于开发配置，不纳入生产安全问题。

## 5. 修改后验证

- `python -m compileall -q src/DjangoBlog-master/djangoblog`：通过。
- `python -W error::SyntaxWarning -m py_compile src/DjangoBlog-master/djangoblog/whoosh_cn_backend.py`：通过。
- `git diff --check`：通过。
- 针对裸异常、无超时 HTTP 请求和低层线程的定向静态检查：0 项。
- SonarQube 复查：
  - `settings.py`：3 项降至 1 项保留项。
  - `utils.py`：6 项降至 1 项保留项。

VSCode 中的 Pylance “无法解析导入”提示主要由当前选择的 Python 解释器未安装项目依赖导致，不属于 SonarQube 代码缺陷。启动项目测试前仍需配置正确的虚拟环境并安装 `requirements.txt`。

## 6. 后续优化建议

1. 将评论邮件从进程内线程迁移到 Celery 等任务队列，提高可靠性和可观测性。
2. 将可选的开发配置示例迁移到 `docs`，避免 SonarQube 将配置示例识别为注释代码。
3. 补充验证码生成、缓存命中、搜索引擎通知和错误页的自动化测试。
4. 为生产环境使用独立密钥，并将 `DEBUG`、`ALLOWED_HOSTS` 和数据库凭据全部通过环境变量配置。
5. 完成其余 App 的精读后，在小组层面统一代码规范和缺陷记录格式。
