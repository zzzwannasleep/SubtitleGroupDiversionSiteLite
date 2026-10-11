# qb_clean.ps1 —— qBittorrent 合集/分集清理（零依赖，Windows 自带 PowerShell）
#
# 用法一（推荐，全自动）：把下面这一条命令粘到
#   qBittorrent → 设置 → 下载 → 「Torrent 完成时运行外部程序」：
#     powershell -NoProfile -ExecutionPolicy Bypass -File "改成本机的qb_clean.ps1完整路径" "%I"
#   合集下载完成的那一刻，自动删掉 QB 里命名相同的分集任务。
#
# 用法二（手动全量清理，可选）：
#   powershell -ExecutionPolicy Bypass -File qb_clean.ps1          # 先看报告，不删除
#   powershell -ExecutionPolicy Bypass -File qb_clean.ps1 -Apply   # 确认报告后真正删除
#
# 可选开关：-KeepFiles 只删任务、保留硬盘文件（默认连文件一起删，内容已包含在合集里）
# 匹配规则保守：跨季、画质不同、系列名不同的一律不删。详情见仓库 README。

param(
    [string]$Hash,                       # %I —— 由 qBittorrent 传入（事件模式）
    [string]$Name,                       # %N —— 可选，备用
    # ↓↓↓ 把这三行改成你的 qBittorrent 配置（设置 → Web UI 里开启）↓↓↓
    [string]$Url      = "http://127.0.0.1:8080",
    [string]$User     = "admin",
    [string]$Password = "请改成你的密码",
    # ↑↑↑ 改完这三行即可 ↑↑↑
    [switch]$Apply,                      # 手动模式：确认报告后真正删除
    [switch]$KeepFiles                   # 只删任务、保留硬盘文件
)
$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

# 本机 QB 不走系统代理（系统挂了梯子时 Invoke-WebRequest 会被代理截走 localhost 请求）
$bHost = ([Uri]$Url).Host
if ($bHost -eq '127.0.0.1' -or $bHost -eq 'localhost' -or $bHost -eq '::1') {
    [System.Net.WebRequest]::DefaultWebProxy = $null
}

if ($Password -eq "请改成你的密码") {
    Write-Output "RESULT: error password-not-configured deleted=0"
    Write-Host "请先编辑 qb_clean.ps1 顶部的 Url / User / Password 三行配置"
    exit 1
}

# ==================== 合集/分集匹配（与站点 src/episode_match.py 同规则） ====================

$CollectionKw = '合集|全集|合订|全一卷|全季|完全版|complete|batch|anthology'
$SeasonToken = '(?<![a-z0-9])(?:s(\d{1,3})|第\s*([0-9一二三四五六七八九十]{1,4})\s*季|season\s*(\d{1,3}))'
$Markers = @(
    '(?<![a-z0-9])s\d{1,3}\s?e\d{1,3}',                                      # S01E02 / s1 e2
    '(?<![a-z0-9])s\d{1,3}(?![0-9a-z])',                                     # 独立的 S01
    '(?<![a-z0-9])(?:ep?|episode)\s*[.\-]?\s?\d{1,4}(?![0-9])',               # E02 / EP3 / Episode 04
    '第\s*[0-9一二三四五六七八九十百]{1,6}\s*[集话話]',                         # 第03集 / 第十二话
    '第\s*[0-9一二三四五六七八九十]{1,4}\s*季',                                # 第2季
    'vol(?:\.|ume)?\s?\d{1,3}(?:\s?(?:[-~]|至|到)\s?\d{1,3})?',               # Vol.1 / Vol.1-12
    '(?<![a-z0-9])\d{1,3}\s?(?:[-~]|至|到)\s?\d{1,3}(?![0-9])\s*[集话話]?',    # 01-12集
    '(?<![0-9])\d{1,3}[集话話]',                                              # 08话 / 12集
    '#\s?\d{1,4}',                                                            # #5
    '(?<![0-9])\d{1,3}\s?v\d(?![0-9])',                                       # 01v2 修正版
    '[([{（【]\s*(?:完|end|fin)\s*[)\]】）\}]',                                # (完) / [END]
    '\bend\b'
)
$BareEpisode = '(?<![0-9a-z.\-])(\d{1,3})(?![0-9a-z])'

