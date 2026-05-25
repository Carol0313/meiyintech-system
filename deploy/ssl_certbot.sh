#!/bin/bash
# ============================================================
# SSL证书申请脚本（使用 Certbot + Let's Encrypt）
# 前置条件：域名已解析到服务器IP，Nginx已配置好80端口
# 使用方法：sudo bash deploy/ssl_certbot.sh your-domain.com
# ============================================================

DOMAIN=${1:-"your-domain.com"}

echo "=========================================="
echo "  SSL证书申请 - Let's Encrypt"
echo "  域名：$DOMAIN"
echo "=========================================="
echo ""

# 安装 certbot
apt-get update
apt-get install -y certbot python3-certbot-nginx

# 申请证书
certbot --nginx -d "$DOMAIN" --agree-tos --non-interactive --email admin@$DOMAIN

# 自动续期测试
echo ""
echo "测试自动续期..."
certbot renew --dry-run

echo ""
echo "=========================================="
echo "  SSL配置完成！"
echo "  https://$DOMAIN"
echo "=========================================="
echo ""
echo "  Certbot 会自动添加续期定时任务"
echo "  手动续期：sudo certbot renew"
