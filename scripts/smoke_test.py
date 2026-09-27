"""本地端到端冒烟测试：先 `npm run dev`（.dev.vars 里 ADMIN_PASSWORD=adminpw），再跑本脚本。

用法: python scripts/smoke_test.py [base_url]
"""

import http.cookiejar
import json
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787"
RUN = uuid.uuid4().hex[:6]  # 标题带随机后缀，重复跑互不干扰
TORRENT = b"d8:announce3:abc4:infod4:name4:teste" + b"e"


def client():
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar)), jar


def call(opener, path, data=None, headers=None, method=None):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {}, method=method)
    try:
        with opener.open(req) as r:
            return r.status, r.read().decode(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(), e.headers


def form(fields):
    return "&".join(f"{k}={urllib.request.quote(v)}" for k, v in fields.items()).encode(), {
        "Content-Type": "application/x-www-form-urlencoded"
    }


def multipart(title, filename, content):
    b = uuid.uuid4().hex
    body = (
        f'--{b}\r\nContent-Disposition: form-data; name="title"\r\n\r\n{title}\r\n'
        f'--{b}\r\nContent-Disposition: form-data; name="torrent"; filename="{filename}"\r\n'
        "Content-Type: application/x-bittorrent\r\n\r\n"
    ).encode() + content + f"\r\n--{b}--\r\n".encode()
    return body, {"Content-Type": f"multipart/form-data; boundary={b}"}


def r2_get(key):
    out = subprocess.run(
        f"npx wrangler r2 object get sgds/{key} --local --pipe",
        shell=True, capture_output=True,
    )
    return out.stdout.decode("utf-8", "replace")


# Secure cookie 在 http://127.0.0.1 下也要能带上
http.cookiejar.DefaultCookiePolicy.return_ok_secure = lambda self, cookie, request: True

anon, _ = client()
status, body, _ = call(anon, "/")
assert status == 200 and "RSS 自动下载" in body, status
assert call(anon, "/admin")[0] == 200  # 被重定向到登录页
assert call(anon, "/api/v1/user")[0] == 401
assert call(anon, "/api/v1/nope")[0] == 404
assert json.loads(call(anon, "/api/v1/stats")[1])["success"]

# 管理员登录（密码来自 ADMIN_PASSWORD）
admin, jar = client()
status, body, _ = call(admin, "/login", *form({"username": "admin", "password": "wrong"}))
assert "用户名或密码错误" in body
status, body, headers = call(admin, "/login", *form({"username": "admin", "password": "adminpw"}))
assert "欢迎回来" in body and "管理后台" in body, body[:500]
cookie = next(c for c in jar if c.name == "s")
assert cookie.secure and cookie.has_nonstandard_attr("HttpOnly")

# 伪造 session 无效
forged, fjar = client()
fjar.set_cookie(http.cookiejar.Cookie(0, "s", cookie.value[:-4] + "abcd", None, False, "127.0.0.1",
                                      False, False, "/", True, False, None, False, None, None, {}))
assert "管理后台" not in call(forged, "/")[1]

# 网页上传：非法文件被拒，合法文件成功
status, body, _ = call(admin, "/upload", *multipart("坏文件", "x.txt", b"hello"))
assert "仅支持 .torrent 文件" in body
status, body, _ = call(admin, "/upload", *multipart(f"第一集 [1080p] {RUN}", "测试 01.torrent", TORRENT))
assert "种子发布成功" in body and f"第一集 [1080p] {RUN}" in body, body[:500]

rss = r2_get("rss.xml")
assert f"第一集 [1080p] {RUN}" in rss and "files.example.com/t/" in rss, rss[:500]
item = ET.fromstring(rss).find("channel/item")
assert item.find("enclosure").get("type") == "application/x-bittorrent" and item.find("pubDate").text.endswith("+0800")

# API Key
status, body, _ = call(admin, "/api-keys/create", *form({"name": "ci"}))
key = body.split("请立即复制保存：")[1].split("<")[0].strip()
assert key.startswith("sgd_")
k = {"X-API-Key": key}
assert json.loads(call(anon, "/api/v1/user", headers=k)[1])["data"]["auth_type"] == "api_key"
assert call(anon, "/api/v1/user", headers={"X-API-Key": "sgd_bad"})[0] == 401

data, h = multipart(f"第二集 {RUN}", "ep02.torrent", TORRENT)
status, body, _ = call(anon, "/api/v1/torrents", data, {**h, **k})
assert status == 201, body
tid = json.loads(body)["data"]["id"]
listing = json.loads(call(anon, "/api/v1/torrents?search=" + urllib.request.quote(RUN) + "&per_page=5", headers=k)[1])
assert listing["data"]["torrents"][0]["id"] == tid and all(RUN in t["title"] for t in listing["data"]["torrents"])
assert json.loads(call(anon, f"/api/v1/torrents/{tid}", headers=k)[1])["data"]["title"] == f"第二集 {RUN}"
assert f"第二集 {RUN}" in r2_get("rss.xml")
assert r2_get(f"t/{tid}.torrent").encode() == TORRENT

# 其它页面能渲染
assert "API Key" in call(admin, "/api-keys")[1] and key[:20] in call(admin, "/api-keys")[1]
assert "files.example.com/rss.xml" in call(anon, "/api/docs")[1]
status, body, _ = call(admin, "/admin")
assert status == 200 and "RSS信息" in body and "files.example.com/rss.xml" in body

# 普通用户：注册（PBKDF2）、登录、没有上传权限
user, _ = client()
name = "u" + uuid.uuid4().hex[:8]
call(user, "/register", *form({"username": name, "password": "pw123456"}))
assert "用户名已存在" in call(user, "/register", *form({"username": name, "password": "x"}))[1]
assert "欢迎回来" in call(user, "/login", *form({"username": name, "password": "pw123456"}))[1]
assert "需要发布员权限" in call(user, "/upload")[1]
data, h = multipart("t", "a.torrent", TORRENT)
ukey_body = call(user, "/api-keys/create", *form({"name": "u"}))[1]
ukey = ukey_body.split("请立即复制保存：")[1].split("<")[0].strip()
assert call(anon, "/api/v1/torrents", data, {**h, "X-API-Key": ukey})[0] == 403
uid = json.loads(call(anon, "/api/v1/user", headers={"X-API-Key": ukey})[1])["data"]["id"]
assert "不能修改默认管理员权限" in call(admin, "/admin/set_role/admin/user")[1]
assert f"已将 {name} 设置为 publisher" in call(admin, f"/admin/set_role/{uid}/publisher")[1]
data, h = multipart(f"第三集 {RUN}", "ep03.torrent", TORRENT)
status, body, _ = call(anon, "/api/v1/torrents", data, {**h, "X-API-Key": ukey})
assert status == 201, body
tid3 = json.loads(body)["data"]["id"]
assert "种子已删除" in call(admin, f"/admin/delete_torrent/{tid3}")[1]

# 管理员删除种子后 RSS 同步
status, body, _ = call(admin, f"/admin/delete_torrent/{tid}")
assert "种子已删除" in body
assert f"第二集 {RUN}" not in r2_get("rss.xml")
assert call(admin, "/logout")[0] == 200 and "管理后台" not in call(admin, "/")[1]

print("smoke test OK")
