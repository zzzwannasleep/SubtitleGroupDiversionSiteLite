# 🧲 RSS种子站点

> 一个支持用户注册、角色权限管理和RSS订阅的种子发布平台

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ 功能特性

- 🔐 **用户系统** - 注册/登录，支持三种角色：管理员、发布员、普通用户
- 📤 **种子发布** - 发布员可上传 `.torrent` 文件，自动分类管理
- 📡 **RSS订阅** - 自动生成标准RSS feed，支持qBittorrent自动下载
- 🎛️ **管理后台** - 管理员可管理用户权限、删除种子、查看统计
- 🐳 **多种部署** - 支持Docker、systemd、手动部署等多种方式
- 💾 **持久存储** - SQLite数据库，数据永久保存
- 📱 **响应式设计** - 适配手机、平板、桌面端

## 🚀 快速开始

### 方式一：Docker部署（推荐）

```bash
# 1. 克隆仓库
git clone https://github.com/zzzwannasleep/SubtitleGroupDiversionSiteLite.git
cd SubtitleGroupDiversionSiteLite

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，修改 SECRET_KEY 和 ADMIN_PASSWORD

# 3. 启动（后台运行）
docker-compose up -d

# 4. 查看日志
docker-compose logs -f
```

访问 http://localhost:5000

### 方式二：Linux一键部署

```bash
# 1. 克隆仓库
git clone https://github.com/zzzwannasleep/SubtitleGroupDiversionSiteLite.git
cd SubtitleGroupDiversionSiteLite

# 2. 运行部署脚本
chmod +x deploy/install.sh
sudo ./deploy/install.sh your-domain.com
```

### 方式三：手动部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置
cp .env.example .env
# 编辑 .env

# 3. 运行
# Windows
start.bat

# Linux/macOS
chmod +x start.sh
./start.sh

# 生产环境
./start.sh --production
```

## 📋 环境变量配置

复制 `.env.example` 为 `.env` 并修改：

```env
# 必须修改！用于Session加密
SECRET_KEY=your-super-secret-key-change-this-now

# 必须修改！管理员密码
ADMIN_PASSWORD=your-secure-admin-password

# 可选配置
SITE_NAME=RSS种子站点
UPLOAD_FOLDER=uploads
DATABASE_PATH=data/site.db
MAX_FILE_SIZE=16
```

### 生成安全密钥

```bash
# Linux/macOS
openssl rand -hex 32

# Python
python -c "import secrets; print(secrets.token_hex(32))"
```

## 📖 使用说明

### 1. 首次登录

- 访问站点
- 使用默认管理员账号：`admin`
- 密码：你在 `.env` 中设置的 `ADMIN_PASSWORD`

### 2. 注册用户

- 点击注册，创建普通用户账号
- 普通用户只能查看和下载种子

### 3. 设置发布员

- 管理员进入管理后台 (`/admin`)
- 在用户列表中找到目标用户
- 点击"设为发布员"按钮

### 4. 发布种子

- 发布员登录后，点击"发布种子"
- 填写标题、选择分类、上传 `.torrent` 文件
- 支持文件大小：最大16MB

### 5. 订阅RSS（qBittorrent）

1. 打开 qBittorrent → 工具 → RSS阅读器
2. 点击 **新建订阅**
3. 输入RSS地址：`http://your-domain.com/rss.xml`
4. 配置自动下载规则：
   - 工具 → RSS → 自动下载规则
   - 创建新规则，留空匹配条件（下载全部）
   - 设置保存路径
   - 勾选 **使用自动下载**

## 🛠️ 生产环境管理

### Systemd服务（Linux）

```bash
# 查看状态
sudo systemctl status rss-torrent-site

# 启动/停止/重启
sudo systemctl start rss-torrent-site
sudo systemctl stop rss-torrent-site
sudo systemctl restart rss-torrent-site

# 开机自启
sudo systemctl enable rss-torrent-site
```

### Docker管理

```bash
# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f

# 重启
docker-compose restart

# 停止
docker-compose down

# 更新（拉取最新代码后）
docker-compose down
docker-compose up -d --build
```

### 日志查看

```bash
# Linux (systemd)
sudo tail -f /var/log/rss-torrent/error.log

# Docker
docker-compose logs -f

# 手动部署
# 日志在 logs/ 目录或控制台输出
```

