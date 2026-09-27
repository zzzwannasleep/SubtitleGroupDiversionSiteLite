"""RSS 种子站 —— Cloudflare Python Worker 版

Worker 只处理页面、登录、上传和 API。rss.xml 与 .torrent 放在 R2，
经 R2 自定义域名 + CDN 分发，订阅端轮询不消耗 Worker 请求额度。
每次发布/删除都会重建 rss.xml 并清掉它的 CDN 缓存，新种子立即可见。
"""

import base64
import hashlib
import hmac
import json
import re
import secrets
import traceback
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import parse_qs, quote, urlsplit

import jinja2
from js import Object, Uint8Array, crypto
from pyodide.ffi import to_js
from workers import File, Response, WorkerEntrypoint, fetch

CST = timezone(timedelta(hours=8))
MAX_TORRENT_SIZE = 16 * 1024 * 1024
PBKDF2_ITERATIONS = 100_000  # workerd 的 WebCrypto 上限
RSS_KEY = "rss.xml"

templates = jinja2.Environment(
    loader=jinja2.FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=True,
)


def now():
    return datetime.now(CST).isoformat()


# ==================== 密码 ====================

async def pbkdf2(password, salt, iterations):
    key = await crypto.subtle.importKey(
        "raw", to_js(password.encode()), "PBKDF2", False, to_js(["deriveBits"])
    )
    params = to_js(
        {"name": "PBKDF2", "hash": "SHA-256", "salt": to_js(salt), "iterations": iterations},
        dict_converter=Object.fromEntries,
    )
    bits = await crypto.subtle.deriveBits(params, key, 256)
    return bytes(Uint8Array.new(bits).to_py())


