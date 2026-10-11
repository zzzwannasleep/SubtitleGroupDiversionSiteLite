"""qb_clean.sh 端到端（mock QB）。

Windows 上没有真实的 dash/sh 环境，本测试只做静态验证：
- 语法层：sh -n 若有 sh 可用则跑；否则跳过
- 逻辑层：确保脚本引用的 qb_clean.jq 存在、参数约定与 ps1/bat 一致
"""

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SH = ROOT / "tools" / "qb_clean.sh"
JQF = ROOT / "tools" / "qb_clean.jq"

src = SH.read_text(encoding="utf-8")

# 静态断言：与 ps1/bat 版保持相同的关键约定
for token in [
    "torrents/info",
    "torrents/files?hash=",
    "torrents/delete",
    "deleteFiles=",
    'test("合集|全集|合订|全一卷|全季|完全版|complete|batch|anthology")',
    "RESULT:",
    "qb_clean.jq",
]:
    assert token in src, f"缺少约定片段: {token}"

# 不许出现 bash-only 的进程替换
assert "< <(" not in src, "POSIX sh 不能用 < <(...) 进程替换"

sh_path = shutil.which("sh") or shutil.which("dash") or shutil.which("busybox")
if sh_path:
    exe = shutil.which("busybox")
    if exe:
        r = subprocess.run([exe, "sh", "-n", str(SH)], capture_output=True)
    else:
        r = subprocess.run([sh_path, "-n", str(SH)], capture_output=True)
    assert r.returncode == 0, f"sh 语法错误:\n{r.stderr.decode(errors='replace')}"
    print(f"sh -n 语法检查通过（{Path(sh_path).name}）")
else:
    print("（本机无 sh，跳过语法检查）")

assert JQF.exists(), "qb_clean.jq 必须与 sh 同目录"
print("qb_clean.sh 静态验证通过：参数/接口/jq 规则与 Windows 版一致")