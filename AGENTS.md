# AGENTS.md — 镁印制版下单系统（闪电制版 / 制版家）

> 本文档面向 AI 编程助手，描述项目架构、技术栈、开发规范与关键注意事项。所有信息基于项目实际代码与配置文件，不假设任何外部知识。
> 
> **文档版本**: 2.0  
> **生成日期**: 2026-06-07  
> **基于代码版本**: 截至 2026-06-07 的静态分析

---

## 1. 项目概述

**镁印制版下单系统**（品牌名：闪电制版 / 制版家，线上域名 `www.zhibanhome.com`，服务器 IP `47.100.212.79`）是一个面向印刷制版行业的垂直 B2B 订单管理平台。

平台连接三方角色：
- **终端客户**（Customer）：制版需求方，在线下单、查看进度、确认收货、管理对账、发起投诉
- **商家/商户**（Merchant）：制版服务提供方，管理会员、处理订单、拼版排产、发货对账、数据分析
- **平台管理员**（Platform Admin）：系统运营方，审核商家入驻、管理全局规格与权限

系统核心能力：PDF 智能红框识别、自动拼版布局、跨订单批次管理、信用额度对账、版类视觉效果预览、SLA 时效追踪、商户数据分析中心。

---

## 2. 技术栈

| 层级 | 技术 | 版本/说明 |
|------|------|-----------|
| 后端框架 | Django | 4.2 LTS（Python 3.8+） |
| 数据库 | SQLite（开发）/ PostgreSQL（生产）/ MySQL（可选，宝塔面板默认） | 通过 `DB_ENGINE` 环境变量切换 |
| WSGI 服务器 | Gunicorn | 21.0+ |
| Web 服务器 | Nginx | 反向代理 + 静态文件服务 |
| 进程管理 | systemd | Linux 生产环境 |
| 前端框架 | Bootstrap 5.3 | CDN 引入，无构建步骤 |
| 图标库 | Font Awesome 6.4 | CDN 引入（2026-06-06 从 Bootstrap Icons 切换） |
| 图表库 | ECharts 5.4.3 | 仅数据分析中心页 |
| 文件存储 | 阿里云 OSS（生产）/ 本地（开发） | `DEFAULT_FILE_STORAGE` 默认已启用 OSS |
| PDF 处理 | PyMuPDF (fitz) | 1.24+ |
| 图片处理 | Pillow | 10.0+ |
| Excel 处理 | openpyxl | 3.1+ |
| 矩形排版 | rectpack（内嵌修改版） | `utils/rectpack/`，纯 Python，非 pip 包 |
| 数据可视化 | matplotlib | 3.7+（拼版效果图） |
| 物流查询 | 快递100 API | 自建封装 `utils/kuaidi100.py` |

**架构风格**：
- 服务端渲染（SSR）：Django 模板引擎渲染完整 HTML 页面
- 传统 MVC：Django 的 Model-View-Template 模式
- 同步阻塞：使用 Gunicorn sync worker，无异步/Channels
- 多 App 垂直拆分：按用户角色端（客户平台/商家平台/平台管理）拆分 App

**前后端交互**：
- 传统多页应用（MPA），非前后端分离
- 页面跳转靠后端 `render(request, template.html, context)`
- 少量异步操作用原生 `fetch` POST JSON，必须携带 `X-CSRFToken`
- **无 RESTful API（无 DRF）、无 GraphQL、无 WebSocket**

---

## 3. 项目目录结构

