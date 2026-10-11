"""qb_episode_clean 端到端（mock qBittorrent）：python scripts/test_qb_e2e.py

起一个假 QB WebUI（登录/任务列表/删除接口），跑工具 dry-run 和 --apply，
验证：不 --apply 时零删除、--apply 时把正确 hash 集合发给 QB。
"""

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

PORT = 8917
deleted_hashes = []

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
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode()
        if self.path == "/api/v2/auth/login":
            if "username=admin&password=pw" in body:
                self._send(body=b"Ok.", headers={"Set-Cookie": "SID=mock; path=/"})
            else:
                self._send(body=b"Fails.")
        elif self.path == "/api/v2/torrents/delete":
            from urllib.parse import parse_qs
            fields = parse_qs(body)
            deleted_hashes.extend(fields.get("hashes", [""])[0].split("|"))
            deleted_hashes.append(("deleteFiles", fields.get("deleteFiles", ["true"])[0]))
            self._send()
        elif self.path == "/api/v2/auth/logout":
            self._send()
        else:
            self._send(404)

    def do_GET(self):
        if self.path.startswith("/api/v2/torrents/info"):
            self._send(body=json.dumps(TORRENTS).encode())
        else:
            self._send(404)


server = HTTPServer(("127.0.0.1", PORT), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()

PY = sys.executable
TOOL = str(Path(__file__).resolve().parents[1] / "tools" / "qb_episode_clean.py")
BASE_ARGS = [
    PY, "-X", "utf8", TOOL,
    "--url", f"http://127.0.0.1:{PORT}", "--user", "admin", "--password", "pw",
]

# 1. dry-run：报告两个分集，但不删除
r = subprocess.run(BASE_ARGS, capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout)
assert r.returncode == 0, r.stderr
assert "待删分集 2 个" in r.stdout and "Show S01E01" in r.stdout and "Show S01E02" in r.stdout
assert deleted_hashes == [], f"dry-run 却发了删除请求：{deleted_hashes}"

# 2. --apply：两个分集被删，合集和无关任务不动
r = subprocess.run(BASE_ARGS + ["--apply"], capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout)
assert r.returncode == 0, r.stderr
assert "已删除 2 个分集任务" in r.stdout
assert deleted_hashes.count("b" * 40) == 1 and deleted_hashes.count("c" * 40) == 1
assert deleted_hashes.count("a" * 40) == 0 and deleted_hashes.count("d" * 40) == 0
delete_files = [v for v in deleted_hashes if isinstance(v, tuple)][0][1]
assert delete_files == "true", delete_files

# 3. --apply --keep-files：保留硬盘文件
deleted_hashes.clear()
r = subprocess.run(BASE_ARGS + ["--apply", "--keep-files"], capture_output=True, text=True, encoding="utf-8", errors="replace")
delete_files = [v for v in deleted_hashes if isinstance(v, tuple)][0][1]
assert delete_files == "false", delete_files

server.shutdown()
print("qb_episode_clean e2e（mock QB）全部通过：dry-run 零删除、apply 只删匹配分集")