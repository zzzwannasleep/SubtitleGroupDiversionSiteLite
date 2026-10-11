"""episode_match 单元测试：python scripts/test_episode_match.py，全绿打印 OK。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from episode_match import (
    bdecode,
    classify,
    parse_season,
    parse_torrent_info,
    seasons_compatible,
    series_key,
)

def match(ep_title, col_title):
    """与两处调用一致的完整匹配：系列键相同 + 季号兼容。"""
    return (
        series_key(ep_title) == series_key(col_title, is_collection=True)
        and seasons_compatible(parse_season(ep_title), parse_season(col_title))
    )

CASES = [
    # (分集标题, 合集标题, 是否应匹配)
    ("Show S01E03 [1080p]", "Show 合集 [1080p]", True),
    ("Show S01 E03", "Show S01 全集", True),
    ("Show S02E01 [1080p]", "Show S02 合集 [1080p]", True),
    ("Show 第01集 [720p]", "Show 合集 [720p]", True),
    ("Show 第十二话 [720p]", "Show 全集合集 [720p]", True),
    ("Show - 01 [1080p]", "Show 合集 [1080p]", True),          # 裸集数
    ("Show 08话 END [1080p]", "Show 完全版 [1080p]", True),
    ("Show Vol.3 [1080p]", "Show 全集 Vol.1-12 [1080p]", True),
    ("Show EP05 (GB)", "Show 01-12集 合集 (GB)", True),
    ("Show E03 #5 [1080p]", "Show Batch [1080p]", True),
    ("Show Season 2 03 [1080p]", "Show Season 2 合集 [1080p]", True),
    ("Show 01v2 [1080p]", "Show 合集 [1080p]", True),
    ("Show 03 [1080p]", "Show S03 合集 [1080p]", True),        # 分集没写季号，合集写了
    ("高达 00 第02话", "高达00 合集", False),                    # 裸集数保护：00 是番名一部分
    # 不应匹配（防错删）
    ("Show S02 E01 [1080p]", "Show S03 合集 [1080p]", False),   # 跨季
    ("Show 第2季 01 [1080p]", "Show 第3季 合集 [1080p]", False),
    ("Show 3 01 [1080p]", "Show 2 合集 [1080p]", False),        # 季号不同的裸写法
    ("Show 01 [720p]", "Show 合集 [1080p]", False),             # 画质不同不算命名相同
    ("Show B 01", "Show A 合集", False),
    ("Show E01 [1080p]", "Show II 合集 [1080p]", False),        # II 是续作不是集数
    ("Another Show E02", "Show 合集", False),
]

for ep_title, col_title, expect in CASES:
    ep_key = series_key(ep_title)
    col_key = series_key(col_title, is_collection=True)
    got = match(ep_title, col_title) and ep_key != ""
    status = "OK " if got == expect else "FAIL"
    print(f"[{status}] {ep_title!r} vs {col_title!r}: {ep_key!r} vs {col_key!r} -> {got} (期望 {expect})")
    assert got == expect, (ep_title, col_title, ep_key, col_key)

# 季号解析
assert parse_season("Show S01E03") == 1
assert parse_season("Show 第十二季") == 12
assert parse_season("Show Season 3") == 3
assert parse_season("Show S02") == 2
assert parse_season("Show E03") is None
assert seasons_compatible(None, 3) and seasons_compatible(2, None) and seasons_compatible(2, 2)
assert not seasons_compatible(2, 3)

# classify：文件数优先，其次标题关键词
assert classify("Show 01", 3) is True
assert classify("Show 01", 1) is False
assert classify("Show 全集", 1) is True
assert classify("Show Complete Series", None) is True
assert classify("Show 01", None) is False

# bencode / parse_torrent_info（夹具用编码器构造，不手搓字节）
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

single = benc({b"announce": b"abc", b"info": {b"name": b"test", b"length": 123}})
multi = benc({
    b"announce": b"abc",
    b"info": {
        b"name": "番剧合集",
        b"files": [
            {b"length": 1, b"path": ["01"]},
            {b"length": 2, b"path": ["02.mkv"]},
        ],
    },
})
info = parse_torrent_info(single)
assert info == {"name": "test", "file_count": 1}, info
info = parse_torrent_info(multi)
assert info == {"name": "番剧合集", "file_count": 2}, info
assert parse_torrent_info(b"not-bencode") is None
assert parse_torrent_info(b"d4:infod4:name4:testee")["file_count"] == 1
assert bdecode(b"li1ei2ee") == [1, 2]

print(f"episode_match 测试全部通过（{len(CASES)} 组匹配用例 + classify + bencode）")