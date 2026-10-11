#!/bin/sh
# RSS种子站点容器入口：
# 1. 校验必填环境变量（缺了直接报错退出，和 Worker 运行时缺变量的提示一致）
# 2. 从环境变量生成 .dev.vars（wrangler dev 自动读取，等价于 CF 的运行时变量）
# 3. 幂等初始化本地 D1（schema.sql 全部 IF NOT EXISTS / INSERT OR IGNORE）
# 4. 启动 wrangler dev（workerd）本地模式，D1/R2 状态持久化在 /data/state
set -eu

PORT="${PORT:-8787}"
STATE_DIR="${SGDS_STATE_DIR:-/data/state}"

missing=""
[ -n "${PUBLIC_URL:-}" ] || missing="$missing PUBLIC_URL"
[ -n "${ADMIN_PASSWORD:-}" ] || missing="$missing ADMIN_PASSWORD"
if [ -n "$missing" ]; then
    echo "未配置：$missing" >&2
    echo "请通过 docker run -e / compose environment 提供，例如：" >&2
    echo "  PUBLIC_URL=http://localhost:8787" >&2
    echo "  ADMIN_PASSWORD=你的管理员密码" >&2
    exit 1
fi

# SECRET_KEY 未提供时自动生成一次并保存在数据卷里，重启后保持不变
# （它是登录 cookie 的签名密钥，变了会让所有已登录会话失效）
if [ -z "${SECRET_KEY:-}" ]; then
    keyfile="$STATE_DIR/secret-key"
    mkdir -p "$STATE_DIR"
    if [ -f "$keyfile" ]; then
        SECRET_KEY="$(cat "$keyfile")"
    else
        SECRET_KEY="$(od -An -N32 -tx1 /dev/urandom | tr -d ' \n')"
        echo "$SECRET_KEY" > "$keyfile"
        chmod 600 "$keyfile"
    fi
fi

# 生成 .dev.vars（可选变量未设置时整行不写，避免空值覆盖语义）
# 自部署不需要 CF_API_TOKEN/CF_ZONE_ID：没有 CDN 缓存可清，
# rss.xml 直出路由自带 max-age=60 兜底。
{
    echo "PUBLIC_URL=$PUBLIC_URL"
    echo "SECRET_KEY=$SECRET_KEY"
    echo "ADMIN_PASSWORD=$ADMIN_PASSWORD"
    if [ -n "${SITE_NAME:-}" ]; then echo "SITE_NAME=$SITE_NAME"; fi
} > /app/.dev.vars

# 建表（幂等）：与 README 本地开发步骤完全一致
npx wrangler d1 execute DB --local --file schema.sql --persist-to "$STATE_DIR"

# 同一 wrangler.jsonc + 同一 persist 目录 ⇒ 与上面建表写进同一个本地 D1 库
exec pywrangler dev \
    --ip 0.0.0.0 \
    --port "$PORT" \
    --persist-to "$STATE_DIR" \
    --show-interactive-dev-session=false \
    --log-level info