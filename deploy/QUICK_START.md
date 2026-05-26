# 宝塔面板快速部署指南（制版家 www.zhibanhome.com）

> 环境：阿里云ECS + 宝塔面板 + PostgreSQL + Nginx

---

## 一、域名解析

阿里云域名控制台 → `www.zhibanhome.com` 和 `zhibanhome.com` 的 A 记录 → 指向服务器公网IP。

---

## 二、宝塔安装软件

软件商店安装：
- **Nginx**
- **PostgreSQL**
- **Python项目管理器**

---

## 三、创建数据库

宝塔 → 数据库 → **PostgreSQL** → 添加数据库：
- 数据库名：`zhibanhome_db`
- 用户名：`zhibanhome_user`
- 密码：随机生成（保存好）

---

## 四、添加网站 + 反向代理

1. 网站 → 添加站点
   - 域名：`www.zhibanhome.com`（再点添加域名把 `zhibanhome.com` 也加上）
   - PHP版本：**纯静态**

2. 站点设置 → **反向代理** → 添加反向代理
   - 代理名称：`django`
   - 目标URL：`http://127.0.0.1:8000`
   - 发送域名：`$host`

---

## 五、Python项目管理器部署

1. Python项目管理器 → 添加项目

| 配置项 | 内容 |
|--------|------|
| 项目路径 | `/www/wwwroots/zhibanhome` |
| Python版本 | 3.10 |
| 框架 | Django |
| 启动方式 | gunicorn |
| 启动文件 | `magnesium_order_platform/wsgi.py` |
| 端口 | 8000 |
| 安装依赖 | ✅ 勾选 |

2. 先别点确定，在**项目路径**那里，项目还不存在。去第6步拉代码。

---

## 六、Git拉取代码

宝塔 → 文件 → `/www/wwwroots/` → 终端：

```bash
git clone https://github.com/Carol0313/meiyintech-system.git zhibanhome
```

拉完再回到第5步，点确定添加项目。

---

## 七、配置环境变量

Python项目管理器 → `zhibanhome` → **配置** → **环境变量**：

```
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=www.zhibanhome.com,zhibanhome.com
DJANGO_SECRET_KEY=这里填openssl rand -base64 50生成的密钥
CSRF_TRUSTED_ORIGINS=https://www.zhibanhome.com,https://zhibanhome.com
DB_ENGINE=postgresql
DB_NAME=zhibanhome_db
DB_USER=zhibanhome_user
DB_PASSWORD=你的数据库密码
DB_HOST=localhost
DB_PORT=5432
```

保存，**重启项目**。

---

## 八、初始化数据库 + 静态文件 + 超管

Python项目管理器 → `zhibanhome` → **终端**：

```bash
cd /www/wwwroots/zhibanhome
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

---

## 九、Nginx配置静态文件

站点设置 → **配置文件**，在 `server {}` 内添加：

```nginx
    client_max_body_size 50M;

    location /static/ {
        alias /www/wwwroots/zhibanhome/staticfiles/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias /www/wwwroots/zhibanhome/media/;
        expires 7d;
        add_header Cache-Control "public";
    }
```

保存，重载Nginx。

---

## 十、SSL证书（HTTPS）

站点设置 → **SSL** → Let's Encrypt → 申请 `www.zhibanhome.com` + `zhibanhome.com` → 开启**强制HTTPS**。

---

## 十一、Git自动部署（以后更新代码自动生效）

宝塔 → 文件 → `/www/wwwroots/zhibanhome` → **Git**

1. 绑定仓库：`https://github.com/Carol0313/meiyintech-system.git`，分支 `master`
2. 点**拉取**
3. **部署后脚本**：

```bash
#!/bin/bash
cd /www/wwwroots/zhibanhome
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
bt python restart zhibanhome
```

以后本地 push 到 GitHub 后，来宝塔 Git 页面点**拉取**即可自动部署。

---

## 十二、自动确认收货定时任务

计划任务 → 添加任务：
- 类型：Shell脚本
- 名称：自动确认收货
- 周期：每天 2:00
- 脚本：

```bash
cd /www/wwwroots/zhibanhome
source venv/bin/activate
python manage.py auto_confirm_receipt
```

---

## 检查清单

- [ ] 域名A记录解析到服务器IP
- [ ] 宝塔安装了 Nginx + PostgreSQL + Python项目管理器
- [ ] PostgreSQL数据库已创建并保存密码
- [ ] 网站已添加，反向代理到127.0.0.1:8000
- [ ] 代码已git clone到 /www/wwwroots/zhibanhome
- [ ] Python项目管理器已添加项目并启动
- [ ] 环境变量已配置（SECRET_KEY、DB_PASSWORD）
- [ ] 已执行 migrate + collectstatic + createsuperuser
- [ ] Nginx已配置static/media路径并重载
- [ ] SSL证书已申请并强制HTTPS
- [ ] Git自动部署脚本已配置
- [ ] 定时任务已添加
