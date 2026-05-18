@echo off
chcp 65001 >nul
echo ==========================================
echo   闪电制版系统 - Django 开发服务器启动器
echo ==========================================
echo.

REM 查找并终止已有的 Python runserver 进程
echo [1/3] 正在检查并关闭旧的服务器进程...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *runserver*" >nul 2>&1
taskkill /F /IM python.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo       已清理旧进程
echo.

REM 切换到项目目录
echo [2/3] 正在启动 Django 开发服务器...
cd /d "D:\HuaweiMoveData\Users\李睿依1106\Desktop\镁印制版下单系统"

REM 启动服务器（同时监听 IPv4 和 IPv6 的 localhost）
start "Django Server" python manage.py runserver 0.0.0.0:8000
timeout /t 3 /nobreak >nul
echo       服务器已启动
echo.

REM 测试访问
echo [3/3] 正在测试服务器响应...
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8000/login/ > temp_status.txt
set /p STATUS=<temp_status.txt
del temp_status.txt

if "%STATUS%"=="200" (
    echo       测试通过！状态码: %STATUS%
    echo.
    echo ==========================================
    echo   服务器启动成功！
    echo ==========================================
    echo.
    echo   请用浏览器访问以下地址：
    echo.
    echo   http://127.0.0.1:8000/login/
    echo   http://localhost:8000/login/
    echo.
    echo   测试账号：
    echo     平台管理员：13800000000 / admin123
    echo     商户账号：   13800138000 / admin123
    echo     客户账号：   13900139000 / admin123
    echo.
    echo   按任意键打开浏览器...
    pause >nul
    start http://127.0.0.1:8000/login/
) else (
    echo       测试失败！状态码: %STATUS%
    echo.
    echo   服务器可能启动失败，请检查错误信息。
    echo   窗口不要关闭，查看上面的错误提示。
    echo.
    pause
)
