@echo off
chcp 65001 >nul
echo ========================================
echo  镁印制版下单系统 - 本地开发启动脚本
echo ========================================
echo.

REM 设置 OSS 环境变量（本地开发使用公网）
set OSS_INTERNAL=false

echo 当前环境变量：
echo   OSS_ACCESS_KEY_ID: %OSS_ACCESS_KEY_ID%
echo   OSS_INTERNAL: %OSS_INTERNAL%
echo.

REM 激活虚拟环境并启动
call "%~dp0venv\Scripts\activate.bat"
"%~dp0venv\Scripts\python.exe" "%~dp0manage.py" runserver

pause
