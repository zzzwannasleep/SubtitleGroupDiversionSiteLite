"""qb_episode_clean —— qBittorrent 合集/分集清理工具（外部独立程序）。

配合 RSS 种子站使用：站里出了合集种子后，把 qBittorrent 里命名相同的分集任务
检测出来并删掉，只留合集。匹配规则与站点完全一致（共享 src/episode_match.py）。

用法：
    python tools/qb_episode_clean.py                          # 交互式输入地址/账号
    python tools/qb_episode_clean.py --url http://127.0.0.1:8080 --user admin --password 123 --apply

参数：
    --url            qBittorrent WebUI 地址，如 http://127.0.0.1:8080
    --user           WebUI 用户名
    --password       WebUI 密码
    --category       只处理这个分类（可省略=全部任务）
    --site           RSS 种子站地址（可选，如 https://你的站点）
    --site-key       站点 API Key（可选；填了就以站点上的合集为基准清理，
                     合集还没被 RSS 下载到 QB 里也能先清分集）
    --apply          真正执行删除；不带此参数只打印报告，不动任何东西
    --keep-files     只从任务列表移除、保留硬盘文件（默认连文件一起删，内容已包含在合集里）

删除的只是「与某合集命名相同」的分集任务；跨季、画质不同、系列名不同的绝不误删。
默认 dry-run：先看报告，确认无误再加 --apply。
"""

import argparse
import getpass
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Windows 控制台默认 GBK，中文/图标输出防炸
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# 共享站点的匹配算法（工具与本仓库 src 同源，语义不会漂移）
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from episode_match import (  # noqa: E402
    classify,
    parse_season,
    seasons_compatible,
    series_key,
)


# ==================== 计划：纯逻辑，可独立测试 ====================

def plan_cleanup(items):
    """给定任务清单，算出要删的分集。

    items: [{"id": 任意标识, "title": 标题, "is_collection": bool 或 None}]
    返回 (collections, deletions)：
      collections = 合集列表 [{id, title}]
      deletions   = 应删分集列表 [{id, title, matched_collection}]
    is_collection=None 的旧数据按标题关键词兜底判断。
    """
    collections, episodes = [], []
    for item in items:
        is_collection = item.get("is_collection")
        if is_collection is None:
            is_collection = classify(item["title"])
        (collections if is_collection else episodes).append(item)

    deletions = []
    for ep in episodes:
        ep_key = series_key(ep["title"])
        if not ep_key:
            continue
        ep_season = parse_season(ep["title"])
        for col in collections:
            if (
                series_key(col["title"], is_collection=True) == ep_key
                and seasons_compatible(ep_season, parse_season(col["title"]))
            ):
                deletions.append({**ep, "matched_collection": col["title"]})
                break
    return collections, deletions


# ==================== qBittorrent WebUI API v2 ====================

class QBApi:
    def __init__(self, base, user, password):
        self.base = base.rstrip("/")
        self.user = user
        self.password = password
        self.cookie = None

    def _request(self, path, data=None, headers=None, method=None):
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers or {}, method=method
        )
        if self.cookie:
            req.add_header("Cookie", self.cookie)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                set_cookie = resp.headers.get("Set-Cookie")
                if set_cookie:
                    self.cookie = set_cookie.split(";")[0]
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            body = e.read()
            return e.code, body

    def login(self):
        data = urllib.parse.urlencode({"username": self.user, "password": self.password}).encode()
        status, body = self._request(
            "/api/v2/auth/login", data,
            {"Content-Type": "application/x-www-form-urlencoded"}, "POST",
        )
        ok = status == 200 and b"Ok" in body
        if not ok:
            raise SystemExit(f"QB 登录失败：HTTP {status} {body[:200].decode('utf-8', 'replace')}")
        return True

    def torrents(self, category=None):
        qs = "?category=" + urllib.parse.quote(category) if category else ""
        status, body = self._request("/api/v2/torrents/info" + qs)
        if status != 200:
            raise SystemExit(f"获取任务列表失败：HTTP {status}")
        return json.loads(body)

    def file_count(self, torrent_hash):
        status, body = self._request("/api/v2/torrents/files?hash=" + torrent_hash)
        return len(json.loads(body)) if status == 200 else None

    def delete(self, hashes, keep_files=False):
        data = urllib.parse.urlencode({
            "hashes": "|".join(hashes),
            "deleteFiles": "false" if keep_files else "true",
        }).encode()
        status, _ = self._request(
            "/api/v2/torrents/delete", data,
            {"Content-Type": "application/x-www-form-urlencoded"}, "POST",
        )
        if status != 200:
            raise SystemExit(f"删除失败：HTTP {status}")

    def logout(self):
        if self.cookie:
            self._request("/api/v2/auth/logout", method="POST")


