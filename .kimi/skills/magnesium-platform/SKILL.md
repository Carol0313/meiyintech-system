---
name: magnesium-platform
description: |
  镁印制版下单系统（闪电制版/制版家）项目专属Skill。
  当用户在此项目中工作时自动触发，提供项目上下文、服务器环境、部署流程等关键信息。
  适用于：代码开发、服务器部署、功能迭代、问题排查等任何与该项目相关的任务。
---

# 镁印制版下单系统 - 项目上下文

## 项目基本信息

- **项目名称**: 镁印制版下单系统（闪电制版 / 制版家）
- **域名**: www.zhibanhome.com
- **服务器IP**: 47.100.212.79
- **技术栈**: Django 4.2, Python 3.8, Bootstrap 5.3, SQLite(开发)/PostgreSQL(生产), 阿里云OSS
- **代码仓库**: https://github.com/Carol0313/meiyintech-system
- **部署状态**: 测试阶段，使用 runserver + SQLite

## 服务器环境

```bash
# 项目路径
cd /home/magnesium/magnesium_order_platform

# 虚拟环境
source venv/bin/activate

# 启动服务
nohup python manage.py runserver 127.0.0.1:8000 > server.log 2>&1 &

# Nginx配置
/etc/nginx/conf.d/*.conf
# 静态文件路径
/home/magnesium/magnesium_order_platform/staticfiles/
```

## 关键环境变量

```bash
# .env文件路径
/home/magnesium/magnesium_order_platform/.env

# 关键配置
OSS_INTERNAL=true  # ECS内网访问OSS
DB_ENGINE=sqlite3  # 当前使用SQLite
```

## 已完成功能（13项）

| 功能 | 完成时间 |
|------|---------|
| 用户认证体系（登录/注册/权限） | 2026-05 |
| 客户下单流程（单页/分步） | 2026-05 |
| PDF红框智能识别 | 2026-05 |
| 订单状态流转与追踪 | 2026-05 |
| 拼版工具（单订单/跨订单） | 2026-05 |
| 生产看板与工厂管理 | 2026-05 |
| 对账单与信用额度 | 2026-05 |
| 阿里云OSS文件存储 | 2026-06-05 |
| 商户端订单详情页优化 | 2026-06-05 |
| 客户投诉功能 | 2026-06-05 |
| SSL证书申请 | 2026-06-05 |
| 规格组特殊要求备注 | 2026-06-05 |
| 规格组缩放比例设置 | 2026-06-05 |

## 进行中功能（2项）

| 功能 | 预计完成 | 备注 |
|------|---------|------|
| 红框尺寸修改功能 | 6月6日 | **商户后台可修改红框尺寸** |
| 商户端投诉管理 | 6月6日 | 查看投诉列表、处理投诉 |

## 待开始任务

| 任务 | 时间 |
|------|------|
| 域名备案 | 预计6月8日 |
| PostgreSQL数据库迁移 | 6月10日-11日 |
| Gunicorn+Nginx生产部署 | 6月12日-13日 |

## 最近数据库迁移

```
orders.0023_add_item_special_requests  - OrderItem新增special_requests字段
orders.0024_add_scale_ratio            - OrderItem新增scale_ratio字段
```

## 已知问题

1. **PostgreSQL已安装但认证配置有问题**（pg_hba.conf需要改为md5认证），当前回退到SQLite
2. **Nginx systemctl重启会失败**（80端口被占用），需要用 `kill -9` 杀掉旧进程后用 `nginx` 命令启动
3. **Django runserver绑定127.0.0.1:8000**，通过Nginx反向代理访问

## 快速恢复命令

```bash
# 1. 进入项目目录
cd /home/magnesium/magnesium_order_platform

# 2. 激活虚拟环境
source venv/bin/activate

# 3. 拉取最新代码
git pull origin master

# 4. 执行迁移
python manage.py migrate

# 5. 收集静态文件
python manage.py collectstatic --noinput

# 6. 重启Nginx（如果失败用kill方式）
systemctl restart nginx
# 或
kill -9 $(pgrep nginx)
nginx

# 7. 重启Django服务
pkill -9 -f runserver
sleep 2
nohup python manage.py runserver 127.0.0.1:8000 > server.log 2>&1 &

# 8. 确认服务状态
ps aux | grep runserver
ps aux | grep nginx
```

## 项目文件

| 文件 | 说明 |
|------|------|
| `平台部署时间进度表_详细版_6月5日-30日.xlsx` | 最新项目进度表 |
| `PROJECT_STATUS.md` | 项目状态记录 |
| `业务流程文档_v2.xlsx` | 业务流程 |
| `功能说明文档_v2.xlsx` | 功能说明 |
| `系统规格说明书_v2.xlsx` | 系统规格 |

## 工作规范

1. **代码修改后必须**: 本地测试 → `python manage.py check` → Git提交 → Git推送 → 服务器更新
2. **服务器更新流程**: `git pull` → `python manage.py migrate` → 重启服务
3. **数据库变更**: 必须创建迁移文件并应用
4. **静态文件**: 修改后执行 `python manage.py collectstatic --noinput`
5. **Nginx重启**: 优先用 `systemctl restart nginx`，失败时用 `kill -9` + `nginx`
