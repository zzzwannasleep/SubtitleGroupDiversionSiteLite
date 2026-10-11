"""qb_clean.jq（sh 用的匹配核心）与 Python episode_match 的等价性验证。

用与 scripts/test_episode_match.py 相同的 21 组用例跑 jq 程序，
验证 sh 版匹配核心与站点/PS1 版行为一致。运行：python scripts/test_qb_sh_core.py
"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JQ = Path(sys.executable).parent / "jq.exe"
if not JQ.exists():
    JQ = Path(r"C:\Users\65282\AppData\Local\Temp\jq.exe")
if not JQ.exists():
    sys.exit("找不到 jq.exe，请先安装（本测试只在本机验证 sh 核心）")

JQF = ROOT / "tools" / "qb_clean.jq"

CASES = [
    ("Show S01E03 [1080p]", "Show 合集 [1080p]", True),
    ("Show S01 E03", "Show S01 全集", True),
    ("Show S02E01 [1080p]", "Show S02 合集 [1080p]", True),
    ("Show 第01集 [720p]", "Show 合集 [720p]", True),
    ("Show 第十二话 [720p]", "Show 全集合集 [720p]", True),
    ("Show - 01 [1080p]", "Show 合集 [1080p]", True),
    ("Show 08话 END [1080p]", "Show 完全版 [1080p]", True),
    ("Show Vol.3 [1080p]", "Show 全集 Vol.1-12 [1080p]", True),
    ("Show EP05 (GB)", "Show 01-12集 合集 (GB)", True),
    ("Show E03 #5 [1080p]", "Show Batch [1080p]", True),
    ("Show Season 2 03 [1080p]", "Show Season 2 合集 [1080p]", True),
    ("Show 01v2 [1080p]", "Show 合集 [1080p]", True),
    ("Show 03 [1080p]", "Show S03 合集 [1080p]", True),
    ("高达 00 第02话", "高达00 合集", False),
    ("Show S02 E01 [1080p]", "Show S03 合集 [1080p]", False),
    ("Show 第2季 01 [1080p]", "Show 第3季 合集 [1080p]", False),
    ("Show 3 01 [1080p]", "Show 2 合集 [1080p]", False),
    ("Show 01 [720p]", "Show 合集 [1080p]", False),
    ("Show B 01", "Show A 合集", False),
    ("Show E01 [1080p]", "Show II 合集 [1080p]", False),
    ("Another Show E02", "Show 合集", False),
]

passed = 0
for i, (ep, col, expect) in enumerate(CASES):
    payload = {
        "hash": "",
        "items": [
            {"hash": "e" * 40, "name": ep, "fc": 1},
            {"hash": "c" * 40, "name": col, "fc": 2},
        ],
    }
    r = subprocess.run(
        [str(JQ), "-c", "-f", str(JQF)],
        input=json.dumps(payload, ensure_ascii=False).encode(),
        capture_output=True,
    )
    out = json.loads(r.stdout.decode("utf-8"))
    got = any(d["title"] == ep for d in out["deletions"])
    status = "OK " if got == expect else "FAIL"
    print(f"[{status}] {ep!r} vs {col!r} -> {got} (期望 {expect})")
    assert got == expect, (ep, col, out, r.stderr.decode("utf-8", "replace"))
    passed = passed + 1 if got == expect else passed

# 手动模式全部用例应过；事件模式校验 iscol 判定
def run_plan(ep, col, completed_hash, completed_name, completed_fc, include_completed=True):
    items = [
        {"hash": "e" * 40, "name": ep, "fc": 1},
        {"hash": "c" * 40, "name": col, "fc": 2},
    ]
    if include_completed:
        items.append({"hash": completed_hash, "name": completed_name, "fc": completed_fc})
    payload = {"hash": completed_hash, "items": items}
    r = subprocess.run([str(JQ), "-c", "-f", str(JQF)], input=json.dumps(payload, ensure_ascii=False).encode(), capture_output=True)
    return json.loads(r.stdout)

# 事件：合集完成 → 删分集
out = run_plan("Show S01E01 [1080p]", "Show 合集 [1080p]", "a" * 40, "Show 合集 [1080p]", 2)
assert out["iscol"] == "collection", out
assert [d["title"] for d in out["deletions"]] == ["Show S01E01 [1080p]"], out

# 事件：分集完成 → 不动手
out = run_plan("Show S01E01 [1080p]", "Show 合集 [1080p]", "b" * 40, "Show S01E01 [1080p]", 1)
assert out["iscol"] == "episode" and out["deletions"] == [], out

# 事件：notfound（完成的种子不在任务列表里）
out = run_plan("Show S01E01 [1080p]", "Show 合集 [1080p]", "f" * 40, "X", 1, include_completed=False)
assert out["iscol"] == "notfound", out

print(f"qb_clean.jq 等价性验证通过（{passed}/21 匹配用例 + 事件模式 + notfound）")