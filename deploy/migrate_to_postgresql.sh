#!/bin/bash
# SQLite → PostgreSQL 数据迁移脚本
# 用法: bash deploy/migrate_to_postgresql.sh
# 前置条件: PostgreSQL已安装，pg_hba.conf已修复

set -e

echo "=== 镁印制版系统: SQLite → PostgreSQL 迁移 ==="

PROJECT_DIR="/home/magnesium/magnesium_order_platform"
DB_NAME="magnesium_db"
DB_USER="magnesium_user"
DB_PASS="${DB_PASSWORD:-magnesium_pass_2026}"
BACKUP_DIR="${PROJECT_DIR}/backups/$(date +%Y%m%d_%H%M%S)"

cd "$PROJECT_DIR"
source venv/bin/activate

# 1. 备份当前SQLite数据库
echo "[1/7] 备份SQLite数据库..."
mkdir -p "$BACKUP_DIR"
cp db.sqlite3 "$BACKUP_DIR/db.sqlite3.backup"
echo "备份已保存到: $BACKUP_DIR"

# 2. 导出所有数据为JSON
echo "[2/7] 导出SQLite数据为JSON..."
python manage.py dumpdata --all --indent 2 > "$BACKUP_DIR/full_backup.json"
echo "数据导出完成: $BACKUP_DIR/full_backup.json"

# 3. 创建PostgreSQL数据库和用户
echo "[3/7] 创建PostgreSQL数据库和用户..."
sudo -u postgres psql <<EOF
DROP DATABASE IF EXISTS ${DB_NAME};
DROP USER IF EXISTS ${DB_USER};
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
\q
EOF
echo "PostgreSQL数据库已创建"

# 4. 设置环境变量并测试连接
echo "[4/7] 配置环境变量..."
export DB_ENGINE=postgresql
export DB_NAME=$DB_NAME
export DB_USER=$DB_USER
export DB_PASSWORD=$DB_PASS
export DB_HOST=localhost
export DB_PORT=5432

# 5. 在PostgreSQL上执行迁移
echo "[5/7] 在PostgreSQL上执行Django迁移..."
python manage.py migrate --run-syncdb
echo "迁移完成"

# 6. 导入数据
echo "[6/7] 导入数据到PostgreSQL..."
python manage.py loaddata "$BACKUP_DIR/full_backup.json"
echo "数据导入完成"

# 7. 验证
echo "[7/7] 验证数据完整性..."
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'magnesium_order_platform.settings')
import django
django.setup()
from apps.accounts.models import User
from apps.orders.models import Order
print(f'用户数量: {User.objects.count()}')
print(f'订单数量: {Order.objects.count()}')
print('验证通过!')
"

echo ""
echo "=== 迁移完成 ==="
echo "请在 .env 文件中添加以下配置:"
echo "DB_ENGINE=postgresql"
echo "DB_NAME=$DB_NAME"
echo "DB_USER=$DB_USER"
echo "DB_PASSWORD=$DB_PASS"
echo "DB_HOST=localhost"
echo "DB_PORT=5432"
echo ""
echo "然后重启服务: sudo systemctl restart magnesium"
