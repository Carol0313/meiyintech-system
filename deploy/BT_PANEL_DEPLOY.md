# 宝塔面板部署指南（制版家 www.zhibanhome.com）

> 适用于已有宝塔面板 + 阿里云ECS + 域名已备案并解析到服务器IP

---

## 一、服务器环境准备

### 1. 域名解析
在阿里云域名控制台，将 `www.zhibanhome.com` 和 `zhibanhome.com` 的 A 记录指向你的服务器公网IP。

### 2. 宝塔面板安装基础环境
登录宝塔面板 → 软件商店，安装以下套件：
- **Nginx**（推荐 1.24+）
- **MySQL**（推荐 8.0 或 5.7）
- **Python项目管理器**（宝塔插件，搜索安装）

---

## 二、创建数据库

1. 宝塔面板 → **数据库** → 添加数据库
2. 填写信息：
   - 数据库名：`zhibanhome_db`
   - 用户名：`zhibanhome_user`
   - 密码：随机生成或自定义（记得保存）
   - 访问权限：**本地服务器**
3. 点击提交

---

## 三、上传项目代码

### 方式A：Git拉取（推荐）
1. 宝塔面板 → **文件** → 进入 `/www/wwwroots/`
2. 打开终端，执行：
   ```bash
   git clone https://github.com/Carol0313/meiyintech-system.git zhibanhome
   cd zhibanhome
   ```

### 方式B：本地上传
1. 本地代码打包成 zip
2. 宝塔 → **文件** → `/www/wwwroots/` → 上传并解压

---

## 四、Python项目管理器部署

1. 宝塔 → **软件商店** → **Python项目管理器** → 添加项目
2. 填写项目信息：

| 配置项 | 填写内容 |
|--------|---------|
| 项目路径 | `/www/wwwroots/zhibanhome` |
| Python版本 | 3.8 / 3.9 / 3.10（推荐3.10） |
| 框架 | `Django` |
| 启动方式 | `gunicorn` |
| 启动文件/文件夹 | `magnesium_order_platform/wsgi.py` |
| 端口 | `8000`（或其他未占用端口） |
| 是否安装模块依赖 | ✅ 勾选（自动读取 requirements.txt） |

3. 点击确定，等待依赖安装完成

---

## 五、配置环境变量

在 Python项目管理器 → 找到项目 → **配置** → **环境变量**，添加以下变量：

```bash
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=www.zhibanhome.com,zhibanhome.com
DJANGO_SECRET_KEY=你的随机密钥（50位以上字母数字混合）
CSRF_TRUSTED_ORIGINS=https://www.zhibanhome.com,https://zhibanhome.com
DB_ENGINE=mysql
DB_NAME=zhibanhome_db
DB_USER=zhibanhome_user
DB_PASSWORD=你设置的数据库密码
DB_HOST=localhost
DB_PORT=3306
```

> **生成随机密钥**：在服务器终端执行 `openssl rand -base64 50`

---

## 六、数据库迁移 + 静态文件

在 Python项目管理器 → 项目 → **终端**，依次执行：

```bash
cd /www/wwwroots/zhibanhome
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

> 创建超级用户时按提示输入用户名、邮箱、密码。

---

## 七、Nginx反向代理 + 域名绑定

1. 宝塔 → **网站** → 添加站点
   - 域名：`www.zhibanhome.com` `zhibanhome.com`
   - 根目录：默认即可（宝塔会自动创建）
   - PHP版本：纯静态

2. 站点设置 → **反向代理** → 添加反向代理
   - 代理名称：`django`
   - 目标URL：`http://127.0.0.1:8000`
   - 发送域名：`$host`
   - 点击提交

3. 站点设置 → **配置文件**，在 `server { ... }` 块内添加以下内容：

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

4. 保存并重载Nginx

---

## 八、SSL证书（HTTPS）

强烈建议开启HTTPS：
1. 宝塔 → **网站** → 站点设置 → **SSL**
2. 选择 **Let's Encrypt** 或 **阿里云SSL**
3. 勾选强制HTTPS
4. 申请并部署

> 开启HTTPS后，确保环境变量 `CSRF_TRUSTED_ORIGINS` 包含 `https://www.zhibanhome.com`

---

## 九、配置自动确认收货定时任务

宝塔 → **计划任务** → 添加任务：
- 任务类型：**Shell脚本**
- 任务名称：`自动确认收货`
- 执行周期：每天 `2:00`
- 脚本内容：
  ```bash
  cd /www/wwwroots/zhibanhome
  source venv/bin/activate
  python manage.py auto_confirm_receipt
  ```

---

## 十、常见问题

### 1. 访问出现 502 Bad Gateway
- 检查 Python项目管理器里的项目是否已启动
- 检查端口是否一致（Nginx反向代理端口 = Python项目端口）

### 2. 静态文件（CSS/图片）加载不出来
- 确认已执行 `python manage.py collectstatic --noinput`
- 确认Nginx配置中 `/static/` 的 alias 路径正确

### 3. 上传文件失败 / 文件过大
- 宝塔 → 站点设置 → **配置文件** → 确认有 `client_max_body_size 50M;`
- Python项目管理器 → 项目 → **配置** → 检查上传大小限制

### 4. MySQL连接报错
- 确认宝塔中创建了数据库，且用户名密码正确
- 确认 `DB_ENGINE=mysql` 已设置
- 如需重新迁移，先删除库再重建，或执行 `python manage.py migrate`

---

## 快速检查清单

- [ ] 域名解析到服务器IP
- [ ] 宝塔安装了 Nginx + MySQL + Python项目管理器
- [ ] 数据库已创建并记录密码
- [ ] 项目代码已上传到 `/www/wwwroots/zhibanhome`
- [ ] Python项目管理器已添加项目并启动
- [ ] 环境变量已配置（特别是 SECRET_KEY 和数据库密码）
- [ ] 已执行 `migrate` 和 `collectstatic`
- [ ] Nginx站点已添加并配置反向代理
- [ ] 静态文件路径已配置
- [ ] SSL证书已申请（可选但强烈建议）
- [ ] 自动确认收货定时任务已添加
