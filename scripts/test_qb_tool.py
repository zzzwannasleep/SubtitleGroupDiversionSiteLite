"""qb_episode_clean.plan_cleanup 单元测试：python scripts/test_qb_tool.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from qb_episode_clean import plan_cleanup  # noqa: E402


def ids(deletions):
    return sorted(d["title"] for d in deletions)


# QB 里已有合集 + 分集 → 分集被点名删掉
items = [
    {"id": "h1", "title": "Show 合集 [1080p]", "is_collection": True},
    {"id": "h2", "title": "Show S01E01 [1080p]", "is_collection": False},
    {"id": "h3", "title": "Show S01E02 [1080p]", "is_collection": False},
    {"id": "h4", "title": "Other S01E01 [1080p]", "is_collection": False},
]
cols, dels = plan_cleanup(items)
assert [c["title"] for c in cols] == ["Show 合集 [1080p]"]
assert ids(dels) == ["Show S01E01 [1080p]", "Show S01E02 [1080p]"], ids(dels)
assert all(d["matched_collection"] == "Show 合集 [1080p]" for d in dels)

# is_collection=None（旧数据）按标题关键词兜底
cols, dels = plan_cleanup([
    {"id": "a", "title": "Show 全集", "is_collection": None},
    {"id": "b", "title": "Show E01", "is_collection": None},
])
assert ids(dels) == ["Show E01"]

# 站点基准：合集还没进 QB 也能点名分集
cols, dels = plan_cleanup([
    {"id": "site-col", "title": "番剧 第2季 合集", "is_collection": True},
    {"id": "h5", "title": "番剧 第3季 第01话 [1080p]", "is_collection": False},
    {"id": "h6", "title": "番剧 第2季 第01话", "is_collection": False},
])
assert ids(dels) == ["番剧 第2季 第01话"], ids(dels)

# 跨季/不同系列不误删
cols, dels = plan_cleanup([
    {"id": "c1", "title": "Show S01 合集", "is_collection": True},
    {"id": "c2", "title": "Another 合集", "is_collection": True},
    {"id": "e1", "title": "Show S02E01", "is_collection": False},
    {"id": "e2", "title": "Other E01", "is_collection": False},
])
assert dels == [], ids(dels)

# 只有分集没有合集 → 不删任何东西
cols, dels = plan_cleanup([
    {"id": "x", "title": "Lone E01", "is_collection": False},
])
assert cols == [] and dels == []

print("qb_episode_clean 测试全部通过")