async def hash_password(password):
    salt = secrets.token_bytes(16)
    dk = await pbkdf2(password, salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


async def check_password(stored, password):
    try:
        algo, iterations, salt, dk = stored.split("$")
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    got = await pbkdf2(password, bytes.fromhex(salt), int(iterations))
    return hmac.compare_digest(got.hex(), dk)


# ==================== 请求上下文 ====================

class Ctx:
    def __init__(self, request, env):
        self.request = request
        self.env = env
        self.method = request.method
        parts = urlsplit(request.url)
        self.path = parts.path
        self.args = {k: v[0] for k, v in parse_qs(parts.query).items()}
        self.origin = f"{parts.scheme}://{parts.netloc}"
        self.public_url = self.var("PUBLIC_URL").rstrip("/")
        self.session = self._load_session()
        self.session_dirty = False
        self._user = False

    def var(self, name):
        value = getattr(self.env, name, None)
        return value if isinstance(value, str) else ""

    # ---------- session：HMAC 签名的 cookie ----------

    def _sign(self, data):
        return hmac.new(self.var("SECRET_KEY").encode(), data, hashlib.sha256).hexdigest()

    def _load_session(self):
        m = re.search(r"(?:^|;\s*)s=([^;]+)", self.request.headers.get("cookie") or "")
        if not m or not self.var("SECRET_KEY"):
            return {}
        payload, _, sig = m.group(1).partition(".")
        try:
            data = base64.urlsafe_b64decode(payload)
            if hmac.compare_digest(self._sign(data), sig):
                return json.loads(data)
        except ValueError:
            pass
        return {}

    def _session_cookie(self):
        if not self.session:
            return "s=; Path=/; Max-Age=0; HttpOnly; Secure; SameSite=Strict"
        data = json.dumps(self.session, separators=(",", ":")).encode()
        value = base64.urlsafe_b64encode(data).decode() + "." + self._sign(data)
        # SameSite=Strict：后台的 GET 操作链接不会被跨站请求带上 cookie（防 CSRF）
        return f"s={value}; Path=/; Max-Age=2592000; HttpOnly; Secure; SameSite=Strict"

    def flash(self, message, category="info"):
        self.session.setdefault("_flashes", []).append([category, message])
        self.session_dirty = True

    def get_flashed_messages(self, with_categories=False):
        flashes = self.session.pop("_flashes", [])
        if flashes:
            self.session_dirty = True
        return [tuple(f) for f in flashes] if with_categories else [f[1] for f in flashes]

    # ---------- D1 ----------

    async def all(self, sql, *params):
        return (await self.env.DB.prepare(sql).bind(*params).all()).results

    async def one(self, sql, *params):
        rows = await self.all(sql, *params)
        return rows[0] if rows else None

    async def run(self, sql, *params):
        await self.env.DB.prepare(sql).bind(*params).run()

    async def user(self):
        """当前登录用户，每次从库里取，角色变更即时生效"""
        if self._user is False:
            uid = self.session.get("user_id")
            self._user = uid and await self.one("SELECT * FROM users WHERE id = ?", uid)
        return self._user

    # ---------- 响应 ----------

    def url_for(self, name, **kw):
        if name == "rss_feed":
            return f"{self.public_url}/{RSS_KEY}"
        if name == "download":
            return f"{self.public_url}/t/{kw['torrent_id']}.torrent"
        if name == "set_role":
            return f"/admin/set_role/{kw['user_id']}/{kw['role']}"
        if name == "delete_torrent":
            return f"/admin/delete_torrent/{kw['torrent_id']}"
        if name == "delete_api_key":
            return f"/api-keys/delete/{kw['key_id']}"
        return PAGE_URLS[name]

    def render(self, name, status=200, **context):
        html = templates.get_template(name).render(
            request=self,
            session=self.session,
            url_for=self.url_for,
            get_flashed_messages=self.get_flashed_messages,
            **context,
        )
        return Response(html, status=status, headers={"Content-Type": "text/html; charset=utf-8"})

    def redirect(self, name_or_path):
        path = PAGE_URLS.get(name_or_path, name_or_path)
        return Response("", status=302, headers={"Location": path})

    def finish(self, response):
        if self.session_dirty:
            # response.headers 是只读副本，要改底层 JS Headers
            response.js_object.headers.append("Set-Cookie", self._session_cookie())
        return response


def json_response(data, status=200):
    return Response(
        json.dumps(data, ensure_ascii=False),
        status=status,
        headers={"Content-Type": "application/json; charset=utf-8"},
    )


def field(form, name):
    """取表单文本字段；缺失或传成文件时返回空串"""
    value = form.get(name)
    return value if isinstance(value, str) else ""


def torrent_json(c, t):
    return {
        "id": t["id"],
        "title": t["title"],
        "file_size": t["file_size"],
        "file_size_human": f"{t['file_size'] / 1024 / 1024:.2f} MB",
        "created_at": t["created_at"],
        "publisher_name": t["publisher_name"],
        "download_url": c.url_for("download", torrent_id=t["id"]),
    }


# ==================== 权限 ====================

def login_required(role=None):
    def deco(handler):
        async def wrapper(c, **kw):
            user = await c.user()
            if not user:
                c.flash("请先登录", "warning")
                return c.redirect("login")
            if role == "admin" and user["role"] != "admin":
                c.flash("需要管理员权限", "danger")
                return c.redirect("index")
            if role == "publisher" and user["role"] not in ("admin", "publisher"):
                c.flash("需要发布员权限", "danger")
                return c.redirect("index")
            return await handler(c, **kw)
        return wrapper
    return deco


def api_auth(publisher=False):
    def deco(handler):
        async def wrapper(c, **kw):
            api_key = c.request.headers.get("x-api-key") or c.args.get("api_key")
            if api_key:
                user = await c.one(
                    "SELECT u.* FROM users u JOIN api_keys k ON u.id = k.user_id "
                    "WHERE k.key = ? AND k.is_active = 1",
                    api_key,
                )
                if not user:
                    return json_response({"success": False, "error": "Invalid API key"}, 401)
                await c.run("UPDATE api_keys SET last_used = ? WHERE key = ?", now(), api_key)
                c.auth_type = "api_key"
            else:
                user = await c.user()
                if not user:
                    return json_response({"success": False, "error": "Authentication required"}, 401)
                c.auth_type = "session"
            if publisher and user["role"] not in ("admin", "publisher"):
                return json_response(
                    {"success": False, "error": "Publisher or admin role required"}, 403
                )
            c.current_user = user
            return await handler(c, **kw)
        return wrapper
    return deco


# ==================== 种子 / RSS / R2 ====================

async def purge_cache(c, urls):
    """清 CDN 缓存。没配 CF_API_TOKEN/CF_ZONE_ID 时跳过，靠 rss.xml 的 max-age=60 兜底"""
    token, zone = c.var("CF_API_TOKEN"), c.var("CF_ZONE_ID")
    if not (token and zone):
        return
    # 清缓存失败不能让已经落库的发布报错（发布员会重试、产生重复种子），只记日志
    try:
        resp = await fetch(
            f"https://api.cloudflare.com/client/v4/zones/{zone}/purge_cache",
            method="POST",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            body=json.dumps({"files": urls}),
        )
        if resp.status != 200:
            print("purge_cache failed:", resp.status, await resp.text())
    except Exception as e:
        print("purge_cache error:", e)


async def publish_rss(c, extra_purge=()):
    torrents = await c.all("SELECT * FROM torrents ORDER BY created_at DESC LIMIT 50")
    rss_url = c.url_for("rss_feed")

    rss = ET.Element("rss", {"version": "2.0", "xmlns:atom": "http://www.w3.org/2005/Atom"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = c.var("SITE_NAME") or "RSS种子站点"
    ET.SubElement(channel, "link").text = c.origin + "/"
    ET.SubElement(channel, "description").text = "RSS种子订阅"
    ET.SubElement(channel, "language").text = "zh-CN"
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(datetime.now(CST))
    ET.SubElement(
        channel, "atom:link", {"href": rss_url, "rel": "self", "type": "application/rss+xml"}
    )
    for t in torrents:
        url = c.url_for("download", torrent_id=t["id"])
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = t["title"]
        ET.SubElement(item, "link").text = url
        ET.SubElement(item, "pubDate").text = format_datetime(datetime.fromisoformat(t["created_at"]))
        ET.SubElement(item, "guid", {"isPermaLink": "false"}).text = t["id"]
        ET.SubElement(
            item,
            "enclosure",
            {"url": url, "length": str(t["file_size"]), "type": "application/x-bittorrent"},
        )

    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(rss, encoding="unicode")
    await c.env.BUCKET.put(
        RSS_KEY,
        xml.encode(),
        {
            "httpMetadata": {
                "contentType": "application/rss+xml; charset=utf-8",
                "cacheControl": "public, max-age=60",
            }
        },
    )
    await purge_cache(c, [rss_url, *extra_purge])


async def save_torrent(c, form, user):
    """校验并保存上传的种子，返回 (torrent_id, None) 或 (None, 错误信息)"""
    title = field(form, "title").strip()
    file = form.get("torrent")
    if not isinstance(file, File) or not file.name:
        return None, "没有选择文件"
    if not title:
        return None, "标题不能为空"
    filename = file.name.replace("\\", "/").rsplit("/", 1)[-1]
    if not filename.lower().endswith(".torrent"):
        return None, "仅支持 .torrent 文件"
    if file.size > MAX_TORRENT_SIZE:
        return None, "文件超过 16MB"
    data = await file.bytes()
    if not data.startswith(b"d"):  # bencode 字典
        return None, "不是有效的种子文件"

    torrent_id = str(uuid.uuid4())
    key = f"t/{torrent_id}.torrent"
    await c.env.BUCKET.put(
        key,
        data,
        {
            "httpMetadata": {
                # 固定类型 + attachment，防止借公开桶托管 HTML 之类的内容
                "contentType": "application/x-bittorrent",
                "contentDisposition": f"attachment; filename*=UTF-8''{quote(filename)}",
                "cacheControl": "public, max-age=31536000, immutable",
            }
        },
    )
    await c.run(
        "INSERT INTO torrents (id, title, filename, original_filename, file_size, "
        "created_at, publisher_id, publisher_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        torrent_id, title, key, filename, len(data), now(), user["id"], user["username"],
    )
    await publish_rss(c)
    return torrent_id, None


# ==================== 页面路由 ====================

async def index(c):
    torrents = await c.all("SELECT * FROM torrents ORDER BY created_at DESC")
    return c.render("index.html", torrents=torrents)


async def register(c):
    if c.method == "GET":
        return c.render("register.html")
    form = await c.request.form_data()
    username = field(form, "username").strip()
    password = field(form, "password")
    if not username or not password:
        c.flash("用户名和密码不能为空", "danger")
        return c.redirect("register")
    if await c.one("SELECT 1 FROM users WHERE username = ?", username):
        c.flash("用户名已存在", "danger")
        return c.redirect("register")
    await c.run(
        "INSERT INTO users (id, username, password, role, created_at) VALUES (?, ?, ?, 'user', ?)",
        str(uuid.uuid4()), username, await hash_password(password), now(),
    )
    c.flash("注册成功，请登录", "success")
    return c.redirect("login")


async def login(c):
    if c.method == "GET":
        return c.render("login.html")
    form = await c.request.form_data()
    username = field(form, "username")
    password = field(form, "password")
    user = await c.one("SELECT * FROM users WHERE username = ?", username)
    if user and user["id"] == "admin":
        # 默认管理员的密码以 ADMIN_PASSWORD secret 为准，改 secret 即改密码
        admin_password = c.var("ADMIN_PASSWORD")
        ok = bool(admin_password) and hmac.compare_digest(password.encode(), admin_password.encode())
    else:
        ok = bool(user) and await check_password(user["password"], password)
    if not ok:
        c.flash("用户名或密码错误", "danger")
        return c.redirect("login")
    c.session = {"user_id": user["id"], "username": user["username"], "role": user["role"]}
    c.flash(f"欢迎回来，{username}！", "success")
    return c.redirect("index")


async def logout(c):
    c.session = {}
    c.flash("已退出登录", "info")
    return c.redirect("index")


@login_required("publisher")
async def upload(c):
    if c.method == "GET":
        return c.render("upload.html")
    torrent_id, error = await save_torrent(c, await c.request.form_data(), await c.user())
    if error:
        c.flash(error, "danger")
        return c.redirect("upload")
    c.flash("种子发布成功！", "success")
    return c.redirect("index")


@login_required("admin")
async def admin(c):
    users = await c.all("SELECT * FROM users ORDER BY created_at DESC")
    torrents = await c.all("SELECT * FROM torrents ORDER BY created_at DESC")
    return c.render("admin.html", users=users, torrents=torrents)


@login_required("admin")
async def set_role(c, user_id, role):
    if role not in ("user", "publisher", "admin"):
        c.flash("无效的角色", "danger")
        return c.redirect("admin")
    user = await c.one("SELECT * FROM users WHERE id = ?", user_id)
    if not user:
        c.flash("用户不存在", "danger")
        return c.redirect("admin")
    if user["username"] == "admin" and role != "admin":
        c.flash("不能修改默认管理员权限", "danger")
        return c.redirect("admin")
    await c.run("UPDATE users SET role = ? WHERE id = ?", role, user_id)
    c.flash(f"已将 {user['username']} 设置为 {role}", "success")
    return c.redirect("admin")


@login_required("admin")
async def delete_torrent(c, torrent_id):
    torrent = await c.one("SELECT * FROM torrents WHERE id = ?", torrent_id)
    if not torrent:
        c.flash("种子不存在", "danger")
        return c.redirect("admin")
    await c.env.BUCKET.delete(torrent["filename"])
    await c.run("DELETE FROM torrents WHERE id = ?", torrent_id)
    await publish_rss(c, [c.url_for("download", torrent_id=torrent_id)])
    c.flash("种子已删除", "success")
    return c.redirect("admin")


@login_required("admin")
async def rebuild_rss(c):
    """迁移数据或改了 PUBLIC_URL 之后，手动重建 rss.xml"""
    await publish_rss(c)
    c.flash("RSS 已重建", "success")
    return c.redirect("admin")


@login_required()
async def api_keys(c):
    keys = await c.all(
        "SELECT * FROM api_keys WHERE user_id = ? ORDER BY created_at DESC",
        c.session["user_id"],
    )
    return c.render("api_keys.html", api_keys=keys)


@login_required()
async def create_api_key(c):
    form = await c.request.form_data()
    api_key = "sgd_" + secrets.token_urlsafe(32)
    await c.run(
        "INSERT INTO api_keys (id, user_id, key, name, created_at) VALUES (?, ?, ?, ?, ?)",
        str(uuid.uuid4()), c.session["user_id"], api_key, field(form, "name") or "Default", now(),
    )
    c.flash(f"API Key 创建成功！请立即复制保存：{api_key}", "success")
    return c.redirect("api_keys")


@login_required()
async def delete_api_key(c, key_id):
    await c.run("DELETE FROM api_keys WHERE id = ? AND user_id = ?", key_id, c.session["user_id"])
    c.flash("API Key 已删除", "info")
    return c.redirect("api_keys")


async def api_docs(c):
    return c.render("api_docs.html", base_url=c.origin, rss_url=c.url_for("rss_feed"))


# ==================== API ====================

@api_auth()
async def api_get_torrents(c):
    try:
        page = max(int(c.args.get("page", 1)), 1)
        per_page = min(max(int(c.args.get("per_page", 20)), 1), 100)
    except ValueError:
        return json_response({"success": False, "error": "Invalid pagination"}, 400)
    where, params = "", []
    if c.args.get("search"):
        where, params = " WHERE title LIKE ?", [f"%{c.args['search']}%"]
    total = (await c.one(f"SELECT COUNT(*) AS total FROM torrents{where}", *params))["total"]
    rows = await c.all(
        f"SELECT * FROM torrents{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        *params, per_page, (page - 1) * per_page,
    )
    return json_response({
        "success": True,
        "data": {
            "torrents": [torrent_json(c, t) for t in rows],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
        },
    })


@api_auth(publisher=True)
async def api_upload_torrent(c):
    if "multipart/form-data" not in (c.request.headers.get("content-type") or ""):
        return json_response(
            {"success": False, "error": "Please use multipart/form-data to upload torrent files"}, 400
        )
    torrent_id, error = await save_torrent(c, await c.request.form_data(), c.current_user)
    if error:
        return json_response({"success": False, "error": error}, 400)
    title = (await c.one("SELECT title FROM torrents WHERE id = ?", torrent_id))["title"]
    return json_response({
        "success": True,
        "data": {
            "id": torrent_id,
            "title": title,
            "download_url": c.url_for("download", torrent_id=torrent_id),
            "message": "Torrent uploaded successfully",
        },
    }, 201)


@api_auth()
async def api_get_torrent(c, torrent_id):
    t = await c.one("SELECT * FROM torrents WHERE id = ?", torrent_id)
    if not t:
        return json_response({"success": False, "error": "Torrent not found"}, 404)
    return json_response({"success": True, "data": torrent_json(c, t)})


async def api_get_stats(c):
    row = await c.one(
        "SELECT (SELECT COUNT(*) FROM torrents) AS torrents, (SELECT COUNT(*) FROM users) AS users, "
        "(SELECT COALESCE(SUM(file_size), 0) FROM torrents) AS size, "
        "(SELECT COUNT(*) FROM torrents WHERE created_at > ?) AS recent",
        (datetime.now(CST) - timedelta(days=1)).isoformat(),
    )
    return json_response({
        "success": True,
        "data": {
            "total_torrents": row["torrents"],
            "total_users": row["users"],
            "total_size": row["size"],
            "total_size_human": f"{row['size'] / 1024 / 1024 / 1024:.2f} GB",
            "recent_torrents_24h": row["recent"],
            "site_name": c.var("SITE_NAME") or "RSS种子站点",
            "rss_url": c.url_for("rss_feed"),
        },
    })


@api_auth()
async def api_get_user(c):
    u = c.current_user
    return json_response({
        "success": True,
        "data": {"id": u["id"], "username": u["username"], "role": u["role"], "auth_type": c.auth_type},
    })


# ==================== 路由表 ====================

PAGE_URLS = {
    "index": "/",
    "register": "/register",
    "login": "/login",
    "logout": "/logout",
    "upload": "/upload",
    "admin": "/admin",
    "rebuild_rss": "/admin/rebuild_rss",
    "api_keys": "/api-keys",
    "create_api_key": "/api-keys/create",
    "api_docs": "/api/docs",
}

ROUTES = [
    ("GET", r"/", index),
    ("GET POST", r"/register", register),
    ("GET POST", r"/login", login),
    ("GET", r"/logout", logout),
    ("GET POST", r"/upload", upload),
    ("GET", r"/admin", admin),
    ("GET", r"/admin/set_role/(?P<user_id>[^/]+)/(?P<role>[^/]+)", set_role),
    ("GET", r"/admin/delete_torrent/(?P<torrent_id>[^/]+)", delete_torrent),
    ("GET", r"/admin/rebuild_rss", rebuild_rss),
    ("GET", r"/api-keys", api_keys),
    ("POST", r"/api-keys/create", create_api_key),
    ("GET", r"/api-keys/delete/(?P<key_id>[^/]+)", delete_api_key),
    ("GET", r"/api/docs", api_docs),
    ("GET", r"/api/v1/torrents", api_get_torrents),
    ("POST", r"/api/v1/torrents", api_upload_torrent),
    ("GET", r"/api/v1/torrents/(?P<torrent_id>[^/]+)", api_get_torrent),
    ("GET", r"/api/v1/stats", api_get_stats),
    ("GET", r"/api/v1/user", api_get_user),
]
ROUTES = [(methods.split(), re.compile(pattern + r"\Z"), handler) for methods, pattern, handler in ROUTES]


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        c = Ctx(request, self.env)
        missing = [name for name in ("PUBLIC_URL", "SECRET_KEY", "ADMIN_PASSWORD") if not c.var(name)]
        if missing:
            return Response(f"未配置：{', '.join(missing)}（Worker → 设置 → Runtime variables and secrets 运行时变量和机密，不是构建变量）", status=500)
        is_api = c.path.startswith("/api/")
        for methods, pattern, handler in ROUTES:
            m = pattern.match(c.path)
            if m and c.method in methods:
                try:
                    return c.finish(await handler(c, **m.groupdict()))
                except Exception:
                    traceback.print_exc()
                    if is_api:
                        return json_response({"success": False, "error": "Internal server error"}, 500)
                    raise
        if is_api:
            return json_response({"success": False, "error": "Endpoint not found"}, 404)
        return Response("Not Found", status=404)
