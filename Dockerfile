FROM python:3.11-slim

WORKDIR /app

# 安装依赖 + 编译 su-exec 用于降权
RUN apt-get update && apt-get install -y --no-install-recommends gcc libc6-dev curl ca-certificates && \
    curl -L https://github.com/ncopa/su-exec/archive/refs/tags/v0.2.tar.gz | tar xz -C /tmp && \
    cd /tmp/su-exec-0.2 && make && mv su-exec /usr/local/bin/ && \
    apt-get purge -y --auto-remove gcc libc6-dev curl ca-certificates && \
    rm -rf /var/lib/apt/lists/* /tmp/su-exec-0.2

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p uploads data

# 非root用户运行（安全）
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# 暴露端口
EXPOSE 5000

# Entrypoint 脚本：启动时修复 volume 挂载导致的权限问题
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# 默认启动命令
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--access-logfile", "-", "--error-logfile", "-", "app:app"]
