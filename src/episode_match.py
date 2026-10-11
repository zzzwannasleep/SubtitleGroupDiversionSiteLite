"""合集 / 分集识别与系列匹配。

被两处共用，只依赖标准库：
- src/entry.py（Cloudflare Worker，pyodide 环境）
- tools/qb_episode_clean.py（本机运行的 qBittorrent 清理工具）

规则（保守优先，宁可漏删、不可错删）：
- 合集判定：种子内含 >= 2 个文件，或标题含合集关键词（合集/全集/complete/batch…）。
- 分集标记：S01E02 / E02 / EP02 / 第03集 / 08话 / Vol.1 / #5 / 01v2 / (完) /
  1-12集区间，以及分集标题末尾的裸集数（如 “Show - 01”）。
- 系列键：去掉集数标记（合集再去掉合集关键词）后，折叠大小写、全角、空白和分隔符。
  两个种子系列键相同 ⇒ 视为“命名相同”，合集可以取代分集。
- 合集标题里的裸数字（如 “第二季” 的 2）不会被去掉，避免第二季/第三季互相误伤；
  且裸集数规则只对分集标题生效、每个标题最多去掉一个。
"""

import re
import unicodedata

# 标题中出现即按合集处理（即使种子只有单文件）
COLLECTION_KW = re.compile(
    r"合集|全集|合订|全一卷|全季|完全版|complete|batch|anthology"
)

# 分集标记（大小写已在 fold 里折掉；从标题里删掉后剩下的就是“系列命名”）
# 季号（s01 / 第2季 / season 2）不进系列键——单独用 parse_season 提取后做兼容性判断，
# 这样“Show 合集”（没写季号）也能匹配到 “Show S01E03”，而 S02 和 S03 互不误伤。
SEASON_TOKEN = re.compile(r"(?<![a-z0-9])(?:s(\d{1,3})|第\s*([\d一二三四五六七八九十]{1,4})\s*季|season\s*(\d{1,3}))")
EPISODE_MARKERS = [
    (re.compile(p), " ")
    for p in (
        r"(?<![a-z0-9])s\d{1,3}\s?e\d{1,3}",                    # S01E02 / s1 e2
        r"(?<![a-z0-9])s\d{1,3}(?![0-9a-z])",                   # 独立的 S01（季号）
        r"(?<![a-z0-9])(?:ep?|episode)\s?[.\-]?\s?\d{1,4}(?![0-9])",  # E02 / EP3 / Episode 04
        r"第\s*[\d一二三四五六七八九十百]{1,6}\s*[集话話]",        # 第03集 / 第十二话
        r"第\s*[\d一二三四五六七八九十]{1,4}\s*季",               # 第2季
        r"vol(?:\.|ume)?\s?\d{1,3}(?:\s?(?:[-~]|至|到)\s?\d{1,3})?",  # Vol.1 / Volume 12 / Vol.1-12
        r"(?<![a-z0-9])\d{1,3}\s?(?:[-~]|至|到)\s?\d{1,3}(?![0-9])\s*[集话話]?",  # 01-12集 / 01-12
        r"(?<![0-9])\d{1,3}[集话話]",                            # 08话 / 12集
        r"#\s?\d{1,4}",                                         # #5
        r"(?<![0-9])\d{1,3}\s?v\d(?![0-9])",                    # 01v2 修正版
        r"[([\{（【]\s*(?:完|end|fin)\s*[)\]\}）】]",             # (完) / [END]
        r"\bend\b",                                             # 独立的 END
    )
]

# 末尾裸集数：1-3 位独立数字，前面不能是字母数字/小数点/连字符（避开 x264、2.0、S-1 等）
BARE_EPISODE = re.compile(r"(?<![0-9a-z.\-])(\d{1,3})(?![0-9a-z])")

_SPACE = re.compile(r"\s+")


def fold(text):
    """NFKC 折叠全角/特殊字符 + casefold，后续正则只按半角小写写。"""
    return unicodedata.normalize("NFKC", str(text)).casefold()


def classify(title, file_count=None):
    """是否合集：多种子文件，或标题含合集关键词。"""
    if file_count and file_count > 1:
        return True
    return bool(COLLECTION_KW.search(fold(title)))


def _strip_markers(text, allow_bare):
    for pattern, replacement in EPISODE_MARKERS:
        text = pattern.sub(replacement, text)
    if allow_bare:
        matches = list(BARE_EPISODE.finditer(text))
        if matches:  # 只去掉最后一个裸数字，且每标题最多一个
            m = matches[-1]
            text = text[: m.start()] + " " + text[m.end():]
    return _SPACE.sub(" ", text).strip()


_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_to_int(text):
    """中文数字转整数（支持 1-99 简单组合），失败返回 None。"""
    if text.isdigit():
        return int(text)
    if text == "十":
        return 10
    if "十" in text:
        left, _, right = text.partition("十")
        tens = _CN_NUM.get(left, 1) if left else 1
        ones = _CN_NUM.get(right, 0) if right else 0
        return tens * 10 + ones
    return _CN_NUM.get(text)


def parse_season(title):
    """从标题提取季号（S01 / 第2季 / Season 3 / s1e2 的 s1），没有则 None。"""
    m = SEASON_TOKEN.search(fold(title))
    if not m:
        return None
    for group in m.groups():
        if group is None:
            continue
        number = _cn_to_int(group)
        if number:
            return number
    return None


def seasons_compatible(episode_season, collection_season):
    """季号兼容性：双方都没写季号必须一致；一方没写视为兼容（合集覆盖全部）。"""
    if episode_season is None or collection_season is None:
        return True
    return episode_season == collection_season


def series_key(title, is_collection=False):
    """系列键：去掉季号与集数标记后的“命名”。相同 ⇒ 同一系列（命名相同）。"""
    text = fold(title)
    if is_collection:
        text = COLLECTION_KW.sub(" ", text)
        text = _strip_markers(text, allow_bare=False)  # 合集不去裸数字（保住“第二季”的 2）
    else:
        text = _strip_markers(text, allow_bare=True)
    # 折掉空白与全部分隔符，只留字母/数字/CJK：兼容 “.”、“_”、“-”、空格等写法差异
    return "".join(ch for ch in text if ch.isalnum())


# ==================== bencode / .torrent 解析 ====================

def bdecode(data):
    """最小 bencode 解码，失败抛 ValueError。只读 bytes，不依赖外部库。"""
    def dec(i):
        c = data[i:i + 1]
        if c == b"i":
            j = data.index(b"e", i)
            return int(data[i + 1:j]), j + 1
        if c in (b"l", b"d"):
            out, i = ([] if c == b"l" else {}), i + 1
            while data[i:i + 1] != b"e":
                k, i = dec(i)
                if c == b"l":
                    out.append(k)
                else:
                    v, i = dec(i)
                    out[k] = v
            return out, i + 1
        if c == b"":
            raise ValueError("unexpected end of data")
        n = data.index(b":", i)
        size = int(data[i:n])
        end = n + 1 + size
        return data[n + 1:end], end

    value, _ = dec(0)
    return value


def parse_torrent_info(data):
    """从 .torrent 内容提取 {name, file_count}；解析失败返回 None（不阻断上传）。"""
    try:
        info = bdecode(data)[b"info"]
        name = info.get(b"name", b"").decode("utf-8", "replace")
        if b"files" in info:
            file_count = len(info[b"files"])
        else:
            file_count = 1
        return {"name": name, "file_count": file_count}
    except (ValueError, KeyError, IndexError, TypeError, RecursionError):
        return None
