# 📚 API 文档

> 完整的 RESTful API 参考文档，帮助开发者对接 RSS 种子站点。

## 🔗 基础信息

- **Base URL**: `https://your-domain.com/api/v1`
- **RSS Feed**: `https://your-domain.com/rss.xml`
- **文档页面**: `https://your-domain.com/api/docs` (交互式文档)

---

## 🔐 认证方式

所有需要认证的 API 端点都必须提供 API Key。

### 获取 API Key

1. 注册账号并登录
2. 联系管理员将你的角色设置为 **发布员 (publisher)**
3. 访问 `/api-keys` 页面
4. 点击"创建 API Key"
5. **立即复制保存**（这是唯一一次完整显示）

### 传递 API Key

支持三种方式（优先级从高到低）：

#### 方式一：HTTP Header（推荐）

```http
GET /api/v1/torrents HTTP/1.1
Host: your-domain.com
X-API-Key: sgd_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 方式二：Query 参数

```
GET /api/v1/torrents?api_key=sgd_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 方式三：JSON Body（仅 POST 请求）

```json
{
  "api_key": "sgd_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "title": "电影名称"
}
```

---

## 📊 响应格式

所有响应均为 JSON，格式如下：

### 成功响应

```json
{
  "success": true,
  "data": { ... }
}
```

### 错误响应

```json
{
  "success": false,
  "error": "错误描述"
}
```

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误 |
| 401 | 未认证或 API Key 无效 |
| 403 | 权限不足（需要发布员/管理员） |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 🎯 API 端点

### 1. 获取站点统计

获取站点整体统计信息（无需认证）。

```
GET /api/v1/stats
```

#### 请求参数

无

#### 响应示例

```json
{
  "success": true,
  "data": {
    "total_torrents": 150,
    "total_users": 25,
    "total_size": 10737418240,
    "total_size_human": "10.00 GB",
    "recent_torrents_24h": 5,
    "site_name": "RSS种子站点",
    "rss_url": "https://your-domain.com/rss.xml"
  }
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| total_torrents | integer | 种子总数 |
| total_users | integer | 用户总数 |
| total_size | integer | 总文件大小（字节） |
| total_size_human | string | 格式化后的总大小 |
| recent_torrents_24h | integer | 最近24小时上传数 |
| site_name | string | 站点名称 |
| rss_url | string | RSS 订阅地址 |

---

### 2. 获取种子列表

获取种子列表，支持分页、分类过滤和搜索（需要认证）。

```
GET /api/v1/torrents
```

#### 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | integer | 否 | 1 | 页码 |
| per_page | integer | 否 | 20 | 每页数量（最大 100） |
| category | string | 否 | - | 分类过滤 |
| search | string | 否 | - | 搜索关键词（搜索标题和描述） |
| api_key | string | 是* | - | API Key（或通过 Header 传递） |

#### 响应示例

```json
{
  "success": true,
  "data": {
    "torrents": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "星际穿越 Interstellar (2014)",
        "description": "1080p BluRay REMUX",
        "category": "movie",
        "file_size": 4294967296,
        "file_size_human": "4096.00 MB",
        "created_at": "2024-01-15T10:30:00",
        "publisher_name": "movie_uploader",
        "download_url": "https://your-domain.com/download/550e8400-e29b-41d4-a716-446655440000"
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

#### 种子对象字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 种子唯一 ID (UUID) |
| title | string | 种子标题 |
| description | string | 种子描述 |
| category | string | 分类 |
| file_size | integer | 文件大小（字节） |
| file_size_human | string | 格式化后的文件大小 |
| created_at | string | 创建时间 (ISO 8601) |
| publisher_name | string | 发布者用户名 |
| download_url | string | 下载链接 |

#### 分页对象字段

| 字段 | 类型 | 说明 |
|------|------|------|
| page | integer | 当前页码 |
| per_page | integer | 每页数量 |
| total | integer | 总数 |
| total_pages | integer | 总页数 |

---

### 3. 获取单个种子

获取单个种子的详细信息（需要认证）。

```
GET /api/v1/torrents/{id}
```

#### 路径参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string | 是 | 种子 ID |

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| api_key | string | 是* | API Key（或通过 Header 传递） |

#### 响应示例

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "星际穿越 Interstellar (2014)",
    "description": "1080p BluRay REMUX",
    "category": "movie",
    "file_size": 4294967296,
    "file_size_human": "4096.00 MB",
    "created_at": "2024-01-15T10:30:00",
    "publisher_name": "movie_uploader",
    "download_url": "https://your-domain.com/download/550e8400-e29b-41d4-a716-446655440000"
  }
}
```

---

### 4. 上传种子

上传新的种子文件（需要 **发布员** 或 **管理员** 权限）。

```
POST /api/v1/torrents
```

#### 请求格式

`multipart/form-data`

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| torrent | file | 是 | `.torrent` 文件 |
| title | string | 是 | 种子标题 |
| description | string | 否 | 种子描述 |
| category | string | 否 | 分类（默认：general） |
| api_key | string | 是* | API Key（或通过 Header 传递） |

#### 支持的分组

- `general` - 综合
- `movie` - 电影
- `tv` - 电视剧
- `anime` - 动漫
- `music` - 音乐
- `game` - 游戏
- `software` - 软件
- `other` - 其他

#### 响应示例（成功）

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "星际穿越 Interstellar (2014)",
    "download_url": "https://your-domain.com/download/550e8400-e29b-41d4-a716-446655440000",
    "message": "Torrent uploaded successfully"
  }
}
```

