# 📚 API 文档

> 简单的 RSS 种子站点 API，仅提供种子上传和下载功能。

## 🔗 基础信息

- **Base URL**: `https://your-domain.com/api/v1`
- **RSS Feed**: `https://your-domain.com/rss.xml`
- **文档页面**: `https://your-domain.com/api/docs`

---

## 🔐 认证方式

需要认证的 API 必须提供 API Key。

### 获取 API Key

1. 注册账号并登录
2. 联系管理员设置为 **发布员**
3. 访问 `/api-keys` 页面创建 Key
4. **立即复制保存**（只显示一次）

### 传递 API Key

**方式一：HTTP Header（推荐）**

```http
X-API-Key: sgd_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**方式二：Query 参数**

```
?api_key=sgd_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 📊 响应格式

### 成功

```json
{
  "success": true,
  "data": { ... }
}
```

### 错误

```json
{
  "success": false,
  "error": "错误描述"
}
```

### 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 参数错误 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 404 | 不存在 |
| 500 | 服务器错误 |

---

## 🎯 API 端点

### 1. 获取站点统计

```
GET /api/v1/stats
```

无需认证。

**响应：**

```json
{
  "success": true,
  "data": {
    "total_torrents": 150,
    "total_users": 25,
    "total_size_human": "10.00 GB",
    "recent_torrents_24h": 5,
    "rss_url": "https://your-domain.com/rss.xml"
  }
}
```

---

### 2. 获取种子列表

```
GET /api/v1/torrents
```

需要认证。

**参数：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| page | integer | 否 | 1 | 页码 |
| per_page | integer | 否 | 20 | 每页数量（最大100） |
| search | string | 否 | - | 搜索标题 |
| api_key | string | 是* | - | API Key |

**响应：**

```json
{
  "success": true,
  "data": {
    "torrents": [
      {
        "id": "uuid",
        "title": "电影名称",
        "file_size_human": "2048.00 MB",
        "created_at": "2024-01-15T10:30:00",
        "publisher_name": "username",
        "download_url": "https://your-domain.com/download/uuid"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 150,
      "total_pages": 8
    }
  }
}
```

---

### 3. 获取单个种子

```
GET /api/v1/torrents/{id}
```

需要认证。

**路径参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 种子ID |

---

### 4. 上传种子

```
POST /api/v1/torrents
```

需要 **发布员** 或 **管理员** 权限。

**格式：** `multipart/form-data`

**参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| torrent | file | 是 | `.torrent` 文件 |
| title | string | 是 | 种子标题 |
| api_key | string | 是* | API Key |

**响应：**

```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "title": "电影名称",
    "download_url": "https://your-domain.com/download/uuid",
    "message": "Torrent uploaded successfully"
  }
}
```

---

### 5. 获取当前用户

```
GET /api/v1/user
```

需要认证。

**响应：**

```json
{
  "success": true,
  "data": {
    "id": "user-uuid",
    "username": "yourname",
    "role": "publisher"
  }
}
```

---

## 💻 代码示例

### Python

```python
import requests

BASE_URL = "https://your-domain.com"
API_KEY = "sgd_your_api_key"

headers = {"X-API-Key": API_KEY}

# 获取统计
r = requests.get(f"{BASE_URL}/api/v1/stats")
print(r.json())

# 获取种子列表
r = requests.get(f"{BASE_URL}/api/v1/torrents", headers=headers)
print(r.json())

# 上传种子
with open("movie.torrent", "rb") as f:
    files = {"torrent": f}
    data = {"title": "电影名称"}
    r = requests.post(
        f"{BASE_URL}/api/v1/torrents",
        headers=headers,
        files=files,
        data=data
    )
    print(r.json())
```

### cURL

```bash
# 获取统计
curl https://your-domain.com/api/v1/stats

# 获取种子列表
curl -H "X-API-Key: sgd_your_api_key" \
  "https://your-domain.com/api/v1/torrents?page=1&per_page=10"

# 上传种子
curl -X POST \
  -H "X-API-Key: sgd_your_api_key" \
  -F "torrent=@movie.torrent" \
  -F "title=电影名称" \
  "https://your-domain.com/api/v1/torrents"
```

---

## 🚀 对接流程

1. **注册账号** → 联系管理员设为 **发布员**
2. **创建 API Key** → 访问 `/api-keys`
3. **复制保存 Key** → 只显示一次
4. **开始对接** → 参考上方代码示例

---

## ❓ 常见问题

### Q: 上传返回 403？

A: 需要 **publisher** 或 **admin** 角色，联系管理员。

### Q: Key 丢失了？

A: 删除旧 Key，重新创建。

### Q: 支持哪些文件？

A: 仅 `.torrent` 文件，最大 16MB。

---

**最后更新**: 2024
