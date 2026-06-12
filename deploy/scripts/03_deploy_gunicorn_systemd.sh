#!/bin/bash
# Gunicorn + systemd + Nginx 生产环境部署脚本
# 用法: bash deploy/scripts/03_deploy_gunicorn_systemd.sh

set -e

PROJECT_DIR="/home/magnesium/magnesium_order_platform"
SERVICE_NAME="magnesium"
DOMAIN="www.zhibanhome.com"

echo "=== 镁印制版系统: Gunicorn + systemd + Nginx 部署 ==="

cd "$PROJECT_DIR"
source venv/bin/activate

# 1. 检查依赖
echo "[1/8] 检查 Gunicorn..."
if ! pip show gunicorn > /dev/null 2>&1; then
    echo "安装 gunicorn..."
    pip install gunicorn
fi

# 2. 收集静态文件
echo "[2/8] 收集静态文件..."
python manage.py collectstatic --noinput

# 3. 创建日志目录
echo "[3/8] 创建日志目录..."
sudo mkdir -p /var/log/gunicorn
sudo mkdir -p /var/log/nginx
sudo chown -R root:root /var/log/gunicorn

# 4. 复制 systemd 服务文件
echo "[4/8] 配置 systemd 服务..."
sudo cp "$PROJECT_DIR/deploy/magnesium.service" "/etc/systemd/system/${SERVICE_NAME}.service"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"

# 5. 停止旧 runserver 进程
echo "[5/8] 停止旧 runserver 进程..."
pkill -f "manage.py runserver" || true
sleep 2

# 6. 启动 Gunicorn 服务
echo "[6/8] 启动 Gunicorn 服务..."
sudo systemctl start "$SERVICE_NAME"
sleep 3
sudo systemctl status "$SERVICE_NAME" --no-pager

# 7. 配置 Nginx
echo "[7/8] 配置 Nginx..."
# 优先使用 SSL 配置
if [ -f "/etc/nginx/conf.d/magnesium.conf" ]; then
    echo "备份现有 Nginx 配置..."
    sudo cp /etc/nginx/conf.d/magnesium.conf "/etc/nginx/conf.d/magnesium.conf.backup.$(date +%Y%m%d%H%M%S)"
fi

# 检查是否有 SSL 证书
SSL_CERT="/etc/nginx/ssl/${DOMAIN}.pem"
SSL_KEY="/etc/nginx/ssl/${DOMAIN}.key"

if [ -f "$SSL_CERT" ] && [ -f "$SSL_KEY" ]; then
    echo "检测到 SSL 证书，使用 HTTPS 配置..."
    sudo cp "$PROJECT_DIR/deploy/nginx_ssl.conf" /etc/nginx/conf.d/magnesium.conf
    sudo sed -i "s|/path/to/your_aliyun_cert.pem|$SSL_CERT|g" /etc/nginx/conf.d/magnesium.conf
    sudo sed -i "s|/path/to/your_aliyun_cert.key|$SSL_KEY|g" /etc/nginx/conf.d/magnesium.conf
else
    echo "未检测到 SSL 证书，使用 HTTP 配置..."
    sudo cp "$PROJECT_DIR/deploy/nginx.conf" /etc/nginx/conf.d/magnesium.conf
fi

# 测试 Nginx 配置
sudo nginx -t

# 8. 启动/重启 Nginx
echo "[8/8] 启动/重启 Nginx..."
if systemctl is-active --quiet nginx; then
    sudo nginx -s reload
else
    sudo systemctl start nginx
fi

# 9. 最终检查
echo ""
echo "=== 部署完成 ==="
echo "检查服务状态:"
sudo systemctl status "$SERVICE_NAME" --no-pager -l || true
echo ""
echo "检查端口监听:"
ss -tlnp | grep -E "8000|80|443" || true
echo ""
echo "访问测试:"
curl -s -o /dev/null -w "HTTP状态: %{http_code}\n" "http://127.0.0.1:8000" || true