```
镁印制版下单系统/
├── magnesium_order_platform/      # 项目配置（settings/urls/wsgi/asgi）
├── apps/                          # 业务应用
│   ├── accounts/                  # 用户认证与账户体系（User/Merchant/CustomerProfile/StaffProfile/Role/Address）
│   ├── admin_platform/            # 平台管理端（商家审核、权限预设、非标审批）
│   ├── common/                    # 公共组件（上下文处理器、未授权页面、模板标签）
│   ├── customer_platform/         # 客户平台（下单、订单查询、对账、子账号、投诉）
│   ├── merchant_platform/         # 商家平台（订单处理、拼版、生产看板、会员、数据分析）
│   ├── orders/                    # 订单核心模型（Order/OrderItem/PlateBatch/Statement/OrderComplaint）
│   └── products/                  # 产品规格模型（ProductSpec/CustomSpecRequest）
├── utils/                         # 工具模块与核心业务逻辑
│   ├── rectpack/                  # 矩形排版算法库（内嵌，非 pip 包）
│   ├── oss_storage.py             # 阿里云 OSS Storage 后端
│   ├── pdf_processor.py           # PDF 基础处理（面积计算/转黑/预览）
│   ├── pdf_preflight.py           # PDF 印前预检（线条/颜色/位图检测）
│   ├── pdf_red_box.py             # PDF 红框智能识别（核心）
│   ├── plate_layout.py            # 单订单拼版算法
│   ├── plate_batch.py             # 跨订单拼版 + 效果图生成（核心，~800 行）
│   ├── plate_pdf.py               # 拼版矢量生产 PDF 生成（核心）
│   ├── plate_preview_effects.py   # 版类视觉效果处理器（9 种效果）
│   ├── plate_type_rules.py        # 版类规则与间距配置
│   ├── pricing_tiers.py           # 价格体系（腐蚀版档位 + 雕刻版固定价）
│   ├── kuaidi100.py               # 快递100 物流查询 SDK
│   └── ...
├── templates/                     # 全局模板目录（65 个 HTML）
│   ├── base.html                  # 基础模板（侧边栏 220px + 主内容区）
│   ├── common/menu.html           # 动态侧边栏菜单
│   ├── customer/                  # 客户平台模板（~17 个）
│   ├── merchant/                  # 商家平台模板（~22 个）
│   ├── admin_platform/            # 平台管理模板（~9 个）
│   ├── accounts/                  # 认证相关模板
│   └── registration/              # 登录页
├── static/                        # 静态文件（CSS 空，JS 含 china_regions.js，images 含 logo）
├── media/                         # 用户上传文件（开发环境本地存储）
│   ├── order_files/               # 订单上传的 PDF/图片
│   ├── plate_layouts/             # 拼版效果图和生产 PDF
│   ├── production_photos/         # 生产/质检/快递照片
│   ├── previews/                  # PDF 预览缩略图
│   └── customer_previews/         # 客户端预览图
├── deploy/                        # 部署配置
│   ├── nginx.conf                 # Nginx 配置模板
│   ├── gunicorn.conf.py           # Gunicorn 配置
│   ├── magnesium.service          # systemd 服务模板
│   ├── deploy.sh                  # 阿里云 ECS 一键部署脚本
│   ├── update.sh                  # 代码更新脚本
│   ├── ssl_certbot.sh             # SSL 证书自动续期
│   ├── QUICK_START.md             # 宝塔面板快速部署指南
│   ├── README.md                  # 阿里云 ECS 完整部署指南
│   └── SOP_代码发布.md             # 代码发布 SOP
├── manage.py                      # Django 管理命令入口（含 .env 自动加载）
├── requirements.txt               # Python 依赖
├── start_server.bat               # Windows 开发启动脚本
├── db.sqlite3                     # 开发环境 SQLite 数据库
├── .env                           # 环境变量文件（生产环境）
├── init_data.py                   # 初始化测试数据脚本
└── ...
```

---

## 4. 关键配置文件

### 4.1 `requirements.txt`
```
Django>=4.2,<5.0
psycopg2-binary>=2.9          # PostgreSQL（生产）
PyMySQL>=1.1                  # MySQL支持（宝塔面板默认使用）
PyMuPDF>=1.24                 # PDF处理（红框识别、矢量嵌入）
Pillow>=10.0                  # 拼版效果图生成
openpyxl>=3.1                 # Excel 导出
requests>=2.31                # HTTP 请求
gunicorn>=21.0                # WSGI 服务器
matplotlib>=3.7               # 报表/图表
django-storages>=1.14         # 对象存储（可选）
oss2>=2.18                    # 阿里云 OSS（可选）
```

### 4.2 `magnesium_order_platform/settings.py`
- 开发默认：`DEBUG=True`，`DB_ENGINE=sqlite3`，`ALLOWED_HOSTS=*`
- 生产切换：通过环境变量 `DJANGO_DEBUG=False`、`DB_ENGINE=postgresql`、`DJANGO_ALLOWED_HOSTS=域名`
- `SECRET_KEY` 默认有占位值，**生产必须通过环境变量 `DJANGO_SECRET_KEY` 覆盖**
- 阿里云 OSS 配置已存在，`DEFAULT_FILE_STORAGE` 默认已启用（指向 `utils.oss_storage.AliyunOSSMediaStorage`）
- `OSS_ACCESS_KEY_ID` 和 `OSS_ACCESS_KEY_SECRET` 优先从环境变量读取，留空则使用本地存储
- 快递100 API Key 默认空字符串，需配置真实值
- 文件上传限制：50MB
- 自定义用户模型：`AUTH_USER_MODEL = 'accounts.User'`，`USERNAME_FIELD = 'phone'`
- 会话有效期：7 天（`SESSION_COOKIE_AGE = 86400 * 7`）

