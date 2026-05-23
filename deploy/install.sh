#!/bin/bash

# ==========================================
# RSS种子站点部署脚本
# ==========================================

set -e

# 配置
APP_NAME="rss-torrent-site"
APP_DIR="/var/www/$APP_NAME"
APP_USER="www-data"
DOMAIN="${1:-your-domain.com}"

echo "=========================================="
echo "RSS种子站点部署脚本"
echo "=========================================="
echo ""

# 检查root权限
if [ "$EUID" -ne 0 ]; then 
    echo "请使用 sudo 运行此脚本"
    exit 1
fi

echo "1. 安装系统依赖..."
apt-get update
apt-get install -y python3-pip python3-venv nginx git curl

echo ""
echo "2. 创建应用目录..."
mkdir -p $APP_DIR
mkdir -p /var/log/rss-torrent
mkdir -p /var/www/rss-torrent-site/data

echo ""
echo "3. 复制应用文件..."
# 假设当前目录是项目根目录
cp -r . $APP_DIR/
cd $APP_DIR

echo ""
echo "4. 创建Python虚拟环境..."
python3 -m venv venv
source venv/bin/activate

echo ""
echo "5. 安装Python依赖..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "6. 配置环境变量..."
if [ ! -f "$APP_DIR/.env" ]; then
    cp .env.example .env
    echo "请编辑 $APP_DIR/.env 文件配置你的密钥和密码"
    echo "然后重新运行此脚本"
    exit 0
fi

echo ""
echo "7. 设置权限..."
chown -R $APP_USER:$APP_USER $APP_DIR
chmod 755 $APP_DIR
chmod -R 755 $APP_DIR/uploads
chmod -R 755 $APP_DIR/data

echo ""
echo "8. 配置Systemd服务..."
cp deploy/rss-torrent-site.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable rss-torrent-site

echo ""
echo "9. 配置Nginx..."
cp deploy/nginx.conf /etc/nginx/sites-available/$APP_NAME
sed -i "s/your-domain.com/$DOMAIN/g" /etc/nginx/sites-available/$APP_NAME
ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx

echo ""
echo "10. 启动应用..."
systemctl start rss-torrent-site

echo ""
echo "=========================================="
echo "部署完成！"
echo "=========================================="
echo ""
echo "站点地址: http://$DOMAIN"
echo "RSS地址: http://$DOMAIN/rss.xml"
echo ""
echo "管理命令:"
echo "  查看状态: sudo systemctl status rss-torrent-site"
echo "  重启应用: sudo systemctl restart rss-torrent-site"
echo "  查看日志: sudo tail -f /var/log/rss-torrent/error.log"
echo ""
echo "默认管理员账号: admin"
echo "默认管理员密码: 查看 .env 文件中的 ADMIN_PASSWORD"
echo ""
echo "如需HTTPS，请运行: certbot --nginx -d $DOMAIN"
echo ""
