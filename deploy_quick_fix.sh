#!/bin/bash
# 快速修复部署脚本 - 仅重启服务
set -e

PROJECT_DIR="/home/magnesium/magnesium_order_platform"

echo "=========================================="
echo "  快速修复部署 - 仅拉取代码并重启"
echo "=========================================="
echo ""

cd "$PROJECT_DIR"

# 拉取最新代码
echo "[1/2] 拉取最新代码..."
git pull gitee master
echo "       代码更新完成"
echo ""

# 重启服务
echo "[2/2] 重启服务..."
systemctl restart magnesium
systemctl reload nginx
echo "       服务重启完成"
echo ""

echo "=========================================="
echo "  修复完成！"
echo "=========================================="
echo ""
echo "  请刷新页面测试上传功能"
echo ""
