"""从旧 Flask 版迁移数据：种子文件传到 R2，其余生成 migrate.sql。

用法:
    npx wrangler login
    python scripts/migrate.py 旧的site.db 旧的uploads目录
    python scripts/migrate.py site.db uploads --tz +08:00  # 旧站不是 Docker 部署、服务器是北京时间时
    python scripts/migrate.py site.db uploads --local      # 迁到本地 dev 环境试跑

然后执行 migrate.sql（命令会打印出来），最后在管理后台点「重建 RSS」。

- 种子：上传到 R2 的 t/<id>.torrent，元数据和网页上传一致；可重复运行，已迁移的会跳过写库
- API Key：原样迁移，发布员的自动化脚本不用改
- 用户：旧密码哈希（werkzeug scrypt）在免费版 Worker 里算不动，改为随机临时密码，
  写进 migrate-passwords.txt 由你转交；admin 不迁移密码，仍用 ADMIN_PASSWORD
- 时间：旧站存的是不带时区的服务器本地时间，Docker 默认 UTC，按 --tz 解释后统一转成 +08:00
"""

import argparse
import hashlib
import secrets
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

CST = timezone(timedelta(hours=8))
PBKDF2_ITERATIONS = 100_000  # 与 src/entry.py 一致


def hash_password(password):
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${dk.hex()}"


def sql(value):
    if value is None:
        return "NULL"
    if isinstance(value, int):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def insert(table, row):
    cols = ", ".join(row)
    vals = ", ".join(sql(v) for v in row.values())
    return f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({vals});"


def parse_tz(text):
    sign = -1 if text.startswith("-") else 1
    hours, minutes = text.lstrip("+-").split(":")
    return timezone(sign * timedelta(hours=int(hours), minutes=int(minutes)))


def to_cst(value, tz):
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(CST).isoformat()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("db", type=Path, help="旧站的 site.db")
    ap.add_argument("uploads", type=Path, help="旧站的 uploads 目录（文件名形如 <uuid>_xxx.torrent）")
    ap.add_argument("--tz", default="+00:00", help="旧站服务器时区，Docker 部署默认 UTC（+00:00）")
    ap.add_argument("--local", action="store_true", help="迁到本地 dev 环境")
    ap.add_argument("--bucket", default="sgds")
    args = ap.parse_args()

    db_path, uploads = args.db, args.uploads
    if not db_path.is_file():
        sys.exit(f"找不到 {db_path}")
    if not uploads.is_dir():
        sys.exit(f"找不到目录 {uploads}")
    tz = parse_tz(args.tz)
    old = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)  # 只读，不动原库
    old.row_factory = sqlite3.Row

    # 旧 admin 的 uuid → 新库固定 id 'admin'
    user_ids = {u["id"]: ("admin" if u["username"] == "admin" else u["id"])
                for u in old.execute("SELECT id, username FROM users")}

    lines, passwords = [], []
    for u in old.execute("SELECT * FROM users ORDER BY created_at"):
        if u["username"] == "admin":
            continue
        temp = secrets.token_urlsafe(9)
        passwords.append(f"{u['username']}\t{u['role']}\t{temp}")
        lines.append(insert("users", {
            "id": u["id"], "username": u["username"], "password": hash_password(temp),
            "role": u["role"], "created_at": to_cst(u["created_at"], tz),
        }))

    for k in old.execute("SELECT * FROM api_keys"):
        lines.append(insert("api_keys", {
            "id": k["id"], "user_id": user_ids.get(k["user_id"], k["user_id"]), "key": k["key"],
            "name": k["name"], "created_at": to_cst(k["created_at"], tz),
            "last_used": k["last_used"] and to_cst(k["last_used"], tz), "is_active": k["is_active"],
        }))

    torrents = old.execute("SELECT * FROM torrents ORDER BY created_at").fetchall()
    target = "--local" if args.local else "--remote"
    missing = 0
    for i, t in enumerate(torrents, 1):
        src = uploads / t["filename"]
        if not src.is_file():
            print(f"[跳过] 文件不存在：{src}（{t['title']}）")
            missing += 1
            continue
        key = f"t/{t['id']}.torrent"
        print(f"[{i}/{len(torrents)}] {t['title']}")
        # 种子先进 R2，SQL 后执行：库里不会出现指向不存在文件的记录
        subprocess.run(
            ["npx", "wrangler", "r2", "object", "put", f"{args.bucket}/{key}", target,
             "--file", str(src),
             "--content-type", "application/x-bittorrent",
             "--content-disposition", f"attachment; filename*=UTF-8''{quote(t['original_filename'])}",
             "--cache-control", "public, max-age=31536000, immutable"],
            check=True, shell=sys.platform == "win32", capture_output=True,
        )
        lines.append(insert("torrents", {
            "id": t["id"], "title": t["title"], "filename": key,
            "original_filename": t["original_filename"], "file_size": src.stat().st_size,
            "created_at": to_cst(t["created_at"], tz),
            "publisher_id": user_ids.get(t["publisher_id"], t["publisher_id"]),
            "publisher_name": t["publisher_name"],
        }))

    Path("migrate.sql").write_text("\n".join(lines) + "\n", encoding="utf-8")
    Path("migrate-passwords.txt").write_text(
        "用户名\t角色\t临时密码\n" + "\n".join(passwords) + "\n", encoding="utf-8")

    print(f"\n种子 {len(torrents) - missing}/{len(torrents)} 已传到 R2，"
          f"用户 {len(passwords)} 个，API Key {old.execute('SELECT COUNT(*) FROM api_keys').fetchone()[0]} 个")
    print("下一步：")
    print(f"  1. npx wrangler d1 execute DB {target} --file migrate.sql")
    print("     （报 missing a database_id 就把 migrate.sql 内容粘到 D1 控制台执行）")
    print("  2. 管理后台点「重建 RSS」")
    print("  3. 把 migrate-passwords.txt 里的临时密码发给对应用户，然后删掉这个文件")


if __name__ == "__main__":
    main()
