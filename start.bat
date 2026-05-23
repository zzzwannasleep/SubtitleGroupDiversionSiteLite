@echo off
chcp 65001 > nul
echo ==========================================
echo RSS种子站点 - Windows启动脚本
echo ==========================================
echo.

REM 检查Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 检查虚拟环境
if not exist "venv" (
    echo [1/4] 创建虚拟环境...
    python -m venv venv
)

echo [2/4] 激活虚拟环境...
call venv\Scripts\activate

echo [3/4] 安装/更新依赖...
pip install -q -r requirements.txt

REM 检查.env文件
if not exist ".env" (
    echo [提示] 创建默认配置文件 .env
    copy .env.example .env > nul
    echo 请编辑 .env 文件修改默认密码和密钥！
    echo.
)

echo [4/4] 启动应用...
echo.
echo ==========================================
echo 应用已启动！
echo ==========================================
echo.
echo 访问地址: http://127.0.0.1:5000
echo RSS地址: http://127.0.0.1:5000/rss.xml
echo.
echo 默认管理员账号: admin
echo 默认管理员密码: admin
echo.
echo 按 Ctrl+C 停止运行
echo.

python app.py

pause
