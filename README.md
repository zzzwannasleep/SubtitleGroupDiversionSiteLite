# RSS种子站点

一个简单的RSS种子发布站点，支持用户注册、发布员上传种子、自动生成RSS feed供qBittorrent订阅下载。

## 功能

- ✅ 用户注册/登录系统
- ✅ 角色权限管理（管理员/发布员/普通用户）
- ✅ 发布员上传种子文件
- ✅ 自动生成标准RSS feed（支持qBittorrent订阅）
- ✅ 管理后台（用户权限管理、种子管理）
- ✅ 响应式Web界面
- ✅ SQLite持久化存储
- ✅ 生产环境部署支持（Gunicorn + Nginx）
- ✅ Docker支持

## 技术栈

- **后端**: Python Flask + SQLite
- **WSGI**: Gunicorn
- **反向代理**: Nginx
- **前端**: HTML + CSS（无框架依赖）

## 快速开始

### 方式一：Windows本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 复制配置文件
copy .env.example .env
# 编辑 .env 修改 SECRET_KEY 和 ADMIN_PASSWORD

# 3. 运行
start.bat
# 或
python app.py
```

### 方式二：Linux/macOS本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 复制配置文件
cp .env.example .env
# 编辑 .env 修改 SECRET_KEY 和 ADMIN_PASSWORD

# 3. 运行
chmod +x start.sh
./start.sh

# 生产模式
./start.sh --production
```

### 方式三：Docker部署（推荐）

```bash
# 1. 复制配置
cp .env.example .env
# 编辑 .env

# 2. 启动
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止
docker-compose down
```

### 方式四：生产服务器部署（Ubuntu/Debian）

```bash
# 1. 复制项目到服务器
# 2. 运行部署脚本
chmod +x deploy/install.sh
sudo ./deploy/install.sh your-domain.com

# 3. 配置SSL（推荐）
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 配置说明

### 环境变量 (.env)

```env
# 必须修改！
SECRET_KEY=your-super-secret-key-change-this-now
ADMIN_PASSWORD=your-secure-admin-password

# 可选
SITE_NAME=RSS种子站点
UPLOAD_FOLDER=uploads
DATABASE_PATH=data/site.db
MAX_FILE_SIZE=16
```

### 生成安全的SECRET_KEY

```bash
# Linux/macOS
openssl rand -hex 32

# Python
python -c "import secrets; print(secrets.token_hex(32))"
```

## 使用说明

### 1. 注册账号
访问注册页面创建新账号，默认角色为普通用户。

### 2. 管理员设置发布员
使用管理员账号登录，进入管理后台，将普通用户设置为发布员。

### 3. 发布种子
发布员登录后可以上传 `.torrent` 文件并填写相关信息。

### 4. 订阅RSS
在qBittorrent中：
- 打开 **工具 → RSS阅读器**
- 点击 **新建订阅**
- 输入RSS地址: `http://你的服务器地址/rss.xml`
- 设置自动下载规则即可

### 5. RSS格式说明
生成的RSS符合标准RSS 2.0格式，包含：
- `title`: 种子标题
- `link`: 种子下载链接
- `enclosure`: 种子文件附件（qBittorrent自动识别）
- `pubDate`: 发布时间
- `category`: 分类

## qBittorrent自动下载配置

1. 打开qBittorrent → 工具 → RSS阅读器
2. 新建订阅，粘贴RSS链接
3. 点击 **RSS → 自动下载规则**
4. 创建新规则：
   - 规则名称：自定义
   - 匹配所有条件：留空（下载全部）
   - 保存路径：选择下载目录
   - 勾选 **使用自动下载**

## 生产环境管理

### Systemd服务命令

```bash
# 查看状态
sudo systemctl status rss-torrent-site

# 启动
sudo systemctl start rss-torrent-site

# 停止
sudo systemctl stop rss-torrent-site

# 重启
sudo systemctl restart rss-torrent-site

# 开机自启
sudo systemctl enable rss-torrent-site
```

### 日志查看

```bash
# 应用日志
sudo tail -f /var/log/rss-torrent/error.log
sudo tail -f /var/log/rss-torrent/access.log

# Nginx日志
sudo tail -f /var/log/nginx/rss-torrent-error.log
```

### 备份

```bash
# 备份数据库和上传文件
tar -czvf backup-$(date +%Y%m%d).tar.gz data/ uploads/

# 恢复
tar -xzvf backup-20240101.tar.gz
```

## 项目结构

```
rss-torrent-site/
├── app.py                  # 主应用
├── requirements.txt        # Python依赖
├── .env.example           # 环境变量示例
├── .env                   # 环境变量（不提交到git）
├── Dockerfile             # Docker镜像
├── docker-compose.yml     # Docker Compose配置
├── start.bat              # Windows启动脚本
├── start.sh               # Linux/macOS启动脚本
├── README.md
├── deploy/
│   ├── install.sh         # 自动部署脚本
│   ├── nginx.conf         # Nginx配置
│   └── rss-torrent-site.service  # Systemd服务
├── data/                  # SQLite数据库目录
├── uploads/               # 种子文件存储
└── templates/             # HTML模板
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register.html
    ├── upload.html
    └── admin.html
```

## 安全建议

1. **修改默认密码**: 立即修改 `.env` 中的 `SECRET_KEY` 和 `ADMIN_PASSWORD`
2. **使用HTTPS**: 生产环境必须配置SSL证书
3. **防火墙**: 只开放80/443端口
4. **定期备份**: 定时备份 `data/` 和 `uploads/` 目录
5. **更新依赖**: 定期运行 `pip install --upgrade -r requirements.txt`

## 常见问题

### Q: 如何修改端口号？
A: 开发环境修改 `app.py` 中的 `port=5000`，生产环境修改 `deploy/rss-torrent-site.service` 中的 `-b 127.0.0.1:8000`

### Q: 如何配置HTTPS？
A: 使用 Let's Encrypt: `sudo certbot --nginx -d your-domain.com`

### Q: 数据存在哪里？
A: SQLite数据库在 `data/site.db`，种子文件在 `uploads/` 目录

### Q: 如何迁移到MySQL/PostgreSQL？
A: 修改 `app.py` 中的数据库连接部分，使用 `sqlalchemy` 替代原始sqlite3

## 扩展建议

- [ ] 添加用户头像、种子封面
- [ ] 添加评论系统
- [ ] 添加下载统计
- [ ] 添加搜索功能
- [ ] 添加RSS过滤器（按分类、关键词等）
- [ ] 添加邮箱验证
- [ ] 添加Rate Limiting
- [ ] 使用Redis缓存
- [ ] 添加WebSocket实时通知

## 许可证

MIT License
