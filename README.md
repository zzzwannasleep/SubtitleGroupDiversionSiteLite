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

## Docker 自部署（与 Cloudflare 版同一运行时）

不想用 Cloudflare、想自己部署的话，`docker/` 目录自带全部 Docker 配置
（Dockerfile / compose.yml / entrypoint.sh / .env.example），互不掺杂。
容器里跑的就是**同一个 workerd 运行时**（wrangler 本地模式）：
`src/entry.py` 业务代码不变，网页、登录、API 与 Cloudflare 部署完全一致；
差异只在存储位置——D1 存到数据卷里的 SQLite、R2 存到数据卷里的本地持久化。
构建期会完成全部依赖安装。

**RSS 链接就是 `站点域名/rss.xml`**：Docker 下只有一个站点地址
（`PUBLIC_URL`，默认指向站点自身），RSS 和种子下载都从它直接出，
不需要 Cloudflare 版那种独立的文件域名——那是为绕开 Workers 免费请求
额度的设计，自部署用不上。

> **联网要求**：容器每次启动时 workerd 会从 Cloudflare 边缘拉取一次 Pyodide
> 运行时（`pyodide-capnp-bin.edgeworker.net`，约几十 MB）——wrangler 未开放
> 磁盘缓存参数，这一步没法预打进镜像。宿主机需允许该域名出站；跑起来之后
> 运行期不再依赖外网。

### 快速开始

```bash
cd docker
cp .env.example .env      # 至少把 ADMIN_PASSWORD 改掉
docker compose up -d --build
```

打开 `http://localhost:8787`，用 admin + 你设置的密码登录即可。
首次启动会自动建表（schema.sql，幂等），并生成默认管理员。

### 配置（docker/.env）

| 名称 | 必填 | 说明 |
|---|---|---|
| `PUBLIC_URL` | ✅ | 站点对外地址：RSS 链接 = 它 + `/rss.xml`，种子下载 = 它 + `/t/<id>.torrent`，默认 `http://localhost:8787` |
| `ADMIN_PASSWORD` | ✅ | admin 的密码 |
| `SECRET_KEY` | | 登录 cookie 签名密钥；不填则首次启动自动生成并保存在数据卷里 |
| `SITE_NAME` | | 站点名，默认“RSS种子站点” |
| `SGDS_PORT` | | 宿主机映射端口；改了要同步改 `PUBLIC_URL` |

Cloudflare 专属的 `CF_API_TOKEN` / `CF_ZONE_ID` 在 Docker 里没有意义
（没有 CDN 缓存可清），不提供。

### 数据与备份

D1（SQLite）和 R2（本地模拟）都固定存在名为 `sgds-state` 的数据卷里，
**备份这个卷 = 备份全站**（种子文件、元数据、用户、API Key）：

```bash
docker run --rm -v sgds-state:/data -v "$PWD:/backup" alpine \
    tar czf /backup/sgds-state.tgz -C /data .
# 恢复：解压回同名卷后再 docker compose up
```

### 与 Cloudflare 部署的差异

- 自部署时 RSS 与种子下载由 Worker 的 `/rss.xml` 和 `/t/<id>.torrent`
  两条直出路由提供（行为与 R2 公开域名一致：同样的响应头、缺失即 404）。
  **Cloudflare 部署不受影响**：这两个路径仍由 R2 公开域名直接返回、不进 Worker。
- `wrangler dev` 是开发形态的运行时（与生产同一 workerd 内核），适合个人/
  轻量自托管；正式对外高流量场景仍建议用 Cloudflare 部署。
- 升级镜像：`git pull && cd docker && docker compose up -d --build`，数据在卷里保留。

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
python scripts/test_r2_serve_routes.py # RSS/种子直出路由测试（自部署 Docker 依赖这两条）
python scripts/test_episode_match.py # 合集/分集匹配算法单测
python scripts/test_qb_tool.py       # QB 清理工具计划逻辑单测
python scripts/test_qb_e2e.py        # QB 清理工具端到端（内置 mock qBittorrent）
python scripts/test_collection_flow.py # 合集上线自动删分集 端到端
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

## 合集 / 分集自动清理

发布**合集种子**（种子内含多个文件，或标题含「合集 / 全集 / 完全版 / complete / batch」等关键词）时，站点会自动检测并删除**命名相同**的分集种子，只留合集：

- 匹配规则：去掉季号、集数标记后的「系列命名」一致 + 季号兼容（见 `src/episode_match.py`，`S01E03`、`第02话`、`E04`、`Vol.1`、`01-12集`、末尾裸集数等都会被识别为分集标记）。
- 防误删：画质/季号/系列名不同的**不会**被删；`高达00 第02话` 这种番名里带数字的也不会被误伤。
- 被删的种子会在发布后的提示里列出，API 上传响应里带 `removed_episodes` 字段。
- 已有部署升级：无需手动操作，Worker 冷启动会自动给 torrents 表补 `is_collection / series_key / season` 三列（或把 schema.sql 末尾注释里的 ALTER 执行一次）。

### qBittorrent 配套清理工具

检测 qBittorrent 里命名相同的分集任务并删掉，匹配规则与站点同源。按平台三选一：

**Windows（推荐，零依赖）**：编辑 `tools/qb_clean.ps1` 顶部的 QB 地址/账号/密码三行，然后

- 全自动（推荐）：qBittorrent → 设置 → 下载 → 「Torrent 完成时运行外部程序」填：

  ```
  "D:\完整路径\qb_clean.bat" "%I"
  ```

  合集下载完成的那一刻自动清理同名分集。
- 手动：双击 `qb_clean.bat` 看报告（不动任何东西）；`qb_clean.bat --apply` 真正删除。

**Linux / macOS（零 Python 依赖，需 curl + jq）**：编辑 `tools/qb_clean.sh` 顶部三行配置

```bash
/qb_clean.sh 所在路径/qb_clean.sh "%I"   # QB 完成时运行外部程序里填这个
./qb_clean.sh --apply                    # 手动全量清理（不带 --apply 只看报告）
KEEP_FILES=1 ./qb_clean.sh --apply       # 只删任务、保留硬盘文件
```

**Python（跨平台备选）**：`python tools/qb_episode_clean.py --url http://127.0.0.1:8080 --user admin --password 你的密码 [--apply]`
（默认 dry-run；`--site/--site-key` 可在合集还没被 RSS 下进 QB 时以站点为基准清理。）

三个入口的匹配规则完全同源，默认都连硬盘文件一起删（内容已包含在合集里），`-KeepFiles` / `KEEP_FILES=1` 可改为只删任务。

API 文档见站内 `/api/docs` 或 [docs/API.md](docs/API.md)。

## 已知限制

- Python Workers 目前还是 **beta**（`create-cloudflare` 里标注为 `Python (beta)`）。
- 免费版每个请求只有 **10ms CPU**。普通页面没问题；注册和普通用户登录要做 PBKDF2（10 万次迭代），有可能超时。admin 登录直接比对 secret，不受影响。如果部署后注册或登录报 1102 错误，可以升级 Workers Paid（每月 5 美元，单请求 30 秒 CPU）。

## License

MIT
