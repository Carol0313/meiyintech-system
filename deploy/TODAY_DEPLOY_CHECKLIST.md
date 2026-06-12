# 镁印制版系统 - 今日生产部署清单（2026-06-13）

> 目标：完成 SQLite → PostgreSQL 迁移 + Gunicorn + systemd + Nginx 生产部署
> 预计耗时：2-4 小时（取决于数据量）
> 操作前请确保：已 SSH 登录服务器 47.100.212.79，当前为 root 用户

---

## 一、执行前检查

```bash
# 1. 确认服务器配置（应显示 4 核、8G 内存）
cat /proc/cpuinfo | grep "processor" | wc -l
free -h

# 2. 确认当前目录为项目目录
cd /home/magnesium/magnesium_order_platform
pwd

# 3. 确认虚拟环境正常
source venv/bin/activate
python --version

# 4. 确认当前数据库为 SQLite
python manage.py shell -c "from django.conf import settings; print('当前数据库引擎:', settings.DATABASES['default']['ENGINE'])"
```

---

## 二、设置数据库密码（可选）

脚本默认使用以下配置，如需自定义请提前设置环境变量：

```bash
export DB_NAME=magnesium_db
export DB_USER=magnesium_user
export DB_PASSWORD=你的安全密码
```

> 建议设置一个强密码，并记录下来。迁移完成后需要写入 `.env` 文件。

---

## 三、步骤 1：安装并配置 PostgreSQL

```bash
cd /home/magnesium/magnesium_order_platform
bash deploy/scripts/01_setup_postgresql.sh
```

执行成功后会输出：
- 数据库名：`magnesium_db`
- 用户名：`magnesium_user`
- 密码

如果系统不是 CentOS 8 / Alibaba Cloud Linux 3，可能需要手动安装 PostgreSQL，然后修改 `pg_hba.conf` 为 md5 认证。

---

## 四、步骤 2：SQLite → PostgreSQL 数据迁移

```bash
cd /home/magnesium/magnesium_order_platform
bash deploy/scripts/02_migrate_sqlite_to_postgres.sh
```

脚本会：
1. 备份 `db.sqlite3`
2. 导出业务数据为 JSON（排除 contenttypes/permissions）
3. 在 PostgreSQL 中创建表结构
4. 导入数据
5. 验证用户、订单、产品规格数量

**注意**：如果迁移过程中报错，请先不要修改 `.env`，服务仍使用 SQLite 运行。排查问题后重新执行迁移脚本即可。

---

## 五、步骤 3：更新 .env 数据库配置

迁移成功后，编辑 `.env` 文件：

```bash
vim /home/magnesium/magnesium_order_platform/.env
```

添加或修改以下配置：

```ini
DB_ENGINE=postgresql
DB_NAME=magnesium_db
DB_USER=magnesium_user
DB_PASSWORD=你的实际密码
DB_HOST=localhost
DB_PORT=5432
```

保存后测试数据库连接：

```bash
cd /home/magnesium/magnesium_order_platform
source venv/bin/activate
python manage.py shell -c "from django.conf import settings; print('当前数据库引擎:', settings.DATABASES['default']['ENGINE']); print('数据库名:', settings.DATABASES['default']['NAME'])"
```

---

## 六、步骤 4：部署 Gunicorn + systemd + Nginx

```bash
cd /home/magnesium/magnesium_order_platform
bash deploy/scripts/03_deploy_gunicorn_systemd.sh
```

脚本会：
1. 安装/确认 Gunicorn
2. 收集静态文件
3. 创建日志目录
4. 配置 systemd 服务
5. 停止旧 runserver
6. 启动 Gunicorn
7. 配置 Nginx
8. 测试并重启 Nginx

---

## 七、部署后验证

### 7.1 检查服务状态

```bash
# Gunicorn 服务状态
sudo systemctl status magnesium --no-pager -l

# Nginx 服务状态
sudo systemctl status nginx --no-pager -l

# 端口监听
ss -tlnp | grep -E "8000|80|443"
```

### 7.2 检查数据库

```bash
cd /home/magnesium/magnesium_order_platform
source venv/bin/activate
python manage.py shell -c "
from django.contrib.auth import get_user_model
from apps.orders.models import Order
User = get_user_model()
print('用户数量:', User.objects.count())
print('订单数量:', Order.objects.count())
print('数据库引擎:', __import__('django.conf').conf.settings.DATABASES['default']['ENGINE'])
"
```

### 7.3 访问测试

```bash
# 本地测试 Gunicorn
curl -s -o /dev/null -w "Gunicorn HTTP状态: %{http_code}\n" http://127.0.0.1:8000

# Nginx 测试
curl -s -o /dev/null -w "Nginx HTTP状态: %{http_code}\n" http://www.zhibanhome.com
```

---

## 八、回退方案

如果部署后出现问题，可以立即回退到 SQLite + runserver：

```bash
cd /home/magnesium/magnesium_order_platform

# 1. 停止 Gunicorn
sudo systemctl stop magnesium

# 2. 修改 .env，改回 SQLite
vim .env
# 注释掉或删除 DB_ENGINE=postgresql 相关配置
# 即：DB_ENGINE=sqlite3 或不设置（默认就是 sqlite3）

# 3. 启动 runserver
source venv/bin/activate
nohup python manage.py runserver 127.0.0.1:8000 > server.log 2>&1 &

# 4. 确认运行
ps aux | grep runserver
```

---

## 九、常见问题

### Q1: PostgreSQL 服务启动失败

```bash
# 查看日志
sudo journalctl -u postgresql-14 -n 50

# 检查配置
sudo cat /var/lib/pgsql/14/data/postgresql.conf | grep listen_addresses
sudo cat /var/lib/pgsql/14/data/pg_hba.conf
```

### Q2: 迁移时报 `loaddata` 错误

可能是外键约束问题。尝试：

```bash
# 重新执行迁移（脚本会自动删除并重建数据库）
bash deploy/scripts/02_migrate_sqlite_to_postgres.sh
```

### Q3: Gunicorn 启动失败

```bash
# 查看日志
sudo tail -n 50 /var/log/gunicorn/magnesium_error.log

# 检查 .env 是否配置正确
sudo systemctl status magnesium -l
```

### Q4: Nginx 502 错误

```bash
# 检查 Gunicorn 是否在运行
sudo systemctl status magnesium

# 检查 Nginx 错误日志
sudo tail -n 50 /var/log/nginx/magnesium_error.log
```

---

## 十、部署成功后收尾

1. **删除测试数据**：如果 PostgreSQL 中有测试数据，执行清理脚本
2. **修改服务器安全策略**：修改 SSH 端口、禁用密码登录、安装 fail2ban
3. **配置监控**：设置服务状态监控告警
4. **更新项目进度表**：标记 PostgreSQL 迁移和 Gunicorn 部署为已完成
5. **通知团队**：部署完成，技术支持可介入验收