### 4.3 `magnesium_order_platform/urls.py`
根路由按用户角色划分前缀：
```python
path('admin/', admin.site.urls),                    # Django 内置后台
path('accounts/', include('apps.accounts.urls')),   # 认证与账户
path('customer/', include('apps.customer_platform.urls')),   # 客户平台
path('merchant/', include('apps.merchant_platform.urls')),   # 商家平台
path('platform/', include('apps.admin_platform.urls')),      # 平台管理
path('', include('apps.accounts.urls')),            # 根路径 fallback
```

---

## 5. 数据库架构

项目共 **21 个有效数据模型**，分布在 5 个 App 中：

| App | 模型数量 | 模型列表 |
|-----|---------|---------|
| `accounts` | 6 | User, Merchant, CustomerProfile, StaffProfile, Role, Address |
| `orders` | 10 | Order, OrderItem, OrderStatusLog, CommunicationLog, PlateBatch, PlateBatchItem, PlateLayout, ProductionPhoto, DeliveryExtension, Statement, OrderComplaint |
| `merchant_platform` | 3 | Factory, FactoryEquipmentStatus, FactoryInventory |
| `products` | 2 | ProductSpec, CustomSpecRequest |
| `admin_platform` / `common` / `customer_platform` | 0 | （无模型，纯视图/模板层） |

### 5.1 核心模型关系

- `User`（统一用户表，手机号登录）→ `CustomerProfile`（1:1，终端客户）/ `StaffProfile`（1:1，商家员工）/ `managed_merchant`（1:1，商家管理员）
- `Merchant` → `CustomerProfile`（1:N，会员）/ `Factory`（1:N，工厂）/ `ProductSpec`（1:N，规格）/ `Role`（1:N，岗位）
- `Order` → `OrderItem`（1:N，明细）/ `PlateBatch`（N:1，拼版批次）/ `Statement`（N:1，对账单）/ `OrderComplaint`（1:N，投诉）
- `PlateBatch` → `PlateBatchItem`（1:N，拼版项目）
- `CustomerProfile` 自关联 N:1（parent，子账号体系）

### 5.2 订单状态机

```
draft（草稿）
  │
  ▼（客户提交）
pending_confirm（待商家确认）
  │
  ├──► info_error（文件/信息有误）──┐
  │                                 │
  ▼（商家审核通过）                  │
design_confirmed（设计/规格确认）    │
  │                                 │
  ├──► pending_payment（待付款）────┤
  │     │（信用额度支付成功）        │
  │     ▼                           │
  └──► paid（已付款）               │
        │                          │
        ▼（安排生产）                │
  in_production（生产中）           │
        │                         │
        ▼（发货）                  │
  shipped（已发货）◄───────────────┘
        │
        ▼（客户确认/7天自动确认）
  received（已收货）
        │
        ▼（对账结清）
  settled（已结清）
```

---

## 6. 代码组织与模块划分

### 6.1 App 职责

| App | 职责 | 包含内容 |
|-----|------|---------|
| `accounts` | 用户体系 | 模型、认证视图（登录/注册/密码重置）、个人中心、地址管理 |
| `customer_platform` | 客户端 | 客户首页、下单（单页/分步）、订单查询、文件下载、对账、子账号管理、投诉 |
| `merchant_platform` | 商户端 | 商家首页、会员管理、工厂管理、规格管理、订单处理、拼版工具、生产看板、对账单、岗位与子账号、数据分析中心 |
| `admin_platform` | 平台管理端 | 平台首页、商家审核、权限预设、非标规格审批 |
| `orders` | 订单模型层 | 全部订单相关模型、模型方法（计算金额/状态流转/支付）、自定义管理命令 |
| `products` | 产品模型层 | ProductSpec / CustomSpecRequest 模型 |
| `common` | 公共组件 | 全局上下文处理器、未授权页面模板、模板标签 |

