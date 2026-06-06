# 镁印制版下单系统 - 项目状态记录

> 最后更新：2026-06-06 22:00
> 此文件用于快速恢复项目上下文，每次对话开始时请将此文件内容发送给AI

---

## 一、项目基本信息

| 项目 | 内容 |
|------|------|
| 项目名称 | 镁印制版下单系统（闪电制版 / 制版家） |
| 域名 | www.zhibanhome.com（备案中） |
| 服务器IP | 47.100.212.79 |
| 技术栈 | Django 4.2, Python 3.8, Bootstrap 5.3, SQLite(开发)/PostgreSQL(生产) |
| 代码仓库 | https://github.com/Carol0313/meiyintech-system |
| 部署状态 | 测试阶段，使用 runserver + SQLite + Nginx反向代理 |

---

## 二、服务器环境

```bash
# 项目路径
cd /home/magnesium/magnesium_order_platform

# 虚拟环境
source venv/bin/activate

# 启动服务
nohup python manage.py runserver 127.0.0.1:8000 > server.log 2>&1 &

# Nginx配置
/etc/nginx/conf.d/magnesium.conf
# 静态文件路径
/home/magnesium/magnesium_order_platform/staticfiles/
```

---

## 三、已完成功能清单（22项）

| 功能 | 完成时间 | 备注 |
|------|---------|------|
| 用户认证体系（登录/注册/权限） | 2026-05 | 手机号登录，四层角色权限 |
| 客户下单流程（单页/分步） | 2026-05 | 支持快速下单和分步下单 |
| PDF红框智能识别 | 2026-05 | 自动检测内容框尺寸 |
| 订单状态流转与追踪 | 2026-05 | 6步进度条可视化 |
| 拼版工具（单订单/跨订单） | 2026-05 | 4种算法，版类效果预览 |
| 生产看板与工厂管理 | 2026-05 | 工厂状态、设备监控 |
| 对账单与信用额度 | 2026-05 | 月度对账、额度管理 |
| 阿里云OSS文件存储 | 2026-06-05 | 内网Endpoint配置完成 |
| 商户端订单详情页优化 | 2026-06-05 | 移除操作面板，丰富内容 |
| 客户投诉功能 | 2026-06-05 | 客户提交投诉，支持描述+图片 |
| SSL证书申请 | 2026-06-05 | Certbot证书已申请 |
| 规格组特殊要求备注 | 2026-06-05 | 每个规格组独立备注 |
| 规格组缩放比例设置 | 2026-06-05 | 支持99.75%缩放补偿金属膨胀 |
| **UI全面改版** | **2026-06-06** | 白色侧边栏+Font Awesome图标+统计卡片新布局 |
| **产品分类重新调整** | **2026-06-06** | 腐蚀版4种+雕刻版5种+树脂版+菲林 |
| **红框尺寸修改功能** | **2026-06-06** | 商户后台可修改红框尺寸，支持添加/删除框、修改长宽高、重新计算订单金额 |
| **Nginx反向代理配置** | **2026-06-06** | `/etc/nginx/conf.d/magnesium.conf` 已配置 |
| **商户端投诉管理** | **2026-06-06** | 列表页+详情处理页完整实现 |
| **PDF预览图生成** | **2026-06-06** | OrderItem新增preview_image字段，订单详情页显示预览图 |
| **待拼版页面改版** | **2026-06-06** | 卡片式展示（预览图+完整信息），底部固定操作栏，支持分组筛选 |
| **手动上传拼版文件** | **2026-06-06** | 拼版工作台支持跳过自动拼版，直接上传拼版PDF |
| **生产看板精简改版** | **2026-06-06** | 删除KPI统计和底部统计模块，只保留三列看板+可折叠抽屉 |
| **SLA时效追踪系统** | **2026-06-06** | 客服30分钟处理+工厂30分钟下载时效追踪，订单列表/详情页/生产看板显示 |
| **商户端数据分析中心** | **2026-06-06** | 8个KPI卡片+6个ECharts图表（趋势/产品/材质/客户/工厂/状态）+SLA统计面板 |

---

## 四、进行中功能（0项）

暂无

---

## 五、待开始任务（2项）

| 任务 | 时间 | 备注 |
|------|------|------|
| PostgreSQL数据库迁移 | 6月10日-11日 | SQLite数据迁移 |
| Gunicorn+Nginx生产部署 | 6月12日-13日 | systemd服务配置 |

