# 🧲 RSS种子站点

> 一个支持用户注册、角色权限管理和RSS订阅的种子发布平台

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com)
[![Docker](https://img.shields.io/badge/Docker-Hub-blue.svg)](https://hub.docker.com)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI%2FCD-blue.svg)](.github/workflows/docker-build.yml)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ 功能特性

- 🔐 **用户系统** - 注册/登录，支持三种角色：管理员、发布员、普通用户
- 📤 **种子发布** - 发布员可上传 `.torrent` 文件，自动分类管理
- 📡 **RSS订阅** - 自动生成标准RSS feed，支持qBittorrent自动下载
- 🔌 **API接口** - 完整的RESTful API，支持第三方应用对接
- 🔑 **API Key管理** - 用户可创建/管理API Key，安全对接外部应用
- 📚 **API文档** - 内置交互式API文档页面，包含示例代码
- 🎛️ **管理后台** - 管理员可管理用户权限、删除种子、查看统计
- 🐳 **多种部署** - 支持Docker、systemd、手动部署等多种方式
- 💾 **持久存储** - SQLite数据库，数据永久保存
- 📱 **响应式设计** - 适配手机、平板、桌面端

## 🚀 快速开始

### 方式一：Docker Hub镜像部署（最简单）

```bash
# 1. 直接拉取镜像运行（无需克隆仓库）
docker pull zzzwannasleep/subtitle-group-diversion-site:latest

# 2. 运行容器
docker run -d \
  --name rss-torrent \
  -p 5000:5000 \
  -e SECRET_KEY=your-secret-key \
  -e ADMIN_PASSWORD=your-admin-password \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/uploads:/app/uploads \
  --restart always \
  zzzwannasleep/subtitle-group-diversion-site:latest

# 或使用 docker-compose（推荐）
# 下载 docker-compose.yml 和 .env.example
curl -O https://raw.githubusercontent.com/zzzwannasleep/SubtitleGroupDiversionSiteLite/main/docker-compose.yml
curl -O https://raw.githubusercontent.com/zzzwannasleep/SubtitleGroupDiversionSiteLite/main/.env.example
cp .env.example .env
# 编辑 .env 后启动
docker-compose up -d
```

访问 http://localhost:5000

### 方式二：Docker本地构建部署

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

### 方式三：Linux一键部署

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

### 6. API 对接（第三方应用）

#### 对接流程

1. **注册账号**并联系管理员设置为**发布员**
2. 访问 **API Keys** 页面，创建 API Key
3. **立即复制保存** Key（只显示一次）
4. 查看 **API文档** (`/api/docs`) 了解接口详情
5. 在第三方应用中使用 API Key 进行对接

#### 快速示例

```bash
# 1. 获取站点统计（无需认证）
curl http://your-domain.com/api/v1/stats

# 2. 获取种子列表
curl -H "X-API-Key: your-api-key" \
  http://your-domain.com/api/v1/torrents?page=1&per_page=20

# 3. 上传种子
curl -X POST \
  -H "X-API-Key: your-api-key" \
  -F "torrent=@movie.torrent" \
  -F "title=电影名称" \
  -F "category=movie" \
  http://your-domain.com/api/v1/torrents
```

**查看完整 API 文档：** 访问 `http://your-domain.com/api/docs`

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

**Docker Hub镜像部署：**

```bash
# 更新到最新镜像
docker-compose pull
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down
```

**本地构建部署：**

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
    ├── admin.html            # 管理后台
    ├── api_keys.html         # API Key管理
    └── api_docs.html         # API文档
```

## 🐳 Docker Hub 自动构建

本项目使用 **GitHub Actions** 自动构建 Docker 镜像并推送到 **Docker Hub**。

### 自动构建触发条件

- ✅ `push` 到 `main` 分支
- ✅ 推送 `v*` 标签（如 `v1.0.0`）
- ✅ Pull Request（仅构建测试，不推送）

### 配置自动构建

如果你想在自己的仓库启用自动构建：

1. **Fork 本仓库** 或创建新仓库推送代码

2. **配置 GitHub Secrets**：
   - 打开仓库 → Settings → Secrets and variables → Actions
   - 添加 `DOCKERHUB_USERNAME`（你的 Docker Hub 用户名）
   - 添加 `DOCKERHUB_TOKEN`（从 [Docker Hub](https://hub.docker.com/settings/security) 生成的 Token）

3. **获取 Docker Hub Token**：
   - 访问 https://hub.docker.com/settings/security
   - 点击 **New Access Token**
   - 描述填写 "GitHub Actions"
   - 权限选择 **Read, Write, Delete**
   - 点击 **Generate** 并复制 Token

4. **推送代码触发构建**：
   ```bash
   git push origin main
   ```

详细配置指南见 [DOCKER_BUILD_GUIDE.md](DOCKER_BUILD_GUIDE.md)

### 镜像标签

自动构建会生成以下标签：

```
zzzwannasleep/subtitle-group-diversion-site:latest    # 最新版本
zzzwannasleep/subtitle-group-diversion-site:main      # 分支名
zzzwannasleep/subtitle-group-diversion-site:v1.0.0    # 版本标签
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
