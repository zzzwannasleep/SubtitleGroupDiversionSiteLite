#!/bin/bash

# ==========================================
# RSS种子站点 - Linux/macOS启动脚本
# ==========================================

echo "=========================================="
echo "RSS种子站点启动脚本"
echo "=========================================="
echo ""

# 检查Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到python3，请先安装Python 3.8+"
    exit 1
fi

# 创建虚拟环境
if [ ! -d "venv" ]; then
    echo "[1/4] 创建虚拟环境..."
    python3 -m venv venv
fi

echo "[2/4] 激活虚拟环境..."
source venv/bin/activate

echo "[3/4] 安装依赖..."
pip install -q -r requirements.txt

# 检查.env
if [ ! -f ".env" ]; then
    echo "[提示] 创建默认配置文件 .env"
    cp .env.example .env
    echo "请编辑 .env 文件修改默认密码和密钥！"
    echo ""
fi

echo "[4/4] 启动应用..."
echo ""
echo "=========================================="
echo "应用已启动！"
echo "=========================================="
echo ""
echo "访问地址: http://127.0.0.1:5000"
echo "RSS地址: http://127.0.0.1:5000/rss.xml"
echo ""
echo "默认管理员账号: admin"
echo "默认管理员密码: admin (或查看 .env 文件)"
echo ""
echo "按 Ctrl+C 停止运行"
echo ""

# 生产环境使用gunicorn，开发环境使用flask
if [ "$1" = "--production" ] || [ "$1" = "-p" ]; then
    echo "[生产模式] 使用Gunicorn启动 (4 workers)..."
    gunicorn -w 4 -b 0.0.0.0:5000 --access-logfile - --error-logfile - app:app
else
    echo "[开发模式] 使用Flask内置服务器..."
    python app.py
fi
