FROM python:3.11-slim

WORKDIR /app

# 安装依赖 + su-exec 用于降权
RUN apt-get update && apt-get install -y --no-install-recommends su-exec && rm -rf /var/lib/apt/lists/*

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
