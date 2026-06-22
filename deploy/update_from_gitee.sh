#!/bin/bash
# ============================================================
# 镁印制版下单系统 - 服务器更新脚本（从 Gitee 拉取）
# 用法：
#   1. SSH登录服务器
#   2. cd /home/magnesium/magnesium_order_platform
#   3. chmod +x deploy/update_from_gitee.sh
#   4. sudo bash deploy/update_from_gitee.sh
# ============================================================

set -e

PROJECT_DIR="/home/magnesium/magnesium_order_platform"
VENV_DIR="$PROJECT_DIR/venv"

echo "=========================================="
echo "  镁印制版系统 - 服务器更新 (Gitee)"
echo "=========================================="
echo ""

cd "$PROJECT_DIR"

# -------------------- 步骤1：拉取最新代码 --------------------
echo "[1/5] 拉取最新代码（Gitee）..."
git pull gitee master
echo "       代码更新完成"
echo ""

# -------------------- 步骤2：激活虚拟环境并安装依赖 --------------------
echo "[2/5] 安装/更新依赖..."
source "$VENV_DIR/bin/activate"
pip install -r requirements.txt
echo "       依赖更新完成"
echo ""

# -------------------- 步骤3：数据库迁移 --------------------
echo "[3/5] 执行数据库迁移..."
export $(cat .env | xargs)
python manage.py migrate
echo "       数据库迁移完成"
echo ""

# -------------------- 步骤4：收集静态文件 --------------------
echo "[4/5] 收集静态文件..."
python manage.py collectstatic --noinput
echo "       静态文件收集完成"
echo ""

# -------------------- 步骤5：重启服务 --------------------
echo "[5/5] 重启服务..."
systemctl restart magnesium
systemctl reload nginx
echo "       服务重启完成"
echo ""

echo "=========================================="
echo "  更新完成！"
echo "=========================================="
echo ""
echo "  访问地址：https://www.zhibanhome.com"
echo ""
echo "  常用命令："
echo "    查看状态：sudo systemctl status magnesium"
echo "    查看日志：sudo tail -f /var/log/gunicorn/magnesium_error.log"
echo ""