### 6.2 权限体系

系统采用 **四层角色 + 岗位权限** 的混合权限模型：

| 角色 | URL 前缀 | 权限范围 |
|------|---------|---------|
| `platform_admin` | `/platform/` + `/accounts/` | 全平台管理：商家审核、全局权限预设、非标审批 |
| `merchant_admin` | `/merchant/` + `/accounts/` | 商家全功能：会员/工厂/规格/订单/拼版/子账号/对账/数据分析 |
| `merchant_staff` | `/merchant/` + `/accounts/` | 受限功能：根据 `Role.permissions` 控制（10 项细粒度权限） |
| `customer` | `/customer/` + `/accounts/` | 仅自身数据：下单/查单/对账/地址/子账号/投诉 |

**自定义装饰器**（定义在各平台 views.py 中）：
- `@login_required` — Django 内置
- `@customer_required` / `@customer_main_required` — 客户权限
- `@merchant_required` / `@merchant_admin_required` — 商家权限
- `@platform_admin_required` — 平台管理员权限

### 6.3 核心工具模块

#### PDF 处理链
```
客户上传 PDF
    │
    ├──► pdf_preflight.py ──► 印前预检报告（线条/颜色/位图）
    │
    ├──► pdf_red_box.py ──► 智能红框识别（多层过滤降噪）
    │     └── 输出: [{x, y, width, height, area, is_red}, ...]
    │
    ├──► pdf_processor.py ──► 面积计算 / 转纯黑 / 预览图生成
    │
    └──► plate_pdf.py ──► 矢量生产 PDF（show_pdf_page 嵌入原始文件）
```

#### 拼版算法链
```
待拼版订单项 (同材质同厚度)
    │
    ├──► plate_layout.py ──► 单订单拼版（Shelf / MaxRects / Guillotine / Skyline）
    │
    └──► plate_batch.py ──► 跨订单拼版（核心）
          │
          ├── 策略1: 单 bin 单规格 ──► 选利用率最高的板材
          ├── 策略2: 多 bin 同规格 ──► 最少张数放下全部
          └── 策略3: Fallback ──► 能放最多的（可能有未放置）
          │
          ├──► plate_preview_effects.py ──► 生成版类视觉效果图（9 种效果）
          │
          └──► plate_pdf.py ──► 生成矢量生产 PDF
```

**拼版算法**：
| 算法 | 来源 | 适用场景 |
|------|------|---------|
| Shelf | 原生实现 (`plate_layout.py`) | 简单场景，快速计算 |
| MaxRectsBssf | rectpack（默认） | 利用率最高，通用首选 |
| GuillotineBssfSas | rectpack | 规则切割场景 |
| SkylineMwf | rectpack | 特定形状优化 |

**间距规则**：同厚度同材质 10~15mm，不同厚度 20mm，不同材质 20mm。

**版类视觉效果映射**（`plate_preview_effects.py`）：
| 效果函数 | 产品类型 | 视觉特征 |
|-------------|---------|---------|
| `effect_normal` | 普通/树脂版 | 清晰黑白 |
| `effect_gold_flat` | 烫金版 | 金色平面光泽 |
| `effect_gold_satin` | 平雕版 | 香槟金柔和光泽 |
| `effect_relief_strong` | 激凸版 | 强浮雕凸起（阴影+高光） |
| `effect_emboss_deboss` | 压纹版 | 压纹凹陷（内阴影） |
| `effect_deboss_strong` | 激凹版 | 强凹陷 |
| `effect_relief_gold` | 浮雕版 | 金色浮雕 |
| `effect_relief_gold_multi` | 多层次浮雕版 | 多层金色浮雕 |
| `effect_film_transparent` | 菲林 | 半透明淡蓝灰 |

---

## 7. 构建与运行命令

### 7.1 开发环境（Windows）

```bash
# 安装依赖
pip install -r requirements.txt

# 数据库迁移
python manage.py migrate

# 初始化测试数据（如存在 init_data.py）
python init_data.py

# 启动开发服务器
python manage.py runserver
# 或双击运行 start_server.bat（自动清理 8000 端口、显示局域网 IP）
```

