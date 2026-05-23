@echo off
chcp 65001 > nul
echo ==========================================
echo RSS种子站点 - Windows后台运行工具
echo ==========================================
echo.
echo 请选择运行方式:
echo.
echo [1] 前台运行 (带控制台窗口)
echo [2] 后台运行 (隐藏窗口，使用pythonw)
echo [3] 安装为Windows服务 (需要管理员权限)
echo [4] 停止后台运行
echo [5] 查看运行状态
echo.
set /p choice="请输入选项 (1-5): "

if "%choice%"=="1" goto foreground
if "%choice%"=="2" goto background
if "%choice%"=="3" goto service_install
if "%choice%"=="4" goto stop
if "%choice%"=="5" goto status

echo 无效选项
pause
exit /b 1

:foreground
echo.
echo 正在前台运行...
call start.bat
exit /b

:background
echo.
echo 正在后台运行...
if not exist "venv" (
    echo 创建虚拟环境...
    python -m venv venv
)
call venv\Scripts\activate
pip install -q -r requirements.txt

if not exist ".env" (
    copy .env.example .env > nul
    echo 已创建默认配置文件，请编辑 .env 修改密码！
)

REM 使用pythonw隐藏窗口运行
start /B "" venv\Scripts\pythonw.exe -c "import os; os.environ['FLASK_ENV']='production'; from app import app; app.run(host='0.0.0.0', port=5000)" > logs\app.log 2>&1

echo.
echo ==========================================
echo 应用已在后台启动！
echo ==========================================
echo.
echo 访问地址: http://127.0.0.1:5000
echo 日志文件: logs\app.log
echo.
echo 使用选项 [4] 停止运行
echo.
pause
exit /b

:service_install
echo.
echo 安装为Windows服务...
echo 注意：需要管理员权限！

REM 检查nssm
where nssm > nul 2>&1
if errorlevel 1 (
    echo.
    echo [错误] 未找到nssm，请先下载nssm:
    echo https://nssm.cc/download
    echo 将nssm.exe放入系统PATH中
    pause
    exit /b 1
)

REM 获取当前路径
set "APP_PATH=%CD%"

REM 安装服务
nssm install RSS-Torrent-Site "venv\Scripts\python.exe" "%APP_PATH%\app.py"
nssm set RSS-Torrent-Site DisplayName "RSS Torrent Site"
nssm set RSS-Torrent-Site Description "RSS种子站点服务"
nssm set RSS-Torrent-Site Start SERVICE_AUTO_START
nssm set RSS-Torrent-Site AppDirectory %APP_PATH%
nssm set RSS-Torrent-Site AppStdout %APP_PATH%\logs\service.log
nssm set RSS-Torrent-Site AppStderr %APP_PATH%\logs\service-error.log

echo.
echo 服务安装完成！
echo 启动服务: net start RSS-Torrent-Site
echo 停止服务: net stop RSS-Torrent-Site
echo.
pause
exit /b

:stop
echo.
echo 正在停止后台运行...
taskkill /F /IM pythonw.exe > nul 2>&1
taskkill /F /IM python.exe > nul 2>&1
echo 已停止
echo.
pause
exit /b

:status
echo.
echo 检查运行状态...
tasklist | findstr python
echo.
echo 如果看到python.exe或pythonw.exe进程，说明正在运行
echo.
pause
exit /b
