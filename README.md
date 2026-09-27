# 🧲 RSS种子站点（Cloudflare Workers 版）

字幕组分流用的轻量种子站：用户注册、角色权限、种子发布、RSS 自动下载、API。
跑在 **Cloudflare Python Workers + D1 + R2** 上，不用服务器。

## 为什么不会把免费额度打爆

订阅端每分钟拉一次 RSS，一个订阅者一天就是 1440 次；Workers 免费版每天只有 10 万次请求，70 个订阅者就用光了。

所以 RSS 和种子文件**根本不经过 Worker**：

```
订阅端 ──每分钟──▶ files.你的域名/rss.xml       R2 自定义域名 + CDN 缓存，不计 Worker 请求
下载   ──────────▶ files.你的域名/t/<id>.torrent  同上

发布员上传 ──▶ Worker ─┬─ 种子写入 R2
                       ├─ 元数据写入 D1
                       ├─ 重建 rss.xml 写入 R2
                       └─ 调 Cloudflare API 清掉 rss.xml 的 CDN 缓存 → 新种子立即可见
```

- Worker 只处理网页、登录、上传、API，一天几百次。
- CDN 命中不消耗 R2 读操作；未命中才回源（R2 免费 1000 万次读/月）。
- `rss.xml` 设 `max-age=60`。即使没配置清缓存，最多也只延迟 1 分钟。

## 部署（Cloudflare 网页后台）

仓库里的 `wrangler.jsonc` 不含任何 ID、域名或密钥。D1 和 R2 在首次部署时自动创建并绑定，**不要在后台手动添加绑定**，否则下次部署会被覆盖。

### 1. R2 桶和公开域名

R2 → 创建存储桶 `sgds` → 设置 → 自定义域 → 连接一个子域名，例如 `files.你的域名`。

不要用 `r2.dev`，官方说明它限速、仅供开发。

### 2. 导入仓库

Workers 和 Pages → 创建 → 导入存储库 → 选这个仓库：

| 项 | 填写 |
|---|---|
| 项目名称 | `subtitle-group-diversion-site`（必须和 wrangler.jsonc 的 `name` 一致） |
| 构建命令 | 留空 |
| 部署命令 | `npm ci && env -u UV_SYSTEM_PYTHON uv run pywrangler deploy` |

> 构建镜像自带 uv。`env -u UV_SYSTEM_PYTHON` 不能省：它会让 pywrangler 把包装进构建机的系统 Python（3.12），而不是 Workers 的 pyodide 环境，报错 `incompatible with the pylock.toml's Python requirement`。

首次部署会自动创建 D1 数据库 `sgds`，并绑定 `DB`、`BUCKET`。

### 3. 变量和机密

Worker → 设置 → **Runtime variables and secrets（运行时变量和机密）**。注意不是"构建"里的变量和机密，那些只在构建时生效，运行时读不到：

| 名称 | 类型 | 必填 | 值 |
|---|---|---|---|
| `PUBLIC_URL` | 文本 | ✅ | 第 1 步的域名，如 `https://files.你的域名` |
| `SECRET_KEY` | 密钥 | ✅ | 随机长字符串，用于签名登录 cookie |
| `ADMIN_PASSWORD` | 密钥 | ✅ | admin 的密码；改这个值就是改密码 |
| `SITE_NAME` | 文本 | | 站点名，默认"RSS种子站点" |
| `CF_API_TOKEN` | 密钥 | | 权限选 Zone → Cache Purge；配了才会发布后立刻清 RSS 缓存 |
| `CF_ZONE_ID` | 文本 | | `PUBLIC_URL` 所在域名的 Zone ID（域名概览页右下角） |

缺少必填项时，站点会返回 500，并提示缺的是哪一项。`wrangler.jsonc` 里设了 `keep_vars`，后续部署不会覆盖这些变量。

### 4. 建表

D1 → `sgds` → 控制台：把 [schema.sql](schema.sql) 的内容粘进去执行。这一步会同时创建默认管理员 `admin`。

### 5. 缓存规则（必做）

域名 → 缓存 → Cache Rules → 新建：

- 条件：`主机名 等于 files.你的域名`
- 动作：`符合缓存条件`
- 边缘 TTL：`如果存在则使用 Cache-Control 标头`

Cloudflare 默认不缓存 `.xml` / `.torrent`，不加这条规则，每次订阅轮询都会回源 R2。

### 命令行部署（可选）

```bash
npm install && npx wrangler login
npx wrangler secret put SECRET_KEY    # 其余变量同上表
npm run deploy
```

## 从旧版（Flask）迁移数据

需要旧站的 `site.db` 和 `uploads/` 目录。先在本地 `npx wrangler login`，然后：

```bash
python scripts/migrate.py 旧的site.db 旧的uploads目录   # 种子直接传到 R2，同时生成 migrate.sql
npx wrangler d1 execute DB --remote --file migrate.sql  # 报 missing a database_id 就把内容粘到 D1 控制台执行
```

最后在管理后台点「重建 RSS」。

- **种子**：按新格式上传到 R2，文件缺失的会跳过并提示。
- **API Key**：原样保留，发布脚本不用改。
- **用户**：旧密码哈希无法迁移，每人分配一个临时密码，写在 `migrate-passwords.txt` 里，转交后删除。admin 仍然用 `ADMIN_PASSWORD` 登录。
- **时间**：旧 Docker 部署存的是 UTC，脚本会转成北京时间。旧站如果是直接跑在北京时间的服务器上，加 `--tz +08:00`。

## 本地开发

```bash
cp .dev.vars.example .dev.vars      # 冒烟测试要求 ADMIN_PASSWORD=adminpw、PUBLIC_URL=https://files.example.com
npx wrangler d1 execute DB --local --file schema.sql
npm run dev                          # http://127.0.0.1:8787
python scripts/smoke_test.py         # 端到端冒烟测试：登录/上传/RSS/API/权限/删除
```

### Windows 注意

- 项目**不在 C 盘**时，pyodide 只能访问项目所在的盘，需要把 uv 的 Python 和缓存也放到同一个盘：
  ```powershell
  $env:UV_PYTHON_INSTALL_DIR = "$PWD\.uv-python"; $env:UV_CACHE_DIR = "$PWD\.uv-cache"; $env:UV_LINK_MODE = "copy"
  ```
- `pywrangler` 用系统编码（GBK）读 `wrangler.jsonc`。里面写中文（比如 `SITE_NAME`）时，要先设 `$env:PYTHONUTF8 = "1"`。

## 角色

| 角色 | 权限 |
|------|------|
| admin | 管理用户角色、删除种子、发布 |
| publisher | 发布种子 |
| user | 浏览、下载、管理自己的 API Key |

API 文档见站内 `/api/docs` 或 [docs/API.md](docs/API.md)。

## 已知限制

- Python Workers 目前还是 **beta**（`create-cloudflare` 里标注为 `Python (beta)`）。
- 免费版每个请求只有 **10ms CPU**。普通页面没问题；注册和普通用户登录要做 PBKDF2（10 万次迭代），有可能超时。admin 登录直接比对 secret，不受影响。如果部署后注册或登录报 1102 错误，可以升级 Workers Paid（每月 5 美元，单请求 30 秒 CPU）。

## License

MIT
