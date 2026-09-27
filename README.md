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

## 部署

需要：Node.js、[uv](https://docs.astral.sh/uv/)、一个托管在 Cloudflare 的域名。

```bash
npm install
npx wrangler login

# 1. 建库、建桶
npx wrangler d1 create sgds          # 记下输出的 database_id
npx wrangler r2 bucket create sgds

# 2. 配置
cp wrangler.example.jsonc wrangler.jsonc   # 填 database_id 和 PUBLIC_URL

# 3. 建表（同时创建默认管理员 admin）
npx wrangler d1 execute DB --remote --file schema.sql

# 4. 密钥
npx wrangler secret put SECRET_KEY        # 随机长字符串，用于签名登录 cookie
npx wrangler secret put ADMIN_PASSWORD    # admin 的密码；改这个 secret 就是改密码
npx wrangler secret put CF_API_TOKEN      # 可选，权限：Zone → Cache Purge
npx wrangler secret put CF_ZONE_ID        # 可选，PUBLIC_URL 所在域名的 Zone ID

# 5. 发布
npm run deploy
```

然后在 Cloudflare 后台完成两件事，**缺一不可**：

1. **R2 → sgds → Settings → Custom Domains**：绑定 `PUBLIC_URL` 里的域名（如 `files.你的域名`）。
   不要用 `r2.dev`，官方说明它限速、仅供开发。
2. **域名 → Caching → Cache Rules**：新建规则，条件 `Hostname equals files.你的域名`，动作 `Eligible for cache`，Edge TTL 选 `Use cache-control header if present`。
   Cloudflare 默认不缓存 `.xml` / `.torrent`，不加这条规则，每次订阅轮询都会回源 R2。

`CF_API_TOKEN` 和 `CF_ZONE_ID` 都配置后，发布或删除种子会立刻清掉 `rss.xml` 的缓存；没配置时，最多延迟 60 秒。

## 本地开发

```bash
cp .dev.vars.example .dev.vars      # 本地测试请设 ADMIN_PASSWORD=adminpw
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