#### 响应示例（错误）

```json
{
  "success": false,
  "error": "Title is required"
}
```

---

### 5. 获取分类列表

获取所有分类及其种子数量（无需认证）。

```
GET /api/v1/categories
```

#### 请求参数

无

#### 响应示例

```json
{
  "success": true,
  "data": [
    {
      "category": "movie",
      "count": 45
    },
    {
      "category": "tv",
      "count": 30
    },
    {
      "category": "anime",
      "count": 25
    },
    {
      "category": "music",
      "count": 15
    },
    {
      "category": "general",
      "count": 20
    }
  ]
}
```

---

### 6. 获取当前用户信息

获取当前认证用户的信息（需要认证）。

```
GET /api/v1/user
```

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| api_key | string | 是* | API Key（或通过 Header 传递） |

#### 响应示例

```json
{
  "success": true,
  "data": {
    "id": "user-uuid-string",
    "username": "yourname",
    "role": "publisher",
    "auth_type": "api_key"
  }
}
```

#### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| id | string | 用户唯一 ID |
| username | string | 用户名 |
| role | string | 用户角色（admin/publisher/user） |
| auth_type | string | 认证方式（api_key/session） |

---

## 💻 代码示例

### Python

```python
import requests

BASE_URL = "https://your-domain.com"
API_KEY = "sgd_your_api_key_here"

headers = {
    "X-API-Key": API_KEY
}

# 1. 获取站点统计
response = requests.get(f"{BASE_URL}/api/v1/stats")
print(response.json())

# 2. 获取种子列表（分页）
response = requests.get(
    f"{BASE_URL}/api/v1/torrents",
    headers=headers,
    params={
        "page": 1,
        "per_page": 20,
        "category": "movie"
    }
)
print(response.json())

# 3. 搜索种子
response = requests.get(
    f"{BASE_URL}/api/v1/torrents",
    headers=headers,
    params={"search": "星际穿越"}
)
print(response.json())

# 4. 获取单个种子
response = requests.get(
    f"{BASE_URL}/api/v1/torrents/550e8400-e29b-41d4-a716-446655440000",
    headers=headers
)
print(response.json())

# 5. 上传种子
with open("movie.torrent", "rb") as f:
    files = {"torrent": f}
    data = {
        "title": "电影名称",
        "description": "电影描述",
        "category": "movie"
    }
    response = requests.post(
        f"{BASE_URL}/api/v1/torrents",
        headers=headers,
        files=files,
        data=data
    )
    print(response.json())
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const BASE_URL = 'https://your-domain.com';
const API_KEY = 'sgd_your_api_key_here';

const headers = {
    'X-API-Key': API_KEY
};

// 获取种子列表
axios.get(`${BASE_URL}/api/v1/torrents`, { headers })
    .then(response => console.log(response.data))
    .catch(error => console.error(error.response.data));

// 上传种子
const form = new FormData();
form.append('torrent', fs.createReadStream('movie.torrent'));
form.append('title', '电影名称');
form.append('category', 'movie');

axios.post(`${BASE_URL}/api/v1/torrents`, form, {
    headers: {
        ...headers,
        ...form.getHeaders()
    }
})
.then(response => console.log(response.data))
.catch(error => console.error(error.response.data));
```