开发测试账号：
| 角色 | 手机号 | 密码 |
|------|--------|------|
| 总平台管理员 | 13800000000 | admin123 |
| 商家管理员 | 13800138000 | admin123 |
| 终端用户 | 13900139000 | admin123 |
| 客服岗（内测） | 13800138002 / 13800138005 / 13800138006 | admin123 |

商家邀请码（客户注册用）：`MA1B2C3`

### 7.2 生产环境（Linux / 阿里云 ECS）

```bash
# 首次部署（一键脚本）
cd /home/magnesium/magnesium_order_platform
chmod +x deploy/deploy.sh
sudo bash deploy/deploy.sh

# 代码更新
sudo bash deploy/update.sh

# 手动运维命令
sudo systemctl status magnesium      # 查看服务状态
sudo systemctl restart magnesium     # 重启服务
sudo systemctl reload nginx          # 重载 Nginx
sudo tail -f /var/log/gunicorn/magnesium_error.log   # 查看错误日志
```

### 7.3 自定义管理命令

| 命令 | 功能 | 建议调度 |
|------|------|---------|
| `python manage.py auto_confirm_receipt` | 发货 7 天自动确认收货 | 每日定时任务 (cron) |
| `python manage.py fix_credit_used` | 修复客户 `credit_used` 字段 | 手动执行 |
| `python manage.py generate_monthly_statements` | 按月自动生成对账单 | 每月 1 日执行 |
| `python manage.py sync_files_to_oss` | 批量同步本地文件到 OSS | 迁移/备份时执行 |

---

## 8. 测试策略

**当前状态**：项目中的 `tests.py` 文件均为 Django 默认生成的空模板（仅包含 `from django.test import TestCase`），**尚未编写实际测试用例**。

| 维度 | 现状 | 建议 |
|------|------|------|
| 单元测试 | ❌ 无 | 为 `utils/` 中的核心算法（拼版、PDF处理、价格计算）编写测试 |
| 集成测试 | ❌ 无 | 为订单状态流转、支付流程编写测试 |
| 端到端测试 | ❌ 无 | 使用 Selenium/Playwright 测试关键用户流程 |
| 手动测试 | ✅ 有内部测试文档 | `测试说明.md` 描述了局域网测试流程和测试账号 |

**运行测试命令**：
```bash
python manage.py test
```

---

## 9. 代码风格指南

### 9.1 Python 代码
- 遵循 PEP 8，使用 4 空格缩进
- 模型字段使用中文 `verbose_name`
- 视图函数使用中文 docstring 说明职责
- 自定义装饰器命名：`{role}_required`，如 `@merchant_required`
- 工具函数模块按职责拆分，避免单文件过大

### 9.2 模板与前端
- 所有模板继承 `base.html`，通过 `{% block content %}` 填充内容
- CSS 变量定义在 `base.html` 的 `:root` 中
- 原生 JavaScript（Vanilla JS），无 jQuery/Vue/React
- AJAX 请求使用 `fetch` API，必须携带 `X-CSRFToken`
- Bootstrap 5.3 + Font Awesome 6.4 通过 CDN 引入

### 9.3 模型规范
- 主键使用 `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)`
- 外键使用 `related_name` 定义反向关系
- 金额字段使用 `DecimalField(max_digits=12, decimal_places=2)`
- 状态字段使用 `CharField(choices=...)`
- 自动编号（订单号/对账单号）在 `save()` 中生成

---

## 10. 安全注意事项

### 10.1 当前安全机制

| 机制 | 状态 | 说明 |
|------|------|------|
| CSRF 保护 | ✅ 已启用 | `CsrfViewMiddleware` |
| XSS 防护 | ✅ 已启用 | `SECURE_BROWSER_XSS_FILTER` |
| 点击劫持 | ✅ 已启用 | `XFrameOptionsMiddleware` (SAMEORIGIN) |
| MIME 嗅探防护 | ✅ 已启用 | `SECURE_CONTENT_TYPE_NOSNIFF` |
| 密码强度校验 | ✅ 已启用 | 4 种 Django 内置校验器 |
| 文件上传大小限制 | ✅ 已启用 | 50MB |

### 10.2 已知风险

