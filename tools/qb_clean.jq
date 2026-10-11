# qb_clean.jq —— 合集/分集匹配核心（被 qb_clean.sh 调用，规则与站点 src/episode_match.py 同源）
#
# 输入：{"hash": "<事件模式传入的种子hash，手动模式传空串>", "items": [{"hash","name","fc"}]}
# 输出：{"iscol": "manual|collection|episode|notfound", "collections": [...], "deletions": [{hash,title,matched}]}
#
# 规则（保守优先，宁可漏删、不可错删）：
# - 合集：标题含合集关键词，或种子内文件数 > 1
# - 分集标记：S01E02 / E02 / EP02 / 第03集 / 08话 / Vol.1 / #5 / 01v2 / (完) /
#   1-12集区间，以及分集标题末尾的裸集数（仅分集、每标题最多去一个）
# - 季号（S01 / 第2季 / Season 3）单独提取做兼容判断：一方没写季号视为兼容
# - 系列键相同 + 季号兼容 ⇒ 视为“命名相同”，合集可以取代分集
# - 跨季、画质不同、番名带数字（高达00）一律不匹配

def fold: ascii_downcase;

def is_kw: test("合集|全集|合订|全一卷|全季|完全版|complete|batch|anthology");

def cnmap: {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9};

def cn1($s):
  if $s == null or $s == "" then null else (cnmap[$s] // null) end;

def cn2int($t):
  if $t == null then null
  elif ($t | test("^[0-9]+$")) then ($t | tonumber)
  elif $t == "十" then 10
  elif ($t | test("十")) then
    ($t | split("十")) as $p
    | (if ($p[0] // "") == "" then 1 else cn1($p[0]) end) as $tens
    | (if (($p | length) > 1) then (if $p[1] == "" then 0 else cn1($p[1]) end) else 0 end) as $ones
    | if $tens == null or $ones == null then null else ($tens * 10 + $ones) end
  else cn1($t)
  end;

def season_re: "(?<![a-z0-9])(?:s(?<g1>[0-9]{1,3})|第\\s*(?<g2>[0-9一二三四五六七八九十]{1,4})\\s*季|season\\s*(?<g3>[0-9]{1,3}))";

# 注意：jq 1.7 的 match/capture 无匹配时返回空流而非报错，
# 所以必须先用 test() 判定再 capture；且先 fold（原始标题可能是大写 S01）
def season_of:
  fold
  | (if test(season_re) then capture(season_re) else null end) as $m
  | if $m == null then null
    else ([ $m.g1, $m.g2, $m.g3 ] | map(select(. != null and . != "")) | first) as $raw
    | if $raw == null then null else cn2int($raw) end
  end;

def markers: [
  "(?<![a-z0-9])s[0-9]{1,3}\\s?e[0-9]{1,3}",                                # S01E02 / s1 e2
  "(?<![a-z0-9])s[0-9]{1,3}(?![0-9a-z])",                                   # 独立的 S01
  "(?<![a-z0-9])(?:ep?|episode)\\s*[.\\-]?\\s?[0-9]{1,4}(?![0-9])",          # E02 / EP3 / Episode 04
  "第\\s*[0-9一二三四五六七八九十百]{1,6}\\s*[集话話]",                        # 第03集 / 第十二话
  "第\\s*[0-9一二三四五六七八九十]{1,4}\\s*季",                               # 第2季
  "vol(?:\\.|ume)?\\s?[0-9]{1,3}(?:\\s?(?:[-~]|至|到)\\s?[0-9]{1,3})?",      # Vol.1 / Vol.1-12
  "(?<![a-z0-9])[0-9]{1,3}\\s?(?:[-~]|至|到)\\s?[0-9]{1,3}(?![0-9])\\s*[集话話]?",  # 01-12集
  "(?<![0-9])[0-9]{1,3}[集话話]",                                            # 08话 / 12集
  "#\\s?[0-9]{1,4}",                                                         # #5
  "(?<![0-9])[0-9]{1,3}\\s?v[0-9](?![0-9])",                                 # 01v2 修正版
  "[([{（【]\\s*(?:完|end|fin)\\s*[)\\]】）\\]}]",                            # (完) / [END]
  "\\bend\\b"
];

def strip_bare:
  ([match("(?<![0-9a-z.\\-])([0-9]{1,3})(?![0-9a-z])"; "g")] | last) as $m
  | if $m == null then .
    else (.[0:$m.offset] + " " + .[($m.offset + $m.length):])
    end;

def strip_markers($allow_bare):
  reduce (markers[]) as $m (.; gsub($m; " "))
  | (if $allow_bare then strip_bare else . end)
  | gsub("\\s+"; " ") | gsub("^ | $"; "");

def key_for($is_col):
  fold
  | (if $is_col
     then gsub("合集|全集|合订|全一卷|全季|完全版|complete|batch|anthology"; " ") | strip_markers(false)
     else strip_markers(true)
     end)
  | gsub("[^\\p{L}\\p{Nd}]"; "");

def scompat($a; $b): ($a == null) or ($b == null) or ($a == $b);

def classify: ((.name | fold | is_kw) or ((.fc // -1) > 1));

def plan:
  (.items) as $items
  | ($items | map(. + {col: classify})) as $tagged
  | ($tagged | map(select(.col))) as $cols
  | ($tagged | map(select(.col | not))) as $eps
  | .hash as $h
  | (if $h == "" then null else ([ $tagged[] | select(.hash == $h) ] | first) // null end) as $me
  | (if $h == "" then "manual"
     elif $me == null then "notfound"
     elif ((($me.name | fold | is_kw) or ((($me.fc // -1) > 1))) | not) then "episode"
     else "collection"
     end) as $mode
  | if $mode == "notfound" or $mode == "episode" then
      {iscol: $mode, collections: [], deletions: []}
    else
      {iscol: $mode, collections: [ $cols[] | .name ],
       deletions:
         ([ $eps[] as $e
            | ($e.name | key_for(false)) as $ek
            | ($e.name | season_of) as $es
            | select(($ek // "") != "")
            | first($cols[] as $c
                | select((($c.name | key_for(true)) == $ek) and scompat($es; ($c.name | season_of)))
                | {hash: $e.hash, title: $e.name, matched: $c.name})
          ] | unique_by(.hash)
         | (if $h == "" then . else [ .[] | select(.hash != $h) ] end))}
    end;

plan