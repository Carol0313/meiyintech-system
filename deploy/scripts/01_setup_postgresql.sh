#!/bin/bash
# PostgreSQL 安装与配置脚本
# 适用系统: CentOS 8 / Alibaba Cloud Linux 3
# 用法: bash deploy/scripts/01_setup_postgresql.sh

set -e

PROJECT_DIR="/home/magnesium/magnesium_order_platform"
DB_NAME="${DB_NAME:-magnesium_db}"
DB_USER="${DB_USER:-magnesium_user}"
DB_PASS="${DB_PASSWORD:-magnesium_pass_2026}"

echo "=== 镁印制版系统: PostgreSQL 安装与配置 ==="

# 1. 检查是否已安装 PostgreSQL
if command -v psql &> /dev/null; then
    echo "[1/6] PostgreSQL 已安装，跳过安装步骤"
    PG_VERSION=$(psql --version | awk '{print $3}')
    echo "当前版本: $PG_VERSION"
else
    echo "[1/6] 安装 PostgreSQL..."
    # 安装 PostgreSQL 14
    sudo dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-8-x86_64/pgdg-redhat-repo-latest.noarch.rpm
    sudo dnf -qy module disable postgresql
    sudo dnf install -y postgresql14-server postgresql14-contrib
    sudo /usr/pgsql-14/bin/postgresql-14-setup initdb
    sudo systemctl enable postgresql-14
    sudo systemctl start postgresql-14
fi

# 2. 修改 pg_hba.conf 为 md5 认证
echo "[2/6] 配置 PostgreSQL 认证方式..."
PG_HBA=$(sudo find /var/lib/pgsql -name "pg_hba.conf" | head -n 1)
if [ -z "$PG_HBA" ]; then
    echo "错误: 找不到 pg_hba.conf 文件"
    exit 1
fi

echo "pg_hba.conf 路径: $PG_HBA"

# 备份原配置
sudo cp "$PG_HBA" "$PG_HBA.backup.$(date +%Y%m%d%H%M%S)"

# 修改认证方式
sudo sed -i 's/^host.*all.*all.*127.0.0.1\/32.*/host    all             all             127.0.0.1\/32            md5/' "$PG_HBA"
sudo sed -i 's/^host.*all.*all.*::1\/128.*/host    all             all             ::1\/128                 md5/' "$PG_HBA"

# 确保有 IPv4 本地连接规则
if ! grep -q "127.0.0.1/32" "$PG_HBA"; then
    echo "host    all             all             127.0.0.1/32            md5" | sudo tee -a "$PG_HBA"
fi
if ! grep -q "::1/128" "$PG_HBA"; then
    echo "host    all             all             ::1/128                 md5" | sudo tee -a "$PG_HBA"
fi

# 3. 修改监听地址
echo "[3/6] 配置 PostgreSQL 监听地址..."
POSTGRESQL_CONF=$(sudo find /var/lib/pgsql -name "postgresql.conf" | head -n 1)
if [ -n "$POSTGRESQL_CONF" ]; then
    sudo cp "$POSTGRESQL_CONF" "$POSTGRESQL_CONF.backup.$(date +%Y%m%d%H%M%S)"
    sudo sed -i "s/^#*listen_addresses.*/listen_addresses = 'localhost'/" "$POSTGRESQL_CONF"
    if ! grep -q "^listen_addresses" "$POSTGRESQL_CONF"; then
        echo "listen_addresses = 'localhost'" | sudo tee -a "$POSTGRESQL_CONF"
    fi
fi

# 4. 重启 PostgreSQL
echo "[4/6] 重启 PostgreSQL..."
if systemctl list-unit-files | grep -q "postgresql-14"; then
    sudo systemctl restart postgresql-14
elif systemctl list-unit-files | grep -q "postgresql"; then
    sudo systemctl restart postgresql
else
    echo "警告: 找不到 PostgreSQL 服务，请手动重启"
fi

# 5. 创建数据库和用户
echo "[5/6] 创建数据库和用户..."
sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS ${DB_NAME};
DROP USER IF EXISTS ${DB_USER};
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
\q
EOF

# 6. 测试连接
echo "[6/6] 测试数据库连接..."
export PGPASSWORD="$DB_PASS"
psql -h localhost -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "数据库连接成功!"
else
    echo "数据库连接失败，请检查配置"
    exit 1
fi

echo ""
echo "=== PostgreSQL 配置完成 ==="
echo "数据库名: $DB_NAME"
echo "用户名: $DB_USER"
echo "密码: $DB_PASS"
echo ""
echo "请记录以上信息，下一步执行迁移脚本时会用到。"
