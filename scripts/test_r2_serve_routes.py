"""R2 直出路由端到端测试：/rss.xml 与 /t/<id>.torrent（自部署 Docker 用）。

先 `npm run dev`（.dev.vars 里 ADMIN_PASSWORD=adminpw），再跑本脚本。
Cloudflare 部署这两个路径由 R2 公开域名直出、不进 Worker，不受影响；
自部署时 Worker 同域名直出，响应头须与写入 R2 时的 httpMetadata 一致。
"""

import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787"
RUN = uuid.uuid4().hex[:6]
TORRENT = b"d8:announce3:abc4:infod4:name4:teste" + b"e"
FILENAME = "直出测试 01.torrent"


def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def call(opener, path, data=None, headers=None, method=None):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {}, method=method)
    try:
        with opener.open(req) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def multipart(title, filename, content):
    b = uuid.uuid4().hex
    body = (
        f'--{b}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'
        f'--{b}\r\nContent-Disposition: form-data; name="torrent"; filename="{filename}"\r\n'
        "Content-Type: application/x-bittorrent\r\n\r\n"
    ).encode() + content + f"\r\n--{b}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={b}"}


# Secure cookie 在 http://127.0.0.1 下也要能带上
http.cookiejar.DefaultCookiePolicy.return_ok_secure = lambda self, cookie, request: True

# 管理员登录并上传一个种子
admin, _ = client()
status, body, headers = call(admin, "/login", b"username=admin&password=adminpw",
                             {"Content-Type": "application/x-www-form-urlencoded"})
assert status == 200 and "欢迎回来" in body.decode(), (status, body[:300])

data, h = multipart(f"直出路由 {RUN}", FILENAME, TORRENT)
status, body, _ = call(admin, "/upload", data, h)
assert status == 200 and "种子发布成功" in body.decode(), (status, body[:300])

# 从首页拿种子 ID（admin 页也有列表；用 index 更省事，标题带随机后缀）
status, body, _ = call(admin, "/")
assert status == 200
import re
m = re.search(r"href=\"[^\"]*/t/([0-9a-f-]+)\.torrent\"", body.decode())
assert m, "首页没有下载链接"
tid = m.group(1)

# /rss.xml：200、正确 Content-Type、含刚发布的标题、max-age=60
status, body, headers = call(admin, "/rss.xml")
assert status == 200, status
assert headers["Content-Type"].startswith("application/rss+xml"), headers["Content-Type"]
assert "max-age=60" in headers["Cache-Control"], headers["Cache-Control"]
text = body.decode()
assert f"直出路由 {RUN}" in text, text[:300]
assert f"/t/{tid}.torrent" in text, text[:300]

# /t/<id>.torrent：字节与上传内容一致，响应头与 R2 写入时一致
status, body, headers = call(admin, f"/t/{tid}.torrent")
assert status == 200 and body == TORRENT, (status, body[:50])
assert headers["Content-Type"] == "application/x-bittorrent", headers["Content-Type"]
assert "attachment" in headers.get("Content-Disposition", ""), headers.get("Content-Disposition")
assert "max-age=31536000" in headers["Cache-Control"], headers["Cache-Control"]

# 不存在的种子 → 404
assert call(admin, f"/t/{uuid.uuid4()}.torrent")[0] == 404

# 删除后 → 404，且 RSS 里不再出现
assert "种子已删除" in call(admin, f"/admin/delete_torrent/{tid}")[1].decode()
assert call(admin, f"/t/{tid}.torrent")[0] == 404
assert f"直出路由 {RUN}" not in call(admin, "/rss.xml")[1].decode()

print("r2 serve routes test OK")
