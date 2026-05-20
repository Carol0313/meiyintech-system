@echo off
chcp 65001 >nul
echo ==========================================
echo   闪电制版系统 - Django 开发服务器启动器
echo ==========================================
echo.

echo [1/3] 正在检查并关闭旧的服务器进程...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000') do (
    taskkill /PID %%a /F >nul 2>&1
)
timeout /t 2 /nobreak >nul
echo       已清理旧进程
echo.

echo [2/3] 正在启动 Django 开发服务器...
cd /d "D:\HuaweiMoveData\Users\李睿依1106\Desktop\镁印制版下单系统"

echo.
echo   服务器已启动，请用浏览器访问：
echo   http://127.0.0.1:8000/login/
echo.
echo   测试账号：
echo     平台管理员：13800000000 / admin123
echo     商户账号：   13800138000 / admin123
echo     客户账号：   13900139000 / admin123
echo.
echo   按 Ctrl+C 可以停止服务器
echo ==========================================

python manage.py runserver 0.0.0.0:8000
