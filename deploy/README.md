# 镁印制版下单系统 - 阿里云部署指南

> 本文档手把手教你把系统部署到阿里云ECS服务器。

---

## 📋 前置准备

### 1. 购买阿里云ECS服务器

**推荐配置：**
- **实例规格**：2核4G 或以上（入门推荐 `ecs.t6-c1m2.large`）
- **操作系统**：Ubuntu 22.04 LTS（64位）
- **带宽**：3Mbps 或以上
- **存储**：系统盘 40GB ESSD + 数据盘 100GB（存放上传的PDF/图片）
- **地域**：选择离你用户最近的地域（如华东1杭州）

**安全组规则（必须开放）：**
| 端口 | 用途 | 授权对象 |
|------|------|---------|
| 22 | SSH远程连接 | 你的IP |
| 80 | HTTP | 0.0.0.0/0 |
| 443 | HTTPS | 0.0.0.0/0 |

### 2. 准备域名（可选但强烈建议）

- 在阿里云购买域名（如 `yourdomain.com`）
- 添加A记录解析到ECS公网IP
- 等待DNS生效（通常10分钟内）

### 3. 准备代码

确保代码已提交到Git仓库，或打包成zip文件。

---

## 🚀 部署步骤

### 第一步：连接服务器

```bash
# Windows 用户：使用 PowerShell 或 Git Bash
# Mac/Linux 用户：使用终端

ssh root@你的服务器公网IP

# 示例：
# ssh root@123.45.67.89
```

首次连接会提示确认指纹，输入 `yes`。

---

### 第二步：上传代码到服务器

**方法一：使用 Git（推荐）**

```bash
# 在服务器上执行
apt-get update && apt-get install -y git
mkdir -p /home/magnesium
cd /home/magnesium
git clone 你的Git仓库地址 magnesium_order_platform
cd magnesium_order_platform
```

**方法二：使用 SCP（本地执行）**

```bash
# 在本地项目根目录执行
scp -r . root@你的服务器IP:/home/magnesium/magnesium_order_platform/
```

**方法三：使用 FTP 工具**
- 推荐：FileZilla、WinSCP
- 连接服务器后，将本地代码上传到 `/home/magnesium/magnesium_order_platform/`

---

### 第三步：运行一键部署脚本

```bash
cd /home/magnesium/magnesium_order_platform
chmod +x deploy/deploy.sh
sudo bash deploy/deploy.sh
```

脚本会自动完成以下操作：
1. ✅ 更新系统软件包
2. ✅ 安装 Python3、Nginx、PostgreSQL
3. ✅ 创建数据库和用户（自动生成随机密码）
4. ✅ 创建 Python 虚拟环境并安装依赖
5. ✅ 生成 `.env` 环境变量文件
6. ✅ 执行 Django 数据库迁移
7. ✅ 收集静态文件
8. ✅ 配置 Systemd 服务
9. ✅ 配置 Nginx 反向代理

**部署完成后，访问 `http://你的服务器IP` 即可看到系统。**

---

### 第四步：创建超级管理员

```bash
cd /home/magnesium/magnesium_order_platform
source venv/bin/activate
export $(cat .env | xargs)
python manage.py createsuperuser
```

按提示输入用户名（手机号）、邮箱、密码。

> 超级管理员可通过 `http://你的服务器IP/admin/` 访问 Django Admin 后台。

---

### 第五步：配置域名和SSL（强烈建议）

#### 5.1 修改 Nginx 配置

```bash
# 编辑配置文件
vim /etc/nginx/sites-available/magnesium
```

将 `server_name` 改为你的域名：
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    ...
}
```

重载Nginx：
```bash
nginx -t
systemctl reload nginx
```

#### 5.2 申请免费SSL证书

```bash
cd /home/magnesium/magnesium_order_platform
chmod +x deploy/ssl_certbot.sh
sudo bash deploy/ssl_certbot.sh yourdomain.com
```

Certbot 会自动：
- 安装证书
- 修改Nginx配置支持HTTPS
- 设置自动续期

**访问 `https://yourdomain.com` 即可。**

---

### 第六步：配置外部服务

#### 6.1 配置快递100（物流查询）

编辑 `.env` 文件：
```bash
vim /home/magnesium/magnesium_order_platform/.env
```

添加：
```bash
KUAIDI100_KEY=你的快递100授权Key
KUAIDI100_CUSTOMER=你的快递100 Customer ID
```

重启服务生效：
```bash
systemctl restart magnesium
```

#### 6.2 配置阿里云OSS（可选，强烈建议）