function Get-Fold([string]$s) {
    if (-not $s) { return '' }
    return $s.Normalize([System.Text.NormalizationForm]::FormKC).ToLowerInvariant()
}

function Test-CollectionKeyword([string]$title) {
    return [regex]::IsMatch((Get-Fold $title), $CollectionKw)
}

function Test-Collection([string]$title, [int]$fileCount) {
    if (Test-CollectionKeyword $title) { return $true }
    return ($fileCount -gt 1)
}

function Remove-Markers([string]$t, [bool]$allowBare) {
    foreach ($p in $Markers) { $t = [regex]::Replace($t, $p, ' ') }
    if ($allowBare) {
        $ms = [regex]::Matches($t, $BareEpisode)
        if ($ms.Count -gt 0) {
            $m = $ms[$ms.Count - 1]
            $t = $t.Substring(0, $m.Index) + ' ' + $t.Substring($m.Index + $m.Length)
        }
    }
    return ([regex]::Replace($t, '\s+', ' ')).Trim()
}

function Get-SeriesKey([string]$title, [bool]$isCollection) {
    $t = Get-Fold $title
    if ($isCollection) { $t = [regex]::Replace($t, $CollectionKw, ' ') }
    $t = Remove-Markers $t (-not $isCollection)
    # 只留字母/数字（含中文）：兼容 “.”、“_”、“-”、空格等写法差异
    return [regex]::Replace($t, '[^\p{L}\p{Nd}]', '')
}

$CnNum = @{ '一' = 1; '二' = 2; '三' = 3; '四' = 4; '五' = 5; '六' = 6; '七' = 7; '八' = 8; '九' = 9 }

function ConvertFrom-CnNumber([string]$t) {
    if (-not $t) { return $null }
    if ($t -match '^[0-9]+$') { return [int]$t }
    if ($t -eq '十') { return 10 }
    if ($t.Contains('十')) {
        $parts = $t -split '十'
        $tens = 1; $ones = 0
        if ($parts[0]) {
            if (-not $CnNum.ContainsKey($parts[0])) { return $null }
            $tens = $CnNum[$parts[0]]
        }
        if ($parts.Count -gt 1 -and $parts[1]) {
            if (-not $CnNum.ContainsKey($parts[1])) { return $null }
            $ones = $CnNum[$parts[1]]
        }
        return $tens * 10 + $ones
    }
    if ($CnNum.ContainsKey($t)) { return $CnNum[$t] }
    return $null
}

function Get-Season([string]$title) {
    $m = [regex]::Match((Get-Fold $title), $SeasonToken)
    if (-not $m.Success) { return $null }
    foreach ($g in @($m.Groups[1].Value, $m.Groups[2].Value, $m.Groups[3].Value)) {
        if ($g) { $n = ConvertFrom-CnNumber $g; if ($n) { return $n } }
    }
    return $null
}

function Test-SeasonCompat($a, $b) {
    if ($null -eq $a -or $null -eq $b) { return $true }
    return ($a -eq $b)
}

function Plan-Cleanup($items) {
    $collections = @(); $episodes = @()
    foreach ($i in @($items)) {
        if (Test-Collection $i.title $i.file_count) { $collections += $i } else { $episodes += $i }
    }
    $deletions = @()
    foreach ($ep in @($episodes)) {
        $key = Get-SeriesKey $ep.title $false
        if (-not $key) { continue }
        $season = Get-Season $ep.title
        foreach ($col in @($collections)) {
            if ((Get-SeriesKey $col.title $true) -eq $key -and (Test-SeasonCompat $season (Get-Season $col.title))) {
                $deletions += [pscustomobject]@{ hash = $ep.hash; title = $ep.title; matched = $col.title }
                break
            }
        }
    }
    return [pscustomobject]@{ collections = @($collections); deletions = @($deletions) }
}

# ==================== qBittorrent WebUI API ====================