# ==================== 站点合集（可选基准） ====================

def site_collections(base, api_key):
    """拉站点全部种子，返回合集列表 [{id, title, is_collection}]（用站内落库的标记）。"""
    items, page = [], 1
    while True:
        qs = urllib.parse.urlencode({"page": page, "per_page": 100})
        req = urllib.request.Request(f"{base.rstrip('/')}/api/v1/torrents?{qs}")
        req.add_header("X-API-Key", api_key)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
        except urllib.error.HTTPError as e:
            raise SystemExit(f"拉取站点种子失败：HTTP {e.code}（检查 --site-key 是否有效）")
        batch = data["data"]["torrents"]
        items += [{"id": t["id"], "title": t["title"], "is_collection": t.get("is_collection")}
                  for t in batch]
        if page >= data["data"]["pagination"]["total_pages"]:
            break
        page += 1
    return [t for t in items if t.get("is_collection")]


# ==================== 主流程 ====================

def main():
    ap = argparse.ArgumentParser(description="qBittorrent 合集/分集清理（默认 dry-run）")
    ap.add_argument("--url", help="qBittorrent WebUI 地址")
    ap.add_argument("--user", help="WebUI 用户名")
    ap.add_argument("--password", help="WebUI 密码")
    ap.add_argument("--category", help="只处理该分类")
    ap.add_argument("--site", help="RSS 种子站地址（可选）")
    ap.add_argument("--site-key", help="站点 API Key（可选）")
    ap.add_argument("--apply", action="store_true", help="真正执行删除（缺省只报告）")
    ap.add_argument("--keep-files", action="store_true", help="删除任务时保留硬盘文件")
    args = ap.parse_args()

    url = args.url or input("QB WebUI 地址（如 http://127.0.0.1:8080）：").strip()
    user = args.user or input("QB 用户名：").strip()
    password = args.password or getpass.getpass("QB 密码：")

    api = QBApi(url, user, password)
    api.login()
    print(f"✓ 已登录 {url}")

    torrents = api.torrents(args.category)
    print(f"✓ 拉到 {len(torrents)} 个任务" + (f"（分类 {args.category}）" if args.category else ""))

    items = []
    for t in torrents:
        items.append({
            "id": t["hash"],
            "title": t["name"],
            "is_collection": classify(t["name"], api.file_count(t["hash"])),
        })

    # 站点基准：站里已有合集、QB 里还没下到，也能先清掉对应分集
    extra = []
    if args.site and args.site_key:
        cols = site_collections(args.site, args.site_key)
        print(f"✓ 站点合集基准：{len(cols)} 个")
        known = {i["id"] for i in items}
        extra = [c for c in cols if c["id"] not in known]
        # 站点合集与 QB 内合集按标题去重（同系列键只保留一个代表）
        dedup, seen = [], set()
        for c in extra:
            key = series_key(c["title"], is_collection=True)
            if key and key not in seen:
                seen.add(key)
                dedup.append(c)
        extra = dedup

    collections, deletions = plan_cleanup(items + extra)
    print(f"\n合集 {len(collections)} 个：")
    for c in collections:
        print(f"  [合集] {c['title']}")
    if not collections:
        print("  （无）")

    print(f"\n待删分集 {len(deletions)} 个：")
    for d in deletions:
        print(f"  [分集] {d['title']}  ← 匹配合集：{d['matched_collection']}")
    if not deletions:
        print("  （无，没有可清理的重复分集）")
    else:
        print("  提示：若匹配的合集还没下载完，删除分集会暂时看不到该集内容，等合集完成即可。")

    if not deletions:
        api.logout()
        return
    if not args.apply:
        print("\n以上为 dry-run 报告，未删除任何东西。确认无误后加 --apply 执行。")
        api.logout()
        return

    hashes = [d["id"] for d in deletions if len(d["id"]) == 40]  # 站点基准项没有 hash
    if hashes:
        api.delete(hashes, keep_files=args.keep_files)
        print(f"\n✓ 已删除 {len(hashes)} 个分集任务"
              + ("（保留硬盘文件）" if args.keep_files else "（含硬盘文件）"))
    api.logout()


if __name__ == "__main__":
    main()
