# 镁印制版下单系统 - 部署指南

> 本文档面向技术人员，描述项目的部署流程、环境配置和运维操作。

---

## 1. 项目概述

| 项目 | 说明 |
|------|------|
| 项目名称 | 镁印制版下单系统（闪电制版/制版家） |
| 线上域名 | www.zhibanhome.com |
| 服务器IP | 47.100.212.79 |
| 技术栈 | Django 4.2 + Python 3.8 + Bootstrap 5 |
| 部署方式 | 源码部署 |

---

## 2. 服务器环境要求

### 2.1 硬件配置

| 配置项 | 最低要求 | 推荐配置 |
|--------|---------|---------|
| CPU | 2核 | 4核 |
| 内存 | 4GB | 8GB |
| 硬盘 | 50GB SSD | 100GB SSD |
| 带宽 | 5Mbps | 10Mbps |

### 2.2 软件环境

| 软件 | 版本 | 说明 |
|------|------|------|
| CentOS/Alibaba Linux | 8.x | 操作系统 |
| Python | 3.8+ | 运行环境 |
| Nginx | 1.20+ | 反向代理 |
| Git | 2.x | 代码管理 |
| SQLite/PostgreSQL | - | 数据库 |

---

## 3. 首次部署流程

### 3.1 服务器准备

```bash
# 更新系统
sudo yum update -y

# 安装基础工具
sudo yum install -y git vim wget curl

# 安装Python 3.8
sudo yum install -y python38 python38-pip

# 安装Nginx
sudo yum install -y nginx
```

### 3.2 项目部署

```bash
# 1. 创建项目目录
mkdir -p /home/magnesium
cd /home/magnesium

# 2. 克隆代码（从GitHub）
git clone https://github.com/Carol0313/meiyintech-system.git magnesium_order_platform

# 3. 进入项目目录
cd magnesium_order_platform

# 4. 创建虚拟环境
python3.8 -m venv venv

# 5. 激活虚拟环境
source venv/bin/activate

# 6. 安装依赖
pip install -r requirements.txt

# 7. 数据库迁移
python manage.py migrate

# 8. 创建超级管理员
python manage.py createsuperuser

# 9. 收集静态文件
python manage.py collectstatic --noinput
```

### 3.3 配置文件设置

#### settings.py 关键配置

```python
# 关闭调试模式
DEBUG = False

# 允许访问的域名
ALLOWED_HOSTS = ['www.zhibanhome.com', 'zhibanhome.com', '47.100.212.79']

# 数据库配置（生产环境建议PostgreSQL）
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'magnesium_db',
        'USER': 'db_user',
        'PASSWORD': 'db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}

# OSS配置（阿里云对象存储）
OSS_ACCESS_KEY_ID = '你的AccessKeyID'
OSS_ACCESS_KEY_SECRET = '你的AccessKeySecret'
OSS_ENDPOINT = 'oss-cn-shanghai.aliyuncs.com'
OSS_BUCKET_NAME = 'zbhomefiles'

# 启用OSS存储
DEFAULT_FILE_STORAGE = 'utils.oss_storage.AliyunOSSMediaStorage'
```

### 3.4 Nginx配置

```nginx
# /etc/nginx/conf.d/magnesium.conf
server {
    listen 80;
    server_name www.zhibanhome.com zhibanhome.com;
    
    # 重定向到HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name www.zhibanhome.com zhibanhome.com;
    
    # SSL证书
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    # 客户端上传文件大小限制
    client_max_body_size 50M;
    
    # 静态文件
    location /static/ {
        alias /home/magnesium/magnesium_order_platform/staticfiles/;
        expires 30d;
    }
    
    # 媒体文件
    location /media/ {
        alias /home/magnesium/magnesium_order_platform/media/;
        expires 7d;
    }
    
    # 反向代理到Django
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3.5 启动服务

```bash
# 启动Nginx
sudo systemctl start nginx
sudo systemctl enable nginx

# 启动Django（使用Gunicorn）
cd /home/magnesium/magnesium_order_platform
source venv/bin/activate
gunicorn magnesium_order_platform.wsgi:application \
    --bind 127.0.0.1:8000 \
    --workers 4 \
    --timeout 120 \
    --access-logfile /var/log/gunicorn/access.log \
    --error-logfile /var/log/gunicorn/error.log
```

---

## 4. 日常更新流程

### 4.1 代码更新

```bash
# 1. 进入项目目录
cd /home/magnesium/magnesium_order_platform

# 2. 拉取最新代码
git pull origin master

# 3. 安装新依赖（如果有更新）
source venv/bin/activate
pip install -r requirements.txt

# 4. 数据库迁移（如果有模型变更）
python manage.py migrate

# 5. 收集静态文件
python manage.py collectstatic --noinput

# 6. 重启服务
pkill -f runserver
sleep 2
nohup python manage.py runserver 127.0.0.1:8000 > server.log 2>&1 &
```

### 4.2 快速更新脚本

创建 `update.sh`：

```bash
#!/bin/bash
cd /home/magnesium/magnesium_order_platform

echo "=== 开始更新 ==="

# 拉取代码
echo "[1/5] 拉取最新代码..."
git pull origin master

# 安装依赖
echo "[2/5] 安装依赖..."
source venv/bin/activate
pip install -r requirements.txt -q