1. 登录 [阿里云OSS控制台](https://oss.console.aliyun.com/)
2. 创建 Bucket（选择"标准存储" + "公共读"）
3. 在 RAM 中创建 AccessKey，获取 ID 和 Secret
4. 编辑 `.env` 文件，添加：

```bash
OSS_ACCESS_KEY_ID=你的AccessKey ID
OSS_ACCESS_KEY_SECRET=你的AccessKey Secret
OSS_BUCKET_NAME=你的Bucket名称
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com  # 根据你的地域修改
```

5. 编辑 `settings.py`，取消注释：
```python
DEFAULT_FILE_STORAGE = 'utils.oss_storage.AliyunOSSMediaStorage'
```

6. 重启服务

---

## 🔧 日常运维命令

```bash
# 查看服务状态
systemctl status magnesium

# 重启服务
systemctl restart magnesium

# 查看Gunicorn错误日志
tail -f /var/log/gunicorn/magnesium_error.log

# 查看访问日志
tail -f /var/log/gunicorn/magnesium_access.log

# 查看Nginx日志
tail -f /var/log/nginx/magnesium_error.log

# 进入虚拟环境
cd /home/magnesium/magnesium_order_platform
source venv/bin/activate

# 手动执行Django命令
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py shell

# 备份数据库
pg_dump -U magnesium_user magnesium_order_db > backup_$(date +%Y%m%d).sql

# 恢复数据库
psql -U magnesium_user magnesium_order_db < backup_20240101.sql

# 重启Nginx
systemctl reload nginx

# 查看服务器资源使用
top
free -h
df -h
```

---

## ⚠️ 生产环境安全检查清单

- [ ] `DEBUG = False`
- [ ] `SECRET_KEY` 已更换为随机强密码
- [ ] `ALLOWED_HOSTS` 已配置为具体域名
- [ ] PostgreSQL 数据库密码为强密码
- [ ] 已配置SSL证书（HTTPS）
- [ ] 已配置阿里云OSS（避免本地磁盘满）
- [ ] 已配置快递100 API Key
- [ ] 防火墙只开放 22/80/443 端口
- [ ] 已设置数据库自动备份（建议每天）
- [ ] 已配置日志轮转（避免日志占满磁盘）

---

## 🆘 常见问题

### Q1: 访问页面显示 502 Bad Gateway

**原因**：Gunicorn 没有启动或配置错误

```bash
# 检查服务状态
systemctl status magnesium

# 查看错误日志
tail -n 50 /var/log/gunicorn/magnesium_error.log

# 手动启动测试
cd /home/magnesium/magnesium_order_platform
source venv/bin/activate
export $(cat .env | xargs)
gunicorn -c deploy/gunicorn.conf.py magnesium_order_platform.wsgi:application
```

### Q2: 静态文件（CSS/JS）加载不出来

```bash
# 重新收集静态文件
cd /home/magnesium/magnesium_order_platform
source venv/bin/activate
export $(cat .env | xargs)
python manage.py collectstatic --noinput

# 检查Nginx配置中的静态文件路径是否正确
ls -la /home/magnesium/magnesium_order_platform/staticfiles/
```

### Q3: 上传文件失败（文件太大）

**原因**：Nginx 和 Django 的上传大小限制不一致

已在 Nginx 配置中设置 `client_max_body_size 50M;`，与 Django 的 `DATA_UPLOAD_MAX_MEMORY_SIZE` 和 `FILE_UPLOAD_MAX_MEMORY_SIZE` 一致。如果还需要更大，同时修改三个地方。

### Q4: 数据库连接失败

```bash
# 检查PostgreSQL是否运行
systemctl status postgresql

# 检查数据库用户是否存在
su - postgres -c "psql -c \"\du\""

# 检查密码是否正确
su - postgres -c "psql -U magnesium_user -d magnesium_order_db -c \"SELECT 1;\""
```

### Q5: 如何更新代码？

```bash
cd /home/magnesium/magnesium_order_platform

# 如果是Git仓库
git pull

# 如果是手动上传，重新上传后执行：
source venv/bin/activate
export $(cat .env | xargs)
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart magnesium
```

---

## 📞 部署完成后验证

访问以下地址进行验证：

| 地址 | 预期结果 |
|------|---------|
| `http://你的IP/` | 跳转登录页 |
| `http://你的IP/admin/` | Django Admin 后台 |
| `http://你的IP/customer/` | 客户平台首页（需登录） |
| `http://你的IP/merchant/` | 商户平台首页（需登录） |
| `http://你的IP/platform/` | 总平台首页（需登录） |

---

> 如有问题，先查看日志：`/var/log/gunicorn/magnesium_error.log`