try {
    $login = Invoke-WebRequest -UseBasicParsing -Uri "$Url/api/v2/auth/login" -Method Post `
        -Body @{ username = $User; password = $Password } -SessionVariable sess
    # PS5.1 对非 HTML 响应返回 byte[]，先统一转成字符串再比对
    $content = if ($login.Content -is [byte[]]) { [Text.Encoding]::UTF8.GetString($login.Content) } else { "$($login.Content)" }
    if ($content -notmatch 'Ok') { throw "登录响应异常：$content" }
} catch {
    Write-Output "RESULT: error login-failed deleted=0"
    Write-Host "QB 登录失败：$($_.Exception.Message)"
    exit 1
}

# JSON 请求统一走「原始字节 + 显式 UTF-8 解码」：
# PS5.1 对不带 charset 的 application/json 会用 ISO-8859-1 解码，中文种子名会乱码，
# 而 qBittorrent 恰恰经常不带 charset。
function Get-QBJson($sess, $uri) {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri $uri -WebSession $sess
    $bytes = $resp.Content
    if ($bytes -isnot [byte[]]) { $bytes = [Text.Encoding]::UTF8.GetBytes($bytes) }
    $parsed = ConvertFrom-Json ([Text.Encoding]::UTF8.GetString($bytes))
    # PS5.1 的 ConvertFrom-Json 对 JSON 数组返回单个数组对象而非逐个元素，
    # 管道过一遍强制展开；单对象 JSON 原样通过
    return @($parsed | ForEach-Object { $_ })
}

$torrents = @(Get-QBJson $sess "$Url/api/v2/torrents/info")

# 组装任务清单（标题关键词即可判合集的不查文件数，省一次请求）
$items = @()
foreach ($x in $torrents) {
    $kw = Test-CollectionKeyword $x.name
    $fc = if ($kw) { -1 } else { @(Get-QBJson $sess "$Url/api/v2/torrents/files?hash=$($x.hash)").Count }
    $items += [pscustomobject]@{ hash = $x.hash; title = $x.name; file_count = $fc }
}

# 事件模式：只有当完成的这个种子本身是合集时才动手
$me = $null
if ($Hash) {
    $h = $Hash.ToLower()
    $me = @($items | Where-Object { $_.hash -eq $h })
    if ($me.Count -eq 0) {
        Write-Output "RESULT: torrent-not-found deleted=0"
        exit 0
    }
    if (-not (Test-Collection $me[0].title $me[0].file_count)) {
        Write-Output "RESULT: not-a-collection deleted=0"
        exit 0
    }
}

$plan = Plan-Cleanup $items
$deletions = $plan.deletions
if ($Hash) { $deletions = @($deletions | Where-Object { $_.hash -ne $me[0].hash }) }  # 兜底：永不删自己

Write-Host ""
Write-Host "合集 $($plan.collections.Count) 个："
foreach ($c in $plan.collections) { Write-Host "  [合集] $($c.title)" }
Write-Host ""
Write-Host "待删分集 $($deletions.Count) 个："
foreach ($d in $deletions) { Write-Host "  [分集] $($d.title)  <- 匹配合集：$($d.matched)" }

$deletedCount = 0
$hashes = @($deletions | ForEach-Object { $_.hash } | Where-Object { $_ -match '^[0-9a-f]{40}$' })

if ($hashes.Count -eq 0) {
    Write-Output "RESULT: collections=$($plan.collections.Count) deletions=0 deleted=0"
    exit 0
}

if (-not $Hash -and -not $Apply) {
    Write-Host ""
    Write-Host "以上为报告，未删除任何东西。确认无误后加 -Apply 执行。"
    Write-Output "RESULT: collections=$($plan.collections.Count) deletions=$($deletions.Count) deleted=0"
    exit 0
}

Invoke-WebRequest -UseBasicParsing -Uri "$Url/api/v2/torrents/delete" -Method Post `
    -Body @{ hashes = ($hashes -join '|'); deleteFiles = ($(if ($KeepFiles) { 'false' } else { 'true' })) } `
    -WebSession $sess | Out-Null
$deletedCount = $hashes.Count
Write-Host ""
Write-Host "已删除 $deletedCount 个分集任务$(if ($KeepFiles) { '（保留硬盘文件）' } else { '（含硬盘文件）' })"
Write-Output "RESULT: collections=$($plan.collections.Count) deletions=$($deletions.Count) deleted=$deletedCount"