# 账号与邮箱验证

登录注册是**真实实现**，不是前端演示：账号落 MySQL，验证码经 SMTP 真实发到邮箱，
密码以 bcrypt 哈希存储，会话用 JWT 令牌签发。

## 数据存放

| 数据 | 位置 | 说明 |
| --- | --- | --- |
| 账号 | MySQL `piao_invoice.users` | 邮箱唯一索引；密码 bcrypt 哈希；无明文口令 |
| 邮箱验证码 | MySQL `piao_invoice.email_codes` | 只存 HMAC 哈希；10 分钟过期；用后即焚；错 5 次锁定 |
| 发票台账等业务数据 | 本机 SQLite `runtime/invoices.sqlite3` | 保持单机离线可用，不随账号迁移 |

建表脚本：`scripts/auth_schema.sql`。测试使用独立库 `piao_invoice_test`，用完自动删除。

## 接口

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/auth/status` | 账号库与邮件服务可用性，供前端判断是否可登录 |
| POST | `/api/auth/check-email` | 注册前检查邮箱是否已注册，前端据此提前引导去登录 |
| POST | `/api/auth/send-code` | 生成验证码并真实发信；60 秒内不可重发 |
| POST | `/api/auth/register` | 校验验证码 → 建号 → 签发令牌 |
| POST | `/api/auth/login` | 校验口令 → 签发令牌；连续错 5 次锁定 15 分钟 |
| GET | `/api/auth/me` | 用令牌换取当前用户（前端启动时校验会话） |
| POST | `/api/auth/change-password` | 需提供当前密码 |

## 配置

全部通过项目根目录 `.env` 提供（已被 `.gitignore` 排除，切勿提交）。`start.py` 与
`backend/app/auth_config.py` 都会加载该文件。模板见 `.env.example`。

```ini
PIAO_MYSQL_HOST=127.0.0.1
PIAO_MYSQL_PORT=3306
PIAO_MYSQL_USER=root
PIAO_MYSQL_PASSWORD=你的数据库密码
PIAO_MYSQL_DATABASE=piao_invoice

PIAO_JWT_SECRET=至少 32 字节的随机字符串
PIAO_AUTH_REQUIRED=0        # 置 1 则业务接口也强制校验令牌

PIAO_SMTP_HOST=smtp.qq.com
PIAO_SMTP_PORT=465
PIAO_SMTP_SSL=1
PIAO_SMTP_USER=你的QQ邮箱地址@qq.com
PIAO_SMTP_PASSWORD=邮箱授权码
```

QQ 邮箱需在「设置 → 账户 → POP3/IMAP/SMTP」中开启 SMTP 服务并生成授权码；
163、企业邮箱同理，服务器地址与端口不同，填入 `.env` 即可。

## 安全说明

- 密码使用 bcrypt（自动加盐）哈希，数据库中不可逆；`PIAO_MYSQL_PASSWORD` 与
  `PIAO_SMTP_PASSWORD` 只存在于本机 `.env`，不写入代码与数据库。
- 验证码只存 HMAC-SHA256 哈希（混入服务端密钥），6 位纯数字不在库中留明文。
- 令牌为 HS256 JWT，默认 12 小时有效；前端在 401 时自动清除本地会话。
- `PIAO_AUTH_REQUIRED=0` 时业务接口不强制校验令牌，便于演示与既有接口测试；
  正式对外部署应置 1。

## 已知边界

- 登录失败计数保存在进程内存，多进程部署需改到 MySQL。
- 忘记密码走管理员重置，尚未实现自助找回。
- 账号未与发票数据绑定：不同账号在同一台机器上看到的是同一份本地台账。
  多账号隔离需要把 `invoices` 表加上 `owner_id` 并改写查询条件。

## 实测记录（2026-11-22，本机）

以真实 QQ 邮箱账号完成端到端验证：

| 环节 | 结果 |
| --- | --- |
| SMTP 认证 | `smtp.qq.com:465` SSL，`235 Authentication successful` |
| 邮件投递 | 收件箱经 IMAP 实测收到，主题 `【票序】您的注册验证码是 xxxxxx`，含 `text/plain` + `text/html` 两部分，HTML 邮件样式完整 |
| 注册 | 用邮件收到的 6 位验证码注册成功，返回 JWT 令牌 |
| 令牌换用户 | `GET /api/auth/me` 返回真实用户（id/email/name/company） |
| 登录 | 邮箱+密码登录成功；错误密码返回 401 |
| 无效令牌 | 返回 401 |
| 口令存储 | MySQL 中为 `$2b$12$` bcrypt 哈希，正解通过、错解拒绝 |
| 验证码存储 | 仅存 HMAC-SHA256 哈希；消费后 `consumed_at` 置位 |
| 重发限流 | 60 秒内重复发送返回 429 |
| 邮箱占用引导 | 输入已注册邮箱后，注册页立即显示"该邮箱已注册"并禁用"获取验证码"，提供"前往登录"链接 |
| 自动化测试 | 后端 52 项（含认证 10 项、邮件 5 项）全部通过 |

### 两个已修复的实现缺陷

1. **邮件模板 CSS 被占位符解析**：早期用 `str.format()` 渲染 HTML 模板，
   CSS 里的 `body{margin:0;...}` 被当成占位符，报 `KeyError: 'margin'`。
   改为 `@@CODE@@` 形式的占位符并用 `replace()` 渲染，回归测试见 `tests/test_mailer.py`。
2. **邮件主题 Header 不可下标**：`message['Subject'] = Header(...)` 后再取值会抛
   `'Header' object is not subscriptable`。直接赋 UTF-8 字符串，由 EmailMessage 负责编码。
