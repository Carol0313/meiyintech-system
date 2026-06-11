#!/bin/bash
# 镁印制版下单系统启动脚本（生产环境请勿使用 runserver，请用 Gunicorn + Systemd）
# 此脚本仅用于开发/测试环境临时启动

cd /home/magnesium/magnesium_order_platform
source venv/bin/activate

# 加载环境变量（从 .env 文件读取，不再硬编码密钥）
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# 如需启用OSS存储，请取消 settings.py 中 DEFAULT_FILE_STORAGE 的注释
# sed -i "s/^# DEFAULT_FILE_STORAGE/DEFAULT_FILE_STORAGE/" magnesium_order_platform/settings.py

# 停止旧服务
pkill -f runserver || true
sleep 2

# 启动开发服务器（⚠️ 生产环境请使用 deploy/magnesium.service + Gunicorn）
nohup python manage.py runserver 127.0.0.1:8000 > server.log 2>&1 &
sleep 3

# 检查服务状态
if ps aux | grep runserver | grep -v grep > /dev/null; then
    echo "✅ 开发服务器启动成功"
    ps aux | grep runserver | grep -v grep
else
    echo "❌ 服务启动失败，请检查日志"
    tail -n 20 server.log
fi