### 数据备份

```bash
# 备份数据库和上传文件
tar -czvf backup-$(date +%Y%m%d).tar.gz data/ uploads/

# 恢复
tar -xzvf backup-20240101.tar.gz
```

## 🔒 安全建议

1. **修改默认密码** ⚠️ 立即修改 `.env` 中的 `SECRET_KEY` 和 `ADMIN_PASSWORD`
2. **启用HTTPS** 生产环境必须使用SSL证书
   ```bash
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```
3. **防火墙配置** 只开放80/443端口
4. **定期备份** 定时备份 `data/` 和 `uploads/` 目录
5. **更新依赖** 定期运行 `pip install --upgrade -r requirements.txt`

## 📁 项目结构

```
.
├── app.py                      # Flask主应用
├── requirements.txt            # Python依赖
├── .env.example               # 环境变量示例
├── .env                       # 环境变量（不提交Git）
├── .gitignore                 # Git忽略规则
├── Dockerfile                 # Docker镜像构建
├── docker-compose.yml         # Docker Compose配置
├── start.bat                  # Windows启动脚本
├── start.sh                   # Linux/macOS启动脚本
├── run.bat                    # Windows后台运行工具
├── README.md                  # 本文件
├── LICENSE                    # MIT许可证
│
├── deploy/                    # 部署配置
│   ├── install.sh            # 自动部署脚本
│   ├── nginx.conf            # Nginx配置
│   └── rss-torrent-site.service  # Systemd服务
│
├── data/                      # SQLite数据库
├── uploads/                   # 种子文件存储
├── logs/                      # 日志文件
│
└── templates/                 # HTML模板
    ├── base.html             # 基础模板
    ├── index.html            # 种子列表页
    ├── login.html            # 登录页
    ├── register.html         # 注册页
    ├── upload.html           # 上传页
    └── admin.html            # 管理后台
```

## ❓ 常见问题

### Q: 如何修改端口号？

**开发环境**：修改 `app.py` 中的 `port=5000`

**生产环境**：修改 `deploy/rss-torrent-site.service` 中的 `-b 127.0.0.1:8000`

**Docker**：修改 `docker-compose.yml` 中的 `ports: - "5000:5000"`

### Q: 数据库文件在哪里？

默认在 `data/site.db`，可通过 `.env` 中的 `DATABASE_PATH` 修改

### Q: 上传的种子文件在哪里？

默认在 `uploads/` 目录，可通过 `.env` 中的 `UPLOAD_FOLDER` 修改

### Q: 如何迁移到MySQL/PostgreSQL？

修改 `app.py` 中的数据库连接部分。建议使用 SQLAlchemy 替代原始 sqlite3，示例：

```python
from flask_sqlalchemy import SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql://user:password@localhost/dbname'
db = SQLAlchemy(app)
```

### Q: 后台运行命令被关闭怎么办？

- **Docker**：`docker-compose up -d` 会持久运行
- **Linux**：使用 systemd 服务
- **Windows**：使用 `run.bat` 选择后台运行，或安装为Windows服务

### Q: 如何更新应用？

```bash
# 拉取最新代码
git pull origin main

# Docker部署
docker-compose down
docker-compose up -d --build

# Systemd部署
sudo systemctl restart rss-torrent-site
```

## 📝 技术栈

- **后端**：Python 3.8+, Flask
- **数据库**：SQLite（可扩展至MySQL/PostgreSQL）
- **WSGI服务器**：Gunicorn
- **反向代理**：Nginx
- **容器化**：Docker, Docker Compose
- **前端**：原生HTML5 + CSS3

## 🔮 未来计划

- [ ] 用户头像和种子封面
- [ ] 评论和评分系统
- [ ] 下载统计和热门排行
- [ ] 搜索和高级筛选
- [ ] RSS过滤器（关键词、分类、大小）
- [ ] 邮箱验证和密码找回
- [ ] API接口和第三方集成
- [ ] 多语言支持
- [ ] WebSocket实时通知

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 [MIT](LICENSE) 许可证

## 👤 作者

- GitHub: [@zzzwannasleep](https://github.com/zzzwannasleep)

---

⭐ 如果这个项目对你有帮助，请给个Star！
