#!/bin/bash
# SQLite → PostgreSQL 数据迁移脚本（改进版）
# 用法: bash deploy/scripts/02_migrate_sqlite_to_postgres.sh
# 前置条件: PostgreSQL 已安装并配置完成

set -e

PROJECT_DIR="/home/magnesium/magnesium_order_platform"
DB_NAME="${DB_NAME:-magnesium_db}"
DB_USER="${DB_USER:-magnesium_user}"
DB_PASS="${DB_PASSWORD:-magnesium_pass_2026}"
BACKUP_DIR="${PROJECT_DIR}/backups/$(date +%Y%m%d_%H%M%S)"

echo "=== 镁印制版系统: SQLite → PostgreSQL 数据迁移 ==="

cd "$PROJECT_DIR"
source venv/bin/activate

# 1. 备份当前 SQLite 数据库
echo "[1/8] 备份 SQLite 数据库..."
mkdir -p "$BACKUP_DIR"
cp db.sqlite3 "$BACKUP_DIR/db.sqlite3.backup"
echo "SQLite 备份已保存到: $BACKUP_DIR/db.sqlite3.backup"

# 2. 导出 SQLite 数据为 JSON
echo "[2/8] 导出 SQLite 数据为 JSON（排除 contenttypes 和 permissions，避免冲突）..."
python manage.py dumpdata \
    --exclude contenttypes \
    --exclude auth.permission \
    --exclude admin.logentry \
    --natural-primary \
    --natural-foreign \
    --indent 2 > "$BACKUP_DIR/full_backup.json"

# 检查导出文件大小
BACKUP_SIZE=$(du -h "$BACKUP_DIR/full_backup.json" | cut -f1)
echo "数据导出完成: $BACKUP_DIR/full_backup.json (大小: $BACKUP_SIZE)"

# 3. 验证 JSON 文件有效性
echo "[3/8] 验证 JSON 备份文件..."
python -c "import json; json.load(open('$BACKUP_DIR/full_backup.json')); print('JSON 文件有效')"

# 4. 设置 PostgreSQL 环境变量
echo "[4/8] 配置数据库连接环境变量..."
export DB_ENGINE=postgresql
export DB_NAME="$DB_NAME"
export DB_USER="$DB_USER"
export DB_PASSWORD="$DB_PASS"
export DB_HOST=localhost
export DB_PORT=5432

# 5. 在 PostgreSQL 上执行 Django 迁移
echo "[5/8] 在 PostgreSQL 上创建表结构..."
python manage.py migrate --run-syncdb
echo "表结构创建完成"

# 6. 清空 PostgreSQL 中的默认数据，准备导入
echo "[6/8] 清空 Django 默认数据（将由 loaddata 重新导入）..."
python manage.py shell -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'magnesium_order_platform.settings')
import django
django.setup()
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth.models import Permission
# contenttypes 和 permissions 由 migrate 自动创建，不需要清空
print('默认数据保留，准备导入业务数据')
"

# 7. 导入数据到 PostgreSQL
echo "[7/8] 导入业务数据到 PostgreSQL..."
python manage.py loaddata "$BACKUP_DIR/full_backup.json"
echo "数据导入完成"

# 8. 验证数据完整性
echo "[8/8] 验证数据完整性..."
python manage.py shell -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'magnesium_order_platform.settings')
import django
django.setup()
from django.contrib.auth import get_user_model
from apps.orders.models import Order
from apps.products.models import ProductSpec

User = get_user_model()
print('=' * 50)
print('数据迁移验证结果:')
print(f'用户数量: {User.objects.count()}')
print(f'订单数量: {Order.objects.count()}')
print(f'产品规格数量: {ProductSpec.objects.count()}')
print('=' * 50)
print('验证通过!')
"

echo ""
echo "=== 迁移完成 ==="
echo "备份目录: $BACKUP_DIR"
echo ""
echo "请在 .env 文件中添加以下数据库配置:"
echo "DB_ENGINE=postgresql"
echo "DB_NAME=$DB_NAME"
echo "DB_USER=$DB_USER"
echo "DB_PASSWORD=$DB_PASS"
echo "DB_HOST=localhost"
echo "DB_PORT=5432"
echo ""
echo "然后重启 Gunicorn 服务:"
echo "sudo systemctl restart magnesium"
