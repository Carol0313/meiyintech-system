#!/bin/bash
# 服务器安全加固脚本
# 警告：执行前请确保已创建普通用户并配置好SSH密钥，否则可能无法登录服务器！
# 用法: bash deploy/scripts/04_security_hardening.sh

set -e

NEW_SSH_PORT="2222"
NEW_USER="deploy"
FAIL2BAN_SSH_MAXRETRY="3"
FAIL2BAN_SSH_BANTIME="3600"

echo "=== 镁印制版系统: 服务器安全加固 ==="
echo "警告：请确保当前已通过另一个终端测试了普通用户登录后再执行！"
echo ""

# 1. 创建普通用户（如果不存在）
echo "[1/8] 检查/创建普通用户 $NEW_USER..."
if ! id "$NEW_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$NEW_USER"
    echo "用户 $NEW_USER 已创建"
else
    echo "用户 $NEW_USER 已存在"
fi

# 添加到 sudoers
echo "$NEW_USER ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/$NEW_USER
chmod 440 /etc/sudoers.d/$NEW_USER

# 2. 配置 SSH 密钥登录
echo "[2/8] 配置 SSH 密钥登录..."
if [ ! -d "/home/$NEW_USER/.ssh" ]; then
    mkdir -p "/home/$NEW_USER/.ssh"
    chmod 700 "/home/$NEW_USER/.ssh"
fi

# 如果当前 root 有 authorized_keys，复制给新用户
if [ -f "/root/.ssh/authorized_keys" ]; then
    cp /root/.ssh/authorized_keys "/home/$NEW_USER/.ssh/authorized_keys"
    chmod 600 "/home/$NEW_USER/.ssh/authorized_keys"
    chown -R "$NEW_USER:$NEW_USER" "/home/$NEW_USER/.ssh"
    echo "已复制 root 的 SSH 公钥到 $NEW_USER"
else
    echo "警告：未找到 /root/.ssh/authorized_keys，请手动添加公钥到 /home/$NEW_USER/.ssh/authorized_keys"
fi

# 3. 备份 SSH 配置
echo "[3/8] 备份 SSH 配置..."
cp /etc/ssh/sshd_config "/etc/ssh/sshd_config.backup.$(date +%Y%m%d%H%M%S)"

# 4. 修改 SSH 配置
echo "[4/8] 修改 SSH 配置..."
# 使用 sed 修改关键配置，如果不存在则追加
set_ssh_config() {
    local key="$1"
    local value="$2"
    if grep -q "^#*${key}\b" /etc/ssh/sshd_config; then
        sed -i "s/^#*${key}\b.*/${key} ${value}/" /etc/ssh/sshd_config
    else
        echo "${key} ${value}" >> /etc/ssh/sshd_config
    fi
}

set_ssh_config "Port" "$NEW_SSH_PORT"
set_ssh_config "PermitRootLogin" "no"
set_ssh_config "PasswordAuthentication" "no"
set_ssh_config "PubkeyAuthentication" "yes"
set_ssh_config "MaxAuthTries" "3"
set_ssh_config "ClientAliveInterval" "300"
set_ssh_config "ClientAliveCountMax" "2"

# 5. 测试 SSH 配置
echo "[5/8] 测试 SSH 配置..."
if sshd -t; then
    echo "SSH 配置测试通过"
else
    echo "SSH 配置有误，请检查 /etc/ssh/sshd_config"
    exit 1
fi

# 6. 安装并配置 fail2ban
echo "[6/8] 安装并配置 fail2ban..."
if command -v dnf &>/dev/null; then
    dnf install -y fail2ban
elif command -v yum &>/dev/null; then
    yum install -y fail2ban
else
    echo "未找到 dnf/yum，请手动安装 fail2ban"
fi

# 配置 fail2ban
cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
backend = systemd

[sshd]
enabled = true
port = $NEW_SSH_PORT
filter = sshd
logpath = /var/log/secure
maxretry = $FAIL2BAN_SSH_MAXRETRY
bantime = $FAIL2BAN_SSH_BANTIME
EOF

systemctl enable fail2ban
systemctl start fail2ban

# 7. 配置防火墙（firewalld）
echo "[7/8] 配置防火墙..."
if systemctl is-active --quiet firewalld; then
    firewall-cmd --permanent --remove-service=ssh || true
    firewall-cmd --permanent --add-port="${NEW_SSH_PORT}/tcp"
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --reload
    echo "防火墙已配置"
elif command -v firewall-cmd &>/dev/null; then
    systemctl enable firewalld
    systemctl start firewalld
    firewall-cmd --permanent --add-port="${NEW_SSH_PORT}/tcp"
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --reload
    echo "防火墙已启用并配置"
else
    echo "未安装 firewalld，请在安全组中配置端口"
fi

# 8. 重启 SSH 服务
echo "[8/8] 重启 SSH 服务..."
systemctl restart sshd

echo ""
echo "=== 安全加固完成 ==="
echo ""
echo "重要提醒："
echo "1. SSH 端口已改为: $NEW_SSH_PORT"
echo "2. root 密码登录已禁用"
echo "3. 请使用普通用户 $NEW_USER + SSH 密钥登录"
echo "4. 登录命令: ssh -p $NEW_SSH_PORT $NEW_USER@47.100.212.79"
echo "5. 请在阿里云安全组中放行 TCP $NEW_SSH_PORT、80、443 端口"
echo "6. 当前 SSH 连接不会断开，但新连接需要使用新端口和密钥"
echo ""
echo "如果无法登录，请通过阿里云控制台 VNC 登录恢复。"
