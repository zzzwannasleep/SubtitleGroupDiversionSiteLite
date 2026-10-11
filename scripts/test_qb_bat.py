"""qb_clean.bat 端到端（mock QB）：python scripts/test_qb_bat.py

bat 是 Windows 用户在 QB「Torrent 完成时运行外部程序」里真正填的东西，
验证 bat -> powershell -> qb_clean.ps1 全链路参数转发与删除行为。
"""

import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PORT = 8921
ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "tools" / "qb_clean.bat"
deleted = []

TORRENTS = [
    {"hash": "a" * 40, "name": "Show 合集 [1080p]"},
    {"hash": "b" * 40, "name": "Show S01E01 [1080p]"},
    {"hash": "c" * 40, "name": "Show S01E02 [1080p]"},
    {"hash": "d" * 40, "name": "Other S01E01 [1080p]"},
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code=200, body=b"", headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode()
        if self.path == "/api/v2/auth/login":
            f = parse_qs(body)
            if f.get("username", [""])[0] == "admin" and f.get("password", [""])[0] == "pw":
                self._send(body=b"Ok.", headers={"Set-Cookie": "SID=mock; path=/"})
            else:
                self._send(body=b"Fails.")
        elif self.path == "/api/v2/torrents/delete":
            deleted.extend(parse_qs(body).get("hashes", [""])[0].split("|"))
            self._send()
        else:
            self._send(404)

    def do_GET(self):
        if self.path.startswith("/api/v2/torrents/info"):
            self._send(body=json.dumps(TORRENTS).encode())
        elif self.path.startswith("/api/v2/torrents/files"):
            h = parse_qs(urlparse(self.path).query).get("hash", [""])[0]
            n = 2 if h == "a" * 40 else 1
            self._send(body=json.dumps([{"length": 1, "path": [f"f{i}"]} for i in range(n)]).encode())
        else:
            self._send(404)


server = HTTPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

URL = f"http://127.0.0.1:{PORT}"


def run(args):
    r = subprocess.run(
        ["cmd", "/c", str(BAT), *args],
        capture_output=True, timeout=180, encoding="utf-8", errors="replace", cwd=str(ROOT),
    )
    if r.returncode != 0:
        print(r.stdout, r.stderr)
    return r


def result(r):
    m = [line for line in (r.stdout or "").splitlines() if line.startswith("RESULT:")]
    assert m, f"没有 RESULT 行:\n{r.stdout}\n{r.stderr}"
    return m[-1]


# 1. 手动 dry-run
r = run(["-Url", URL, "-User", "admin", "-Password", "pw"])
line = result(r)
assert r.returncode == 0 and "collections=1 deletions=2 deleted=0" in line, line
assert deleted == [], f"dry-run 却发了删除请求：{deleted}"

# 2. 手动 --apply
r = run(["-Url", URL, "-User", "admin", "-Password", "pw", "-Apply"])
line = result(r)
assert "deleted=2" in line, line
assert sorted(h for h in deleted if len(h) == 40) == ["b" * 40, "c" * 40], deleted

# 3. 事件模式：合集完成 → 自动删分集
deleted.clear()
r = run(["a" * 40, "-Url", URL, "-User", "admin", "-Password", "pw"])
line = result(r)
assert "deleted=2" in line, line
assert sorted(h for h in deleted if len(h) == 40) == ["b" * 40, "c" * 40], deleted

server.shutdown()
print("qb_clean.bat e2e（mock QB）全部通过：dry-run 零删除 / -Apply 精准删除 / 事件模式自动清理")