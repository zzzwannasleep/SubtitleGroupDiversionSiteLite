@echo off
rem qBittorrent 合集/分集清理 —— Windows 入口（调系统自带 PowerShell，无需安装任何东西）
rem
rem 用法一（推荐，全自动）：把下面这条命令粘到
rem   qBittorrent → 设置 → 下载 → 「Torrent 完成时运行外部程序」：
rem     "D:\完整路径\qb_clean.bat" "%I"
rem   合集下载完成的那一刻，自动删掉 QB 里命名相同的分集任务。
rem
rem 用法二（手动全量清理）：双击本文件 = 只看报告不删除；qb_clean.bat --apply = 真正删除
rem 配置（地址/账号/密码）在 qb_clean.ps1 顶部，改一次即可。
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0qb_clean.ps1" %*
