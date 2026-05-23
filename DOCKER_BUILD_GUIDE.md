# 🐳 Docker Hub 自动构建配置指南

## 需要配置的GitHub Secrets

在GitHub仓库中设置以下Secrets：

### 1. DOCKERHUB_USERNAME
- **值**: 你的Docker Hub用户名
- **获取方式**: 
  - 访问 https://hub.docker.com/
  - 登录后，用户名显示在右上角

### 2. DOCKERHUB_TOKEN
- **值**: Docker Hub访问令牌（推荐）或密码
- **获取方式**:
  1. 访问 https://hub.docker.com/settings/security
  2. 点击 **New Access Token**
  3. 输入描述（如 "GitHub Actions"）
  4. 选择权限（**Read, Write, Delete**）
  5. 点击 **Generate**
  6. **立即复制令牌**（只显示一次！）

> ⚠️ **强烈建议使用Token而不是密码**，更安全且可单独撤销

## 配置步骤

### 步骤1：在GitHub添加Secrets

1. 打开你的GitHub仓库
2. 点击 **Settings** → **Secrets and variables** → **Actions**
3. 点击 **New repository secret**
4. 分别添加：
   - `DOCKERHUB_USERNAME` = 你的Docker Hub用户名
   - `DOCKERHUB_TOKEN` = 上面生成的Token

### 步骤2：修改镜像名称（可选）

编辑 `.github/workflows/docker-build.yml`：

```yaml
env:
  IMAGE_NAME: ${{ secrets.DOCKERHUB_USERNAME }}/你的镜像名
```

默认使用 `subtitle-group-diversion-site`，可以不改。

### 步骤3：推送触发构建

```bash
git add .
git commit -m "ci: Add GitHub Actions workflow for Docker Hub"
git push origin main
```

推送后，GitHub Actions会自动：
- ✅ 构建Docker镜像
- ✅ 推送到Docker Hub
- ✅ 支持多架构（AMD64 + ARM64）
- ✅ 自动缓存加速构建

## 构建触发条件

工作流会在以下情况触发：

| 事件 | 构建 | 推送 |
|------|------|------|
| push到main分支 | ✅ | ✅ |
| push标签 v* | ✅ | ✅ |
| Pull Request | ✅ | ❌（仅构建测试） |

## 生成的镜像标签

推送后会生成多个标签：

```
你的用户名/镜像名:latest      # 最新版本（main分支）
你的用户名/镜像名:main        # 分支名
你的用户名/镜像名:v1.0.0      # 语义化版本标签
你的用户名/镜像名:v1.0        # 主.次版本
```

## 使用构建好的镜像

```bash
# 拉取最新版
docker pull 你的用户名/subtitle-group-diversion-site:latest

# 运行
docker run -d \
  -p 5000:5000 \
  -e SECRET_KEY=你的密钥 \
  -e ADMIN_PASSWORD=你的密码 \
  你的用户名/subtitle-group-diversion-site:latest
```

或使用docker-compose：

```yaml
version: '3.8'
services:
  rss-torrent:
    image: 你的用户名/subtitle-group-diversion-site:latest
    ports:
      - "5000:5000"
    environment:
      - SECRET_KEY=${SECRET_KEY}
      - ADMIN_PASSWORD=${ADMIN_PASSWORD}
    volumes:
      - ./data:/app/data
      - ./uploads:/app/uploads
```

## 常见问题

### Q: 构建失败提示权限不足？
A: 检查Docker Hub Token权限是否为 **Read, Write, Delete**

### Q: 如何查看构建日志？
A: GitHub仓库 → Actions → 选择工作流运行 → 查看日志

### Q: 推送到Docker Hub后镜像在哪里？
A: https://hub.docker.com/r/你的用户名/镜像名

### Q: 如何只构建不推送？
A: 发起Pull Request时会构建但不推送

### Q: 支持哪些平台？
A: 目前支持 `linux/amd64` 和 `linux/arm64`（包括树莓派等ARM设备）

## 安全建议

1. **使用Token而非密码** ✅
2. **定期轮换Token**（每3-6个月）
3. **在Docker Hub限制Token权限**
4. **不要在代码中硬编码凭据**