| # | 风险 | 严重程度 | 建议 |
|---|------|---------|------|
| 1 | **OSS 密钥硬编码** | 🔴 高 | `settings.py` 中 `OSS_ACCESS_KEY_ID` 和 `OSS_ACCESS_KEY_SECRET` 应迁移至环境变量 |
| 2 | **无日志配置** | 🟡 中 | `settings.py` 中未定义 `LOGGING`，生产环境需补充文件日志配置 |
| 3 | **DEBUG 默认 True** | 🟡 中 | 未设置 `DJANGO_DEBUG` 环境变量时默认开启 DEBUG，生产易误配 |
| 4 | **SQLite 为默认数据库** | 🟡 中 | 未设置 `DB_ENGINE` 时默认 SQLite，生产部署需显式切换 |
| 5 | **HTTPS 配置被注释** | 🟡 中 | `SECURE_SSL_REDIRECT`、`SESSION_COOKIE_SECURE` 等被注释，启用 HTTPS 后需取消注释 |
| 6 | **开发脚本含绝对路径** | 🟢 低 | `start_server.bat` 硬编码了开发者本地路径 |

---

## 11. 部署架构

```
用户浏览器
    │ HTTPS
    ▼
Nginx (反向代理)
    - Server Name: www.zhibanhome.com, zhibanhome.com
    - Client Max Body: 50M
    - /static/ → staticfiles/ (缓存 30 天)
    - /media/ → media/ (缓存 7 天)
    - 其他 → proxy_pass http://127.0.0.1:8000
    │
    ▼
Gunicorn (WSGI 服务器)
    - bind: 127.0.0.1:8000
    - workers: CPU * 2 + 1
    - worker_class: sync
    - max_requests: 1000
    - timeout: 120 秒
    │
    ▼
Django Application
    - WSGI 入口: magnesium_order_platform.wsgi
    - 静态文件: WhiteNoise（开发）/ Nginx（生产）
    - 媒体文件: 本地（开发）/ 阿里云 OSS（生产）
    │
    ├──────► PostgreSQL/MySQL（生产数据库）
    └──────► 阿里云 OSS（文件存储）
```

---

## 12. 关键数据契约：`layout_data` JSON 格式

拼版结果存储在 `PlateBatch.layout_data` 中，格式如下：

```json
{
  "plate_width": 610,
  "plate_height": 914,
  "plate_spec_name": "610×914mm",
  "placed_count": 5,
  "usage_rate": 78.5,
  "algorithm": "maxrects",
  "rectangles": [
    {
      "id": "order-item-uuid_0",
      "x": 0,
      "y": 0,
      "width": 120,
      "height": 80,
      "rotation": 0,
      "label": "SN20250001",
      "order_sn": "SN20250001",
      "customer_phone": "13800138000"
    }
  ]
}
```

**坐标系约定**：原点在板材左上角，X 向右，Y 向下。生产 PDF 生成时自动转换为 PDF 坐标系（原点在左下角，Y 向上）。

---

## 13. 文档索引

| 文档 | 内容 |
|------|------|
| `README.md` | 项目简介、快速启动、测试账号 |
| `PROJECT_ARCHITECTURE.md` | 完整架构文档（技术栈、数据库 ER 图、业务流程、部署运维） |
| `PROJECT_STATUS.md` | 项目状态记录（已完成功能、进行中、待开始、已知问题、快速恢复命令） |
| `CHANGELOG.md` | 每日变更日志（按 conventional commit 类型分类） |
| `PLATE_LAYOUT_TECH_GUIDE.md` | 拼版功能技术栈与嵌入对接指南 |
| `deploy/QUICK_START.md` | 宝塔面板快速部署指南 |
| `deploy/README.md` | 阿里云 ECS 完整部署指南 |
| `测试说明.md` | 内部测试人员操作指南 |
| `服务器部署指南.txt` | 服务器部署步骤速查 |
| `业务流程文档_v2.xlsx` | 业务流程说明 |
| `功能说明文档_v2.xlsx` | 功能模块说明 |
| `系统规格说明书_v2.xlsx` | 系统规格说明 |

---

## 14. 项目统计

| 指标 | 数值 |
|------|------|
| Python 文件数 | ~125 |
| Python 代码行数 | ~14,500（apps: ~8,800 + utils: ~5,700） |
| HTML 模板数 | 65 |
| 数据库模型数 | 21 |
| 数据库迁移文件数 | ~49 |
| Git 提交数 | 94+ |
| 测试覆盖率 | 0%（尚未编写测试） |

---

> **文档版本**: 2.0  
> **生成日期**: 2026-06-07  
> **基于代码版本**: 截至 2026-06-07 的静态分析
