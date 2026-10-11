# RSS种子站点 Docker 镜像（构建上下文 = 仓库根目录）
#
# 与 Cloudflare 部署完全一致：容器里跑的是同一个 workerd 运行时
# （wrangler dev 本地模式），D1 用本地 SQLite、R2 用本地持久化，
# src/entry.py 业务代码不变，网页/登录/API 行为一致。
# 构建期完成全部依赖安装与 Python vendor（pywrangler sync）。
#
# 注意：workerd 启动时会从 Cloudflare 边缘拉取一次 Pyodide 运行时
# （pyodide-capnp-bin.edgeworker.net，约几十 MB）。wrangler 未开放磁盘缓存
# 参数，无法预打进镜像；宿主机需允许该域名的出站 HTTPS。运行起来之后
# 不再依赖外网。

# uv 官方镜像：自带 uv + Python 3.13（wrangler.jsonc 的 compatibility_date
# 2026-09-01 会解析为 Python Workers 3.13 运行时，见 pywrangler/utils.py）
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

ENV PYTHONUTF8=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_INSTALL_DIR=/opt/uv/python \
    UV_CACHE_DIR=/opt/uv/cache \
    # 非 TTY 环境：禁止 wrangler 交互提示与遥测
    CI=true \
    WRANGLER_SEND_METRICS=false

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

# 从官方 node 镜像借 Node.js 22（pywrangler 通过 npx 调 wrangler）
COPY --from=node:22-slim /usr/local/lib/node_modules /usr/local/lib/node_modules
COPY --from=node:22-slim /usr/local/bin/node /usr/local/bin/node
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

WORKDIR /app

# 1) npm 依赖（wrangler ^4.141.0，按 package-lock 锁定）
COPY package.json package-lock.json ./
RUN npm ci

# 2) 项目 venv（dev 组里有 pywrangler/workers-py）
#    .python-version 不复制进来：让 venv 直接用镜像自带的 Python 3.13
COPY pyproject.toml pylock.toml uv.lock ./
RUN uv sync --frozen

# 3) 源码（.dockerignore 已排除本地 venv/node_modules/python_modules 等）
COPY . .

# 4) Python Worker 依赖 vendor：生成 python_modules/（pyodide wheel）与
#    .venv-workers/，并写入 sync token —— 启动时 sync 检测到无需变更，直接跳过
RUN uv run pywrangler sync --force

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:/usr/local/bin:$PATH"

COPY docker/entrypoint.sh /app/docker/entrypoint.sh
RUN chmod +x /app/docker/entrypoint.sh

EXPOSE 8787

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-8787}/api/v1/stats" || exit 1

ENTRYPOINT ["/app/docker/entrypoint.sh"]