### cURL

```bash
# 获取统计（无需认证）
curl https://your-domain.com/api/v1/stats

# 获取种子列表
curl -H "X-API-Key: sgd_your_api_key_here" \
  "https://your-domain.com/api/v1/torrents?page=1&per_page=10"

# 搜索种子
curl -H "X-API-Key: sgd_your_api_key_here" \
  "https://your-domain.com/api/v1/torrents?search=星际穿越"

# 上传种子
curl -X POST \
  -H "X-API-Key: sgd_your_api_key_here" \
  -F "torrent=@movie.torrent" \
  -F "title=电影名称" \
  -F "description=电影描述" \
  -F "category=movie" \
  "https://your-domain.com/api/v1/torrents"
```

### PowerShell

```powershell
$BaseUrl = "https://your-domain.com"
$ApiKey = "sgd_your_api_key_here"
$Headers = @{"X-API-Key" = $ApiKey}

# 获取种子列表
Invoke-RestMethod -Uri "$BaseUrl/api/v1/torrents" -Headers $Headers

# 上传种子
$Form = @{
    torrent = Get-Item "movie.torrent"
    title = "电影名称"
    category = "movie"
}
Invoke-RestMethod -Uri "$BaseUrl/api/v1/torrents" -Method Post -Headers $Headers -Form $Form
```

---

## 🚀 对接流程

### 步骤 1：获取 API Key

1. 在站点注册账号
2. 联系管理员将你的角色设置为 **发布员**
3. 访问 `/api-keys` 页面
4. 创建 API Key 并**立即复制保存**

### 步骤 2：测试连接

使用 `/api/v1/stats` 接口测试（无需认证）：

```bash
curl https://your-domain.com/api/v1/stats
```

### 步骤 3：验证 API Key

```bash
curl -H "X-API-Key: sgd_your_api_key_here" \
  https://your-domain.com/api/v1/user
```

### 步骤 4：开发对接

参考上面的代码示例，根据你的需求对接：

- **自动发布工具**: 使用 `POST /api/v1/torrents` 上传种子
- **RSS 订阅器**: 订阅 `https://your-domain.com/rss.xml`
- **内容聚合**: 使用 `GET /api/v1/torrents` 获取列表

---

## 🔧 常见问题

### Q: 上传种子返回 403 错误？

A: 你的账号角色必须是 **publisher** 或 **admin**。联系管理员修改角色。

### Q: API Key 丢失了怎么办？

A: 在 `/api-keys` 页面删除旧 Key，重新创建一个新的。

### Q: 如何批量上传种子？

A: 循环调用 `POST /api/v1/torrents` 接口，每次上传一个文件。

### Q: 支持的最大文件大小？

A: 默认 16MB，可通过环境变量 `MAX_FILE_SIZE` 修改。

### Q: 支持哪些文件格式？

A: 仅支持 `.torrent` 文件。

---

## 📞 支持

如有问题，请：

1. 查看交互式文档：`https://your-domain.com/api/docs`
2. 提交 Issue：https://github.com/zzzwannasleep/SubtitleGroupDiversionSiteLite/issues
3. 查看项目 README：[README.md](../README.md)

---

**最后更新**: 2024-01-15
