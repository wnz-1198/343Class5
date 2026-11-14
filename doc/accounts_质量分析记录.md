# accounts 模块质量分析记录

> 分析人：吴念祖（组长，#WNZ）
> 说明：本文是质量分析工作底稿，最终提交时仍需按课程提供的质量分析报告模板整理。

## 1. 分析范围

- App：`accounts`
- 分析对象：`src/DjangoBlog-master/accounts/` 下的 Python 源码（models / forms / views / urls / admin / utils / user_login_backend / apps，共 8 个文件）
- 分析工具：Python `py_compile` 语法检查、Django 5.2 `manage.py test accounts`（52 个用例）、对照 SonarQube 规则集的人工代码审查
- 分析分支：`WNZ_branch`

## 2. 模块职责概述

accounts 应用承担站点的**用户账户体系**：

| 文件 | 职责 |
|---|---|
| `models.py` | `BlogUser` 继承 `AbstractUser`，扩展 `nickname`、`creation_time`、`last_modify_time`、`source` 四个业务字段 |
| `user_login_backend.py` | 自定义认证后端 `EmailOrUsernameModelBackend`，支持用户名/邮箱双模式登录 |
| `forms.py` | `LoginForm`（样式包装）、`RegisterForm`（邮箱唯一性校验）、`ForgetPasswordForm`（新密码+邮箱+验证码三合一校验）、`ForgetPasswordCodeForm` |
| `views.py` | 注册（邮箱验证激活）、登录/登出（含"记住我" TTL）、验证结果页、找回密码视图、发码接口 |
| `utils.py` | 找回密码验证码的缓存存取（TTL 5 分钟）与发码邮件 |
| `admin.py` | BlogUser 后台管理（创建表单密码哈希落库、列表展示与搜索） |
| `urls.py` | 6 条路由，命名空间 `accounts` |
| `apps.py` | 应用配置 |

## 3. 修改前基线（人工审查发现）

### 安全类

1. **验证码可重放（严重）**：`utils.verify()` 校验通过后不删除缓存中的验证码，5 分钟窗口内可凭同一验证码反复重置密码。
2. **验证码比较非常量时间**：`utils.verify()` 使用 `!=` 逐字符比较，理论上存在时序侧信道（生成端已由朱梓诚改用 `secrets.choice`，比较端未配套）。
3. **注册验证链接使用 HTTP**：`views.RegisterView` 拼接的邮箱激活链接为 `http://`，激活 URL 与签名参数明文传输（djangoblog 模块已统一 HTTPS，此处遗漏）。
4. **发码接口可向任意地址滥发邮件**：`ForgetPasswordEmailCode.post` 不校验邮箱是否注册，可被用作邮件轰炸向量；同时响应区分"注册/未注册"会泄露注册状态（实际实现统一返回 `ok`，泄露问题不存在，滥发问题存在）。
5. **认证后端空凭据未防御**：`EmailOrUsernameModelBackend.authenticate` 在 `username=None` 时执行 `'@' in None` 抛 `TypeError`。

### 健壮性类

6. **同邮箱多账号导致 500（严重）**：`ForgetPasswordView.form_valid` 用 `.filter(email=...).get()` 取用户，但 `email` 字段在数据库层无唯一约束（OAuth 绑定、后台创建都可能产生重复邮箱），多账号时抛 `MultipleObjectsReturned` 直接 500。
7. **`BlogUser.__str__` 可能返回空串**：`email` 允许 `blank=True`，空邮箱用户的后台/日志显示为空。

### 可维护性类（记录未修改）

8. `RegisterView.form_valid` 中 `if form.is_valid()` 冗余——`SecureFormView`（FormView 体系）只在表单有效时调用 `form_valid`，else 分支不可达；`form.save(False)` / `user.save(True)` 使用位置布尔参数，语义不清（应为 `commit=False`）。
9. `account_result` 视图用 `type` 作局部变量名，遮蔽 Python 内建类型。
10. `urls.py` 对不含正则语义的路由使用 `re_path`，应统一为 `path`；`r'account/result.html'` 的 `r` 前缀无意义。
11. `urls.py` 中 `kwargs={'authentication_form': LoginForm}` 与视图类自身的 `form_class` 重复声明。
12. `ForgetPasswordForm.clean_email` 通过报错暴露"邮箱是否注册过"，上游代码已留 todo 自注；为保持与原站行为一致（提示用户邮箱不存在便于找回），本次不修改。
13. `LoginView.form_valid` 里用 `self.request.POST` 重新实例化并校验一遍 `AuthenticationForm`，与 `form_valid(form)` 传入的表单重复，属冗余逻辑。
14. `logged_user` cookie 设 `httponly=False`（供前端 JS 判断登录态），配合 `samesite='Lax'`，风险可接受，但需知悉其非安全边界。

## 4. 已完成的修改

| 文件 | 修改内容 | 目的 |
|---|---|---|
| `utils.py` | `verify()` 改用 `secrets.compare_digest` 恒定时间比较；验证通过后 `cache.delete(email)` 作废验证码 | 防时序侧信道、防验证码重放 |
| `views.py` | 注册验证链接 `http://` → `https://` | 激活链接与签名不再明文传输 |
| `views.py` | 找回密码取用户改 `.first()` 并处理 `None` | 消除同邮箱多账号 500 |
| `views.py` | 发码接口先校验邮箱已注册，未注册直接返回 `ok` 不发码 | 防邮件滥发，且不泄露注册状态 |
| `user_login_backend.py` | `authenticate` 增加 `username/password` 空值防御 | 空凭据返回 None 而非抛异常 |
| `models.py` | `__str__` 改为 `self.email or self.username` | 空邮箱用户不再显示为空串 |

以上修改均以 `#WNZ:` 署名注释标注；同时按课程要求为全部 8 个文件补充了模块级注释、关键方法与核心代码行注释。

## 5. 保留项与理由

1. `clean_email` 暴露邮箱存在性：保留上游行为，避免改变用户交互预期（第 3 节第 12 条）。
2. `re_path`、冗余 `form.is_valid()`、重复表单实例化等可维护性问题：不影响正确性与安全，留给编码规范落地时统一处理，避免本次改动面过大。
3. `logged_user` 非httponly cookie：前端登录态标记的既有设计，保留。

## 6. 修改后验证

- `python -m py_compile accounts/*.py`：8 个文件全部通过。
- `DJANGO_USE_SQLITE=True python manage.py test accounts --parallel 1`：**52 个用例全部通过（OK）**，含注册-验证-登录、找回密码成功/失败、验证码错误等既有回归路径。

## 7. 后续优化建议

1. 给 `BlogUser.email` 增加显式唯一约束（需处理存量重复数据），从根上消除同邮箱多账号问题。
2. 发码接口增加频率限制（如同一邮箱 60 秒内仅允许一次），进一步收敛邮件轰炸面。
3. 注册激活与找回密码的验证码/签名机制可统一收敛到一个独立模块，避免 `sha256(sha256(SECRET_KEY+id))` 与缓存验证码两套方案并存。
4. 将第 3 节第 8-13 条可维护性项纳入编码规范落地清单，统一整改。
5. `test_user_business_logic.py` 覆盖了模型与认证后端，但 `views.py` 的"记住我" TTL、登出清 cookie 等路径尚无自动化用例，建议补充。
