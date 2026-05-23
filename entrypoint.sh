#!/bin/sh
set -e

# 修复因 volume 挂载导致的权限问题
# 如果当前是 root 用户，修正数据目录权限后降权运行
if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/data /app/uploads
    chown -R appuser:appuser /app/data /app/uploads 2>/dev/null || true
    chmod -R u+w /app/data /app/uploads 2>/dev/null || true
    exec su-exec appuser "$@"
else
    exec "$@"
fi