# 数据库迁移
echo "[3/5] 数据库迁移..."
python manage.py migrate --noinput

# 收集静态文件
echo "[4/5] 收集静态文件..."
python manage.py collectstatic --noinput

# 重启服务
echo "[5/5] 重启服务..."
pkill -f runserver
sleep 2
nohup python manage.py runserver 127.0.0.1:8000 > server.log 2>&1 &
sleep 3

# 检查状态
if ps aux | grep runserver | grep -v grep > /dev/null; then
    echo "✅ 更新成功，服务已启动"
    ps aux | grep runserver | grep -v grep
else
    echo "❌ 服务启动失败"
    tail -n 20 server.log
fi

echo "=== 更新完成 ==="
```

赋予执行权限：
```bash
chmod +x update.sh
```

---

## 5. 环境变量配置

### 5.1 使用 .env 文件

创建 `.env` 文件：

```bash
# 数据库
DB_ENGINE=postgresql
DB_NAME=magnesium_db
DB_USER=db_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Django
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=your-secret-key-here
DJANGO_ALLOWED_HOSTS=www.zhibanhome.com,zhibanhome.com

# OSS
OSS_ACCESS_KEY_ID=your-access-key
OSS_ACCESS_KEY_SECRET=your-secret-key
OSS_INTERNAL=true

# 快递100
KUADI100_KEY=your-api-key
```

### 5.2 加载环境变量

`manage.py` 已配置自动加载 `.env` 文件。

---

## 6. 常见问题

### 6.1 GitHub连接超时

**现象**：
```
fatal: unable to access 'https://github.com/...': Empty reply from server
```

**解决**：
```bash
# 方法1：重试
git pull origin master

# 方法2：使用镜像
git pull https://ghproxy.com/https://github.com/Carol0313/meiyintech-system.git master

# 方法3：手动下载文件
curl -o utils/plate_preview_effects.py \
  https://raw.githubusercontent.com/Carol0313/meiyintech-system/master/utils/plate_preview_effects.py
```

### 6.2 依赖安装失败

**现象**：
```
ERROR: Could not find a version that satisfies the requirement...
```

**解决**：
```bash
# 更新pip
pip install --upgrade pip

# 使用阿里云镜像
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

### 6.3 静态文件404

**现象**：CSS/JS文件加载失败

**解决**：
```bash
# 重新收集静态文件
python manage.py collectstatic --noinput --clear

# 检查Nginx配置路径是否正确
ls -la /home/magnesium/magnesium_order_platform/staticfiles/
```

### 6.4 数据库迁移错误

**现象**：
```
django.db.migrations.exceptions.InconsistentMigrationHistory
```

**解决**：
```bash
# 备份数据库
cp db.sqlite3 db.sqlite3.backup.$(date +%Y%m%d)

# 删除迁移记录重新生成
find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
python manage.py makemigrations
python manage.py migrate
```

---

## 7. 备份策略

### 7.1 数据库备份

```bash
# SQLite备份
cp db.sqlite3 backups/db.sqlite3.$(date +%Y%m%d_%H%M%S)

# PostgreSQL备份
pg_dump -U db_user magnesium_db > backups/db_$(date +%Y%m%d).sql
```

### 7.2 媒体文件备份

```bash
# 同步到OSS
python manage.py sync_files_to_oss

# 或本地备份
tar czvf backups/media_$(date +%Y%m%d).tar.gz media/
```

### 7.3 自动备份脚本

创建 `backup.sh`：

```bash
#!/bin/bash
BACKUP_DIR="/home/magnesium/backups/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# 备份数据库
cp /home/magnesium/magnesium_order_platform/db.sqlite3 $BACKUP_DIR/

# 备份媒体文件
tar czvf $BACKUP_DIR/media.tar.gz /home/magnesium/magnesium_order_platform/media/

# 保留最近30天备份
find /home/magnesium/backups -type d -mtime +30 -exec rm -rf {} \;

echo "备份完成: $BACKUP_DIR"
```

添加到定时任务：
```bash
crontab -e
# 每天凌晨3点备份
0 3 * * * /home/magnesium/magnesium_order_platform/backup.sh >> /var/log/backup.log 2>&1
```

---

## 8. 监控与日志

### 8.1 查看服务状态

```bash
# 查看Django进程
ps aux | grep runserver

# 查看Nginx状态
sudo systemctl status nginx

# 查看日志
tail -f /home/magnesium/magnesium_order_platform/server.log
tail -f /var/log/nginx/error.log
```

### 8.2 性能监控

```bash
# 查看CPU/内存
top

# 查看磁盘空间
df -h

# 查看网络连接
netstat -tuln | grep 8000
```

---

## 9. 安全建议

| 项目 | 建议 |
|------|------|
| 防火墙 | 只开放80/443/22端口 |
| SSL证书 | 使用Let's Encrypt自动续期 |
| 密码强度 | 管理员密码至少12位 |
| 定期更新 | 每月更新系统补丁 |
| 日志审计 | 定期检查异常访问日志 |

---

## 10. 联系方式

| 项目 | 信息 |
|------|------|
| 服务器IP | 47.100.212.79 |
| 域名 | www.zhibanhome.com |
| GitHub仓库 | https://github.com/Carol0313/meiyintech-system |

---

> **文档版本**: 1.0  
> **更新日期**: 2026-06-09  
> **维护人员**: 技术团队
