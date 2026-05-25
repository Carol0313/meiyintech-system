#!/bin/bash
# ============================================================
# 镁印制版下单系统 - 阿里云ECS一键部署脚本
# 使用方法：
#   1. 将代码上传到服务器 /home/magnesium/magnesium_order_platform
#   2. cd /home/magnesium/magnesium_order_platform
#   3. chmod +x deploy/deploy.sh
#   4. sudo bash deploy/deploy.sh
# ============================================================

set -e  # 遇到错误立即退出

PROJECT_DIR="/home/magnesium/magnesium_order_platform"
VENV_DIR="$PROJECT_DIR/venv"
DB_NAME="magnesium_order_db"
DB_USER="magnesium_user"
DB_PASSWORD="$(openssl rand -base64 32)"  # 自动生成随机密码
DJANGO_SECRET_KEY="$(openssl rand -base64 50)"

echo "=========================================="
echo "  镁印制版下单系统 - 阿里云部署脚本"
echo "=========================================="
echo ""

# -------------------- 步骤1：系统更新 --------------------
echo "[1/10] 更新系统软件包..."
apt-get update -y
apt-get upgrade -y

# -------------------- 步骤2：安装系统依赖 --------------------
echo "[2/10] 安装系统依赖..."
apt-get install -y \
    python3 python3-pip python3-venv \
    nginx postgresql postgresql-contrib \
    git curl wget vim \
    build-essential libpq-dev \
    libffi-dev libssl-dev \
    pkg-config

# -------------------- 步骤3：创建项目用户和目录 --------------------
echo "[3/10] 创建项目目录..."
mkdir -p /home/magnesium
# 如果当前目录不是项目目录，则提示
if [ ! -f "$PROJECT_DIR/manage.py" ]; then
    echo "错误：未找到 manage.py，请先将项目代码上传到 $PROJECT_DIR"
    exit 1
fi

# -------------------- 步骤4：配置PostgreSQL --------------------
echo "[4/10] 配置 PostgreSQL 数据库..."
systemctl start postgresql
systemctl enable postgresql

# 创建数据库和用户
su - postgres -c "psql -c \"CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';\" 2>/dev/null || true"
su - postgres -c "psql -c \"CREATE DATABASE $DB_NAME OWNER $DB_USER;\" 2>/dev/null || true"
su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;\""
su - postgres -c "psql -c \"ALTER USER $DB_USER CREATEDB;\""

echo "  数据库：$DB_NAME"
echo "  用户名：$DB_USER"
echo "  密码：$DB_PASSWORD"

# -------------------- 步骤5：创建Python虚拟环境 --------------------
echo "[5/10] 创建 Python 虚拟环境..."
cd "$PROJECT_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# -------------------- 步骤6：配置环境变量 --------------------
echo "[6/10] 配置环境变量..."
cat > "$PROJECT_DIR/.env" << EOF
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=$(curl -s ifconfig.me)
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DB_ENGINE=postgresql
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASSWORD=$DB_PASSWORD
DB_HOST=localhost
DB_PORT=5432
EOF

echo "  密钥：$DJANGO_SECRET_KEY"
echo "  数据库密码：$DB_PASSWORD"
echo "  注意：.env 文件已保存，请妥善保管！"

# -------------------- 步骤7：Django数据库迁移和静态文件 --------------------
echo "[7/10] Django 数据库迁移和静态文件收集..."
cd "$PROJECT_DIR"
export $(cat .env | xargs)
python manage.py migrate
python manage.py collectstatic --noinput

# 创建超级用户（可选）
echo ""
echo "  是否创建 Django 超级用户？(y/n)"
read -r CREATE_SUPERUSER
if [ "$CREATE_SUPERUSER" = "y" ]; then
    python manage.py createsuperuser
fi

# -------------------- 步骤8：创建日志目录 --------------------
echo "[8/10] 创建日志目录..."
mkdir -p /var/log/gunicorn
mkdir -p /var/log/nginx

# -------------------- 步骤9：配置Systemd服务 --------------------
echo "[9/10] 配置 Systemd 服务..."
cp "$PROJECT_DIR/deploy/magnesium.service" /etc/systemd/system/magnesium.service
# 替换服务文件中的环境变量
sed -i "s|your-production-secret-key-here-change-it|$DJANGO_SECRET_KEY|g" /etc/systemd/system/magnesium.service
sed -i "s|your-db-password|$DB_PASSWORD|g" /etc/systemd/system/magnesium.service
sed -i "s|your-domain.com,www.your-domain.com|$(curl -s ifconfig.me)|g" /etc/systemd/system/magnesium.service

systemctl daemon-reload
systemctl enable magnesium
systemctl start magnesium

# -------------------- 步骤10：配置Nginx --------------------
echo "[10/10] 配置 Nginx..."
cp "$PROJECT_DIR/deploy/nginx.conf" /etc/nginx/sites-available/magnesium
sed -i "s|your-domain.com www.your-domain.com|$(curl -s ifconfig.me)|g" /etc/nginx/sites-available/magnesium

# 删除默认站点，启用新站点
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/magnesium /etc/nginx/sites-enabled/magnesium

# 测试配置并重载
nginx -t
systemctl reload nginx
systemctl enable nginx

# -------------------- 完成 --------------------
echo ""
echo "=========================================="
echo "  部署完成！"
echo "=========================================="
echo ""
echo "  访问地址：http://$(curl -s ifconfig.me)"
echo "  项目目录：$PROJECT_DIR"
echo "  虚拟环境：$VENV_DIR"
echo ""
echo "  数据库信息（已保存到 .env）："
echo "    名称：$DB_NAME"
echo "    用户：$DB_USER"
echo "    密码：$DB_PASSWORD"
echo ""
echo "  常用命令："
echo "    查看服务状态：sudo systemctl status magnesium"
echo "    重启服务：sudo systemctl restart magnesium"
echo "    查看日志：sudo tail -f /var/log/gunicorn/magnesium_error.log"
echo "    重启Nginx：sudo systemctl reload nginx"
echo ""
echo "  下一步建议："
echo "    1. 配置域名解析到服务器IP"
echo "    2. 申请SSL证书（推荐使用 certbot）"
echo "    3. 配置阿里云OSS（生产环境建议启用）"
echo "    4. 配置快递100 API Key"
echo ""
