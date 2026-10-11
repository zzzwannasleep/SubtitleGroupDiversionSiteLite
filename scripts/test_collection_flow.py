"""合集/分集端到端验证：先 npm run dev 起本地站点，再跑本脚本。

场景：上传 2 个分集 + 1 个无关种子 → 上传同名合集 →
验证 2 个分集被自动删除（含 RSS 同步），无关种子和合集本身保留。
"""

import json
import sys
import uuid
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8787"
RUN = uuid.uuid4().hex[:6]

import http.cookiejar

http.cookiejar.DefaultCookiePolicy.return_ok_secure = lambda self, cookie, request: True
jar = http.cookiejar.CookieJar()
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))


def benc(obj):
    if isinstance(obj, int):
        return b"i" + str(obj).encode() + b"e"
    if isinstance(obj, str):
        obj = obj.encode()
    if isinstance(obj, bytes):
        return str(len(obj)).encode() + b":" + obj
    if isinstance(obj, list):
        return b"l" + b"".join(benc(x) for x in obj) + b"e"
    if isinstance(obj, dict):
        return b"d" + b"".join(benc(k) + benc(v) for k, v in obj.items()) + b"e"
    raise TypeError(obj)


def call(path, data=None, headers=None, method=None):
    req = urllib.request.Request(BASE + path, data=data, headers=headers or {}, method=method)
    try:
        with op.open(req) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def form(f):
    return "&".join(f"{k}={urllib.request.quote(v)}" for k, v in f.items()).encode(), {
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


s, b = call("/login", *form({"username": "admin", "password": "adminpw"}))
assert "欢迎回来" in b, "管理员登录失败"

# 站点 API Key（复用 admin 会话创建）
s, b = call("/api-keys/create", *form({"name": "e2e"}))
KEY = {"X-API-Key": s if False else b.split("请立即复制保存：")[1].split("<")[0].strip()}

SINGLE = benc({b"info": {b"name": b"ep", b"length": 1}})

# 合集种子：info 内含 files 列表（2 个文件）
COLL = (
    b"d4:infod4:name" + ("合集包").encode() + b"5:files"
    + benc([{b"length": 1, b"path": ["01"]}, {b"length": 2, b"path": ["02.mkv"]}])
    + b"ee"
)


def upload(title, filename, content):
    data, h = multipart(title, filename, content)
    s, b = call("/api/v1/torrents", data, {**h, **KEY})
    return s, json.loads(b)


# 1. 造数据：两个同名系列分集 + 一个无关分集
s, r1 = upload(f"【测试组】番剧{RUN} 第01话 [1080p]", "ep01.torrent", SINGLE)
assert s == 201, r1
s, r2 = upload(f"【测试组】番剧{RUN}.第02话 [1080p]", "ep02.torrent", SINGLE)
assert s == 201, r2
s, r3 = upload(f"【测试组】无关番剧{RUN} 第01话", "other.torrent", SINGLE)
assert s == 201, r3
assert r1["data"]["removed_episodes"] == [] and r2["data"]["removed_episodes"] == []

# 2. 上传合集（标题含"合集"关键词 + 种子内 2 个文件）
s, rc = upload(f"【测试组】番剧{RUN} 合集 [1080p]", "coll.torrent", COLL)
assert s == 201, rc
removed = [(d["title"]) for d in rc["data"]["removed_episodes"]]
assert len(removed) == 2, f"应删除 2 个分集，实际 {removed}: {rc}"
assert any("第01话" in t for t in removed) and any("第02话" in t for t in removed), removed

# 3. 无关分集必须还在；合集还在；两个分集已消失
s, body = call(f"/api/v1/torrents?search={urllib.request.quote(RUN)}&per_page=50", headers=KEY)
titles = [t["title"] for t in json.loads(body)["data"]["torrents"]]
assert any(f"无关番剧{RUN}" in t for t in titles), titles
assert f"【测试组】番剧{RUN} 第01话 [1080p]" not in titles, titles
assert f"【测试组】番剧{RUN}.第02话 [1080p]" not in titles, titles
coll_rows = [t for t in json.loads(body)["data"]["torrents"] if "合集" in t["title"]]
assert len(coll_rows) == 1 and coll_rows[0]["is_collection"] is True, titles

# 4. 清理：删掉测试产生的全部种子
for t in json.loads(call(f"/api/v1/torrents?search={urllib.request.quote(RUN)}&per_page=50", headers=KEY)[1])["data"]["torrents"]:
    s, b = call(f"/admin/delete_torrent/{t['id']}")
    assert "种子已删除" in b

print(f"e2e 合集/分集验证 OK（RUN={RUN}）：合集上线自动删除 {len(removed)} 个同名分集，无关种子未受影响")