---

## 六、等待审核（1项）

| 事项 | 预计时间 | 状态 |
|------|---------|------|
| 域名备案 | 6月8日 | 审核中 |

---

## 七、最近数据库迁移

```
orders.0023_add_item_special_requests  - OrderItem新增special_requests字段
orders.0024_add_scale_ratio            - OrderItem新增scale_ratio字段
orders.0025_alter_orderitem_product_name  - 产品分类名称调整（第一轮）
orders.0026_alter_orderitem_product_name  - 产品分类名称调整（第二轮，去掉空格）
products.0007_alter_productspec_product_name  - ProductSpec产品分类名称调整（第一轮）
products.0008_alter_productspec_product_name  - ProductSpec产品分类名称调整（第二轮，去掉空格）
orders.0028_order_customer_service_processed_at_and_more  - Order新增SLA时效字段（file_uploaded_at/customer_service_processed_at/factory_notified_at/factory_downloaded_at）
```

---

## 八、已知问题

1. **PostgreSQL已安装但认证配置有问题**（pg_hba.conf需要改为md5认证），当前回退到SQLite
2. **Python 3.8 弃用警告** - PyMySQL的cryptography库提示Python 3.8不再支持，不影响运行但建议后续升级
3. **Nginx systemctl重启会失败**（80端口被占用），需要用 `kill -9` 杀掉旧进程后用 `nginx` 命令启动
4. **GitHub推送间歇性超时** — 需要多次重试

---

## 九、环境变量

```bash
# .env文件路径
/home/magnesium/magnesium_order_platform/.env

# 关键配置
OSS_INTERNAL=true  # ECS内网访问OSS
DB_ENGINE=sqlite3  # 当前使用SQLite
```

---

## 十、文件清单

| 文件 | 说明 |
|------|------|
| `平台部署时间进度表_详细版_6月5日-30日.xlsx` | 最新项目进度表（6个Sheet） |
| `PROJECT_STATUS.md` | 本文件 |
| `业务流程文档_v2.xlsx` | 业务流程 |
| `功能说明文档_v2.xlsx` | 功能说明 |
| `系统规格说明书_v2.xlsx` | 系统规格 |

---

## 十一、快速恢复命令

```bash
# 1. 连接服务器（Xshell）
# IP: 47.100.212.79

# 2. 进入项目目录
cd /home/magnesium/magnesium_order_platform

# 3. 激活虚拟环境
source venv/bin/activate

# 4. 拉取最新代码
git pull origin master

# 5. 执行迁移
python manage.py migrate

# 6. 收集静态文件
python manage.py collectstatic --noinput

# 7. 重启Nginx（如果失败用kill方式）
nginx -s reload
# 或
kill -9 $(pgrep nginx)
nginx

# 8. 重启Django服务
pkill -9 -f runserver
sleep 2
nohup python manage.py runserver 127.0.0.1:8000 > server.log 2>&1 &

# 9. 确认服务状态
ps aux | grep runserver
ps aux | grep nginx
```

---

## 十二、本次对话关键决策

1. **UI全面改版** — 已完成：白色侧边栏+蓝色active指示、Font Awesome 6.4图标、统计卡片左侧大图标布局
2. **产品分类重新调整** — 已完成：腐蚀版4种（凹版/凸版/镁凹树凸/双面镁激凸）+ 雕刻版5种（平雕凸/平雕凹/浮雕激凸烫凸一体/浮雕多层次激凸烫凸一体/多层次浮雕）+ 树脂版 + 菲林
3. **红框尺寸修改功能** — 已完成：商户后台可修改，支持添加/删除框，修改后自动重新计算订单金额
4. **上传文件区域2行布局** — 已完成：第一行预览图+文件名，第二行尺寸数量输入
5. **Nginx反向代理配置** — 已完成：`/etc/nginx/conf.d/magnesium.conf` 配置完成
6. **域名备案** — 预计6月8日通过
7. **SLA时效追踪系统** — 已完成：客服30分钟处理+工厂30分钟下载时效追踪
8. **商户端数据分析中心** — 已完成：独立数据分析页面，8个KPI+6个图表+SLA面板

---

*此文件应在每次重要变更后更新*
