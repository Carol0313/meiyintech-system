# 镁印制版下单系统 — 架构文档

> 文档版本: 1.0  
> 生成日期: 2026-06-03  
> 项目名称: 闪电制版 / magnesium_order_platform  
> 线上域名: www.zhibanhome.com

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术架构](#2-技术架构)
3. [项目目录结构](#3-项目目录结构)
4. [数据库架构](#4-数据库架构)
5. [后端架构](#5-后端架构)
6. [前端架构](#6-前端架构)
7. [核心业务流程](#7-核心业务流程)
8. [部署与运维](#8-部署与运维)
9. [安全与风险](#9-安全与风险)
10. [附录](#10-附录)

---

## 1. 项目概述

**镁印制版下单系统**（又称"闪电制版"）是一个面向制版行业的垂直 B2B 订单管理平台。平台连接三方角色：

- **终端客户**（Customer）：制版需求方，可在线下单、查看进度、确认收货、管理对账
- **商家/商户**（Merchant）：制版服务提供方，管理会员、处理订单、拼版排产、发货对账
- **平台管理员**（Platform Admin）：系统运营方，审核商家入驻、管理全局规格与权限

系统核心能力包括：PDF 智能红框识别、自动拼版布局、跨订单批次管理、信用额度对账、版类视觉效果预览等。

### 1.1 业务领域

| 维度 | 内容 |
|------|------|
| 产品类型 | 腐蚀版、雕刻版、树脂版、菲林等 10 种制版工艺 |
| 材质 | 镁、铜、锌、不锈钢、树脂 |
| 计价方式 | 按面积计价（元/cm²），支持省份档位定价和商户自定义报价 |
| 核心特色 | PDF 红框自动识别 → 面积自动计算 → 智能拼版 → 矢量生产 PDF |

---

## 2. 技术架构

### 2.1 技术栈

| 层级 | 技术选型 | 版本/说明 |
|------|---------|----------|
| 后端框架 | Django | 4.2 LTS（Python 3.8） |
| 数据库 | SQLite（开发）/ PostgreSQL（生产）/ MySQL（可选） | 通过 `DB_ENGINE` 环境变量切换 |
| WSGI 服务器 | Gunicorn | 21.0+ |
| Web 服务器 | Nginx | 反向代理 + 静态文件服务 |
| 进程管理 | systemd | Linux 生产环境 |
| 前端框架 | Bootstrap 5.3 | CDN 引入 |
| 图标库 | Bootstrap Icons | 1.10.5 |
| 图表库 | ECharts | 5.4.3（仅订单统计页） |
| 文件存储 | 阿里云 OSS | 生产环境默认启用 |
| PDF 处理 | PyMuPDF (fitz) | 1.24+ |
| 图片处理 | Pillow | 10.0+ |
| Excel 处理 | openpyxl | 3.1+ |
| 矩形排版 | rectpack（内嵌修改版） | MaxRects/Guillotine/Skyline |
| 数据可视化 | matplotlib | 3.7+（拼版效果图） |
| 物流查询 | 快递100 API | 自建封装 `utils/kuaidi100.py` |

### 2.2 架构风格

- **服务端渲染 (SSR)**：Django 模板引擎渲染完整 HTML 页面
- **传统 MVC**：Django 的 Model-View-Template 模式
- **同步阻塞**：使用 Gunicorn sync worker，无异步/Channels
- **多 App 垂直拆分**：按用户角色端（客户平台/商家平台/平台管理）拆分 App，而非按功能域拆分

---

## 3. 项目目录结构

```
镁印制版下单系统/
├── magnesium_order_platform/      # 项目配置（settings/urls/wsgi/asgi）
├── apps/                          # 业务应用
│   ├── accounts/                  # 用户认证与账户体系（User/Merchant/Customer/Staff/Role/Address）
│   ├── admin_platform/            # 平台管理端（商家审核、权限预设、非标审批）
│   ├── common/                    # 公共组件（上下文处理器、未授权页面）
│   ├── customer_platform/         # 客户平台（下单、订单查询、对账、子账号）
│   ├── merchant_platform/         # 商家平台（订单处理、拼版、生产看板、会员）
│   ├── orders/                    # 订单核心模型（Order/OrderItem/PlateBatch/Statement）
│   └── products/                  # 产品规格模型（ProductSpec/CustomSpecRequest）
├── utils/                         # 工具模块与核心业务逻辑
│   ├── rectpack/                  # 矩形排版算法库
│   ├── oss_storage.py             # 阿里云 OSS Storage 后端
│   ├── pdf_processor.py           # PDF 基础处理（面积计算/转黑/预览）
│   ├── pdf_preflight.py           # PDF 印前预检（线条/颜色/位图检测）
│   ├── pdf_red_box.py             # PDF 红框智能识别（核心）
│   ├── plate_layout.py            # 单订单拼版算法
│   ├── plate_batch.py             # 跨订单拼版 + 效果图生成（核心）
│   ├── plate_pdf.py               # 拼版矢量生产 PDF 生成（核心）
│   ├── plate_preview_effects.py   # 版类视觉效果处理器
│   ├── plate_type_rules.py        # 版类规则与间距配置
│   ├── pricing_tiers.py           # 价格体系（腐蚀版档位 + 雕刻版固定价）
│   ├── kuaidi100.py               # 快递100 物流查询 SDK
│   └── ...                        # 其他辅助模块
├── templates/                     # 全局模板目录
│   ├── base.html                  # 基础模板（侧边栏 + 主内容区）
│   ├── common/                    # 公共片段（菜单、未授权页）
│   ├── customer/                  # 客户平台模板（17 个）
│   ├── merchant/                  # 商家平台模板（22 个）
│   ├── admin_platform/            # 平台管理模板（9 个）
│   ├── accounts/                  # 认证相关模板
│   └── registration/              # 登录页
├── static/                        # 静态文件
│   ├── css/                       # （空，CSS 全部内联）
│   ├── js/                        # china_regions.js（省市区数据）
│   └── images/                    # logo.png, login-bg.jpg
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
│   ├── deploy.sh / update.sh      # 部署/更新脚本
│   └── ...
├── manage.py                      # Django 管理命令入口
├── requirements.txt               # Python 依赖
├── start_server.bat               # Windows 开发启动脚本
└── db.sqlite3                     # 开发环境 SQLite 数据库
```

---

## 4. 数据库架构

### 4.1 模型总览

项目共 **21 个有效数据模型**，分布在 5 个 App 中：

| App | 模型数量 | 模型列表 |
|-----|---------|---------|
| `accounts` | 6 | User, Merchant, CustomerProfile, StaffProfile, Role, Address |
| `orders` | 10 | Order, OrderItem, OrderStatusLog, CommunicationLog, PlateBatch, PlateBatchItem, PlateLayout, ProductionPhoto, DeliveryExtension, Statement |
| `merchant_platform` | 3 | Factory, FactoryEquipmentStatus, FactoryInventory |
| `products` | 2 | ProductSpec, CustomSpecRequest |
| `admin_platform` / `common` / `customer_platform` | 0 | （无模型，纯视图/模板层） |

### 4.2 实体关系图（ER）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            accounts (用户体系)                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────┐           ┌─────────────────┐           ┌──────────┐        │
│   │   User   │◄──1:1────►│ CustomerProfile │◄──N:1────►│ Merchant │        │
│   │(统一用户)│           │  (终端客户资料)  │           │ (商家)   │        │
│   └────┬─────┘           └────────┬────────┘           └────┬─────┘        │
│        │                          │                       │                │
│        │◄─────────1:1─────────────┘                       │                │
│        │◄─────────────────1:1──────────────────────────────┘                │
│        │                                                                    │
│   ┌────┴─────┐           ┌──────────┐                                       │
│   │StaffProfile│◄──N:1───►│   Role   │◄──N:1───► Merchant                  │
│   │(员工资料) │           │(岗位角色)│                                       │
│   └──────────┘           └──────────┘                                       │
│        ▲                                                                    │
│        │                                                                    │
│   ┌────┴─────┐                                                              │
│   │  Address │◄──N:1───► User                                              │
│   │(收货地址)│                                                               │
│   └──────────┘                                                              │
│                                                                             │
│   CustomerProfile ──自关联 N:1 ──► parent (主/子账号)                        │
│   Merchant.admin_user ──1:1───► User (商家管理员)                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                        merchant_platform (工厂管理)                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   Merchant ◄──1:N─── Factory ◄──1:1─── FactoryEquipmentStatus               │
│                   │                                                         │
│                   └──1:N─── FactoryInventory                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           orders (订单核心)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌────────┐          ┌───────────┐          ┌─────────────────────────┐   │
│   │ Statement│◄──1:N───│   Order   │◄──1:N───│       OrderItem         │   │
│   │(对账单)  │         │ (订单主表) │         │      (订单明细)          │   │
│   └────────┘          └─────┬─────┘          └─────┬───────────────────┘   │
│                             │                      │                       │
│         ┌───────────────────┼──────────────────────┘                       │
│         │                   │                                              │
│         ▼                   ▼                                              │
│   ┌────────────┐     ┌────────────┐                                       │
│   │OrderStatusLog│   │PlateBatch  │◄──1:N─── PlateBatchItem               │
│   │(状态日志)    │   │(拼版批次)   │         │        │                    │
│   └────────────┘     └────────────┘         │        └──► OrderItem        │
│                             │               └──► Order                    │
│         ┌───────────────────┼──────────────────────┐                       │
│         ▼                   ▼                      ▼                       │
│   ┌────────────┐     ┌────────────┐      ┌─────────────────┐              │
│   │Communication│    │PlateLayout │      │ ProductionPhoto │              │
│   │(沟通记录)   │    │(旧版拼版)   │      │  (生产照片)      │              │
│   └────────────┘     └────────────┘      └─────────────────┘              │
│                                                                            │
│   Order ──自关联 N:1 ──► original_order (补版单)                            │
│   Order ──N:1 ──► User (customer / design_assigned_to / remake_initiator)  │
│   Order ──N:1 ──► Merchant / Factory / Address                             │
│   Order ──N:1 ──► Statement                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          products (产品规格)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ProductSpec ◄──N:1─── Merchant                                            │
│   CustomSpecRequest ◄──N:1─── Merchant                                      │
│   CustomSpecRequest ──N:1───► User (reviewed_by)                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.3 核心模型详细说明

#### 4.3.1 `accounts.User` — 统一用户表

| 字段 | 类型 | 说明 |
|------|------|------|
| `phone` | CharField(unique) | **登录字段** (`USERNAME_FIELD`)，手机号登录 |
| `user_type` | CharField(choices) | `platform_admin` / `merchant_admin` / `merchant_staff` / `customer` |
| `avatar` | ImageField | 用户头像 |
| `is_approved` | BooleanField | 是否审核通过 |

扩展 `AbstractUser`，废弃 `email` 作为登录标识，改为手机号体系。

#### 4.3.2 `accounts.Merchant` — 商家/商户

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUIDField | UUID 主键 |
| `admin_user` | OneToOneField → User | 商家管理员账号 |
| `status` | CharField(choices) | `pending` / `approved` / `rejected` / `frozen` |
| `invite_code` | CharField(unique) | 商家邀请码（自动生成：`M` + 6位十六进制） |
| `max_sub_accounts` | PositiveIntegerField | 子账号上限（默认 5） |
| `annual_fee_paid` | BooleanField | 开户服务费是否已支付 |

#### 4.3.3 `accounts.CustomerProfile` — 终端客户资料

| 字段 | 类型 | 说明 |
|------|------|------|
| `user` | OneToOneField → User | 关联用户 |
| `merchant` | ForeignKey → Merchant | 归属商家 |
| `credit_limit` | DecimalField | 信用额度 |
| `credit_used` | DecimalField | 已用额度 |
| `pricing_tier` | PositiveSmallIntegerField | 价格档位（1~3，默认 3） |
| `custom_prices` | TextField | JSON 格式自定义报价 |
| `is_main_account` | BooleanField | 是否主账号 |
| `parent` | ForeignKey → self | 所属主账号（子账号体系） |
| `max_sub_accounts` | PositiveIntegerField | 子账号上限（默认 10） |

**属性**: `credit_remaining` = `credit_limit` - `credit_used`

#### 4.3.4 `orders.Order` — 订单主表

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUIDField | UUID 主键 |
| `sn` | CharField(unique) | 订单编号（自动生成：`O` + 年月日 + 6位随机大写） |
| `customer` | ForeignKey → User | 下单客户 |
| `merchant` | ForeignKey → Merchant | 所属商家 |
| `status` | CharField(choices) | **10 种状态**，见下方状态机 |
| `plate_status` | CharField(choices) | 拼版状态：`none` / `auto_generated` / `confirmed` / `rejected` |
| `order_type` | CharField(choices) | `normal` / `remake`（补版单） |
| `total_amount` | DecimalField | 订单总金额 |
| `urgent` | BooleanField | 是否加急（+10% 费用） |
| `delivery_type` | CharField(choices) | `express`（快递）/ `flash`（跑腿） |
| `tracking_number` | CharField | 物流单号 |
| `original_order` | ForeignKey → self | 原订单（补版单关联） |
| `statement` | ForeignKey → Statement | 所属对账单 |
| `is_settled` | BooleanField | 是否已结清 |

**订单状态机：**

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

#### 4.3.5 `orders.OrderItem` — 订单明细

| 字段 | 类型 | 说明 |
|------|------|------|
| `order` | ForeignKey → Order | 所属订单 |
| `product_name` | CharField(choices) | 产品名称（10 种工艺） |
| `material` | CharField(choices) | 材质：镁 / 铜 / 锌 / 不锈钢 / 树脂 / 菲林 |
| `thickness` | CharField(choices) | 厚度：1.5 / 2.0 / 3.0 / 4.0 / 6.0 / 6.35 / - |
| `length_mm` / `width_mm` | DecimalField | 尺寸（mm） |
| `quantity` | PositiveIntegerField | 数量 |
| `unit_price` | DecimalField | 单价（元/cm²） |
| `area` | DecimalField | 面积（cm²） |
| `subtotal` | DecimalField | 小计（元） |
| `file` | FileField | 上传的设计文件 |
| `red_box_data` | TextField | 红框识别数据（JSON） |
| `plate_batch` | ForeignKey → PlateBatch | 所属拼版批次 |

**面积计算规则（save 时自动计算）：**
- **腐蚀版**：单边 +5mm 版边；支持多框（`red_box_data`），每框单独加版边后求和
- **雕刻版**：四周各 +10mm 版边（即 +20mm）
- 小计 = 面积 × 单价 × 数量

#### 4.3.6 `orders.PlateBatch` — 拼版批次（新版核心）

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUIDField | UUID 主键 |
| `merchant` / `factory` | ForeignKey | 所属商家/生产工厂 |
| `product_name` / `material` / `thickness` | CharField | 分组维度（同类型才能拼版） |
| `plate_spec_name` | CharField | 板材规格 |
| `plate_width` / `plate_height` | FloatField | 板材尺寸（mm） |
| `layout_data` | TextField | 拼版布局数据（JSON） |
| `layout_image` | ImageField | 拼版效果图 |
| `production_pdf` | FileField | 生产 PDF 文件 |
| `usage_rate` | FloatField | 材料利用率（%） |
| `status` | CharField(choices) | `auto_generated` / `confirmed` / `rejected` / `in_production` |
| `designer` | ForeignKey → User | 设计师 |

#### 4.3.7 `orders.PlateBatchItem` — 拼版批次项目

| 字段 | 类型 | 说明 |
|------|------|------|
| `plate_batch` | ForeignKey → PlateBatch | 所属批次 |
| `order` / `order_item` | ForeignKey | 关联订单/明细 |
| `x` / `y` | FloatField | 在板材上的坐标（mm） |
| `width` / `height` | FloatField | 放置尺寸（mm） |
| `rotation` | IntegerField | 旋转角度（0 或 90） |

#### 4.3.8 `orders.Statement` — 月度对账单

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUIDField | UUID 主键 |
| `sn` | CharField(unique) | 对账单号（`S` + 年月日 + 6位随机大写） |
| `customer` / `merchant` | ForeignKey | 客户 / 商家 |
| `period_start` / `period_end` | DateField | 账单周期 |
| `total_amount` | DecimalField | 账单总金额 |
| `status` | CharField(choices) | `pending` / `confirmed` / `paid` / `settled` |

#### 4.3.9 `products.ProductSpec` — 商品规格

| 字段 | 类型 | 说明 |
|------|------|------|
| `product_name` / `material` / `thickness` | CharField | 规格组合 |
| `unit_price` | DecimalField | 单价（元/cm²） |
| `is_platform_preset` | BooleanField | 是否平台预设 |
| `merchant` | ForeignKey → Merchant | 所属商家（null 表示平台预设） |

**唯一约束**: `[product_name, material, thickness, merchant]`

### 4.4 关键数据库索引与约束

- `User.phone` — unique
- `Merchant.invite_code` — unique
- `Order.sn` — unique
- `Statement.sn` — unique
- `ProductSpec` — `unique_together = [product_name, material, thickness, merchant]`
- `Role` — `unique_together = [merchant, name]`

---

## 5. 后端架构

### 5.1 App 职责划分

| App | 职责 | 包含内容 |
|-----|------|---------|
| `accounts` | 用户体系 | 模型（User/Merchant/CustomerProfile/StaffProfile/Role/Address）、认证视图（登录/注册/密码重置）、个人中心、地址管理 |
| `customer_platform` | 客户端 | 客户首页、下单（单页/分步）、订单查询、文件下载、对账、子账号管理 |
| `merchant_platform` | 商户端 | 商家首页、会员管理、工厂管理、规格管理、订单处理、拼版工具、生产看板、对账单、岗位与子账号 |
| `admin_platform` | 平台管理端 | 平台首页、商家审核、权限预设、非标规格审批 |
| `orders` | 订单模型层 | 全部订单相关模型、模型方法（计算金额/状态流转/支付）、自定义管理命令 |
| `products` | 产品模型层 | ProductSpec / CustomSpecRequest 模型 |
| `common` | 公共组件 | 全局上下文处理器、未授权页面模板 |

### 5.2 URL 路由架构

根路由按用户角色划分前缀：

```python
urlpatterns = [
    path('admin/', admin.site.urls),                    # Django 内置后台
    path('accounts/', include('apps.accounts.urls')),   # 认证与账户
    path('customer/', include('apps.customer_platform.urls')),   # 客户平台
    path('merchant/', include('apps.merchant_platform.urls')),   # 商家平台
    path('platform/', include('apps.admin_platform.urls')),      # 平台管理
    path('', include('apps.accounts.urls')),            # 根路径 fallback
]
```

#### 各平台路由统计

| 平台 | 路由数量 | 核心路径 |
|------|---------|---------|
| `accounts` | 10 | `/accounts/login/`, `/accounts/register/customer/`, `/accounts/profile/`, `/accounts/addresses/` |
| `customer_platform` | 25 | `/customer/place-order/`, `/customer/orders/`, `/customer/statements/`, `/customer/subaccounts/` |
| `merchant_platform` | 34 | `/merchant/orders/`, `/merchant/plate-batches/`, `/merchant/members/`, `/merchant/statements/`, `/merchant/production-board/` |
| `admin_platform` | 11 | `/platform/merchants/`, `/platform/roles/`, `/platform/spec-requests/` |

### 5.3 权限体系

系统采用 **四层角色 + 岗位权限** 的混合权限模型：

| 角色 | URL 前缀 | 权限范围 |
|------|---------|---------|
| `platform_admin` | `/platform/` + `/accounts/` | 全平台管理：商家审核、全局权限预设、非标审批 |
| `merchant_admin` | `/merchant/` + `/accounts/` | 商家全功能：会员/工厂/规格/订单/拼版/子账号/对账 |
| `merchant_staff` | `/merchant/` + `/accounts/` | 受限功能：根据 `Role.permissions` 控制（10 项细粒度权限） |
| `customer` | `/customer/` + `/accounts/` | 仅自身数据：下单/查单/对账/地址/子账号 |

**商家员工岗位权限** (`Role.permissions`)：
- `order_view` / `order_process` — 订单查看/处理
- `design_layout` — 拼版设计
- `production_manage` — 生产管理
- `finance_statement` — 财务对账
- `member_manage` — 会员管理
- 等共 10 项

**自定义装饰器**：
- `@login_required` — Django 内置
- `@customer_required` — 仅已审核通过的终端客户
- `@customer_main_required` — 仅客户主账号
- `@merchant_required` — 商家管理员或员工（验证资料有效性）
- `@merchant_admin_required` — 仅商家管理员
- `@platform_admin_required` — 仅平台管理员

### 5.4 核心工具模块详解

#### 5.4.1 PDF 处理链

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

#### 5.4.2 拼版算法链

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

**拼版算法详细说明：**

| 算法 | 来源 | 适用场景 |
|------|------|---------|
| **Shelf** | 原生实现 (`plate_layout.py`) | 简单场景，快速计算 |
| **MaxRectsBssf** | rectpack（默认） | 利用率最高，通用首选 |
| **GuillotineBssfSas** | rectpack | 规则切割场景 |
| **SkylineMwf** | rectpack | 特定形状优化 |

**间距规则：**
- 同厚度同材质：10~15mm
- 不同厚度：20mm
- 不同材质：20mm

**版类视觉效果映射：**

| 版类效果函数 | 产品类型 | 视觉特征 |
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

#### 5.4.3 价格体系

```
腐蚀版（按省份档位）
├── 1档（偏远省份）: 0.15 ~ 0.35 元/cm²
├── 2档: 0.12 ~ 0.30 元/cm²
└── 3档（制造集中地）: 0.10 ~ 0.25 元/cm²
    （厚度 1.5/2.0/3.0mm 对应不同单价）

雕刻版 / 树脂版 / 菲林（固定单价）
└── 产品 × 材质 × 厚度 = 固定单价

实际报价优先级：商户自定义价 > 平台预设价
```

#### 5.4.4 自定义管理命令

| 命令 | 功能 | 建议调度 |
|------|------|---------|
| `auto_confirm_receipt` | 发货 7 天自动确认收货 | 每日定时任务 (cron) |
| `fix_credit_used` | 修复客户 `credit_used` 字段 | 手动执行 |
| `generate_monthly_statements` | 按月自动生成对账单 | 每月 1 日执行 |
| `sync_files_to_oss` | 批量同步本地文件到 OSS | 迁移/备份时执行 |

---

## 6. 前端架构

### 6.1 技术特征

| 维度 | 特征 |
|------|------|
| 渲染模式 | 服务端渲染 (SSR)，Django 模板引擎 |
| CSS 框架 | Bootstrap 5.3（CDN） |
| 图标库 | Bootstrap Icons |
| JS 方案 | **原生 JavaScript（Vanilla JS）**，无 jQuery/Vue/React |
| 图表 | ECharts 5.4.3（仅 `customer/my_orders.html`） |
| 样式方案 | Bootstrap 基础 + 大量内联自定义 CSS（无独立 CSS 文件） |
| 响应式 | 基础移动端适配（侧边栏可隐藏） |

### 6.2 模板继承体系

所有 **56 个 HTML 模板全部直接继承自 `base.html`**，结构扁平：

```
base.html
├── {% include "common/menu.html" %}      # 动态侧边栏菜单
│
├── registration/login.html
├── accounts/customer_register.html
├── accounts/merchant_register.html
├── accounts/forget_password.html
│
├── customer/          # 17 个模板
│   ├── dashboard.html
│   ├── place_order.html          # 最复杂：规格组管理 + 文件上传 + AJAX识别
│   ├── order_step1.html ~ order_step7.html   # 分步下单
│   ├── my_orders.html            # ECharts 统计 + 文件预览
│   ├── order_detail.html
│   ├── statements.html
│   └── ...
│
├── merchant/          # 22 个模板
│   ├── dashboard.html
│   ├── orders.html               # 批量操作 + 双 Tab 筛选
│   ├── order_detail.html         # 多 action 订单处理
│   ├── plate_batch_list.html
│   ├── plate_layout_work.html    # CSS 绝对定位拼版画布
│   ├── production_board.html
│   ├── members.html
│   ├── statements.html
│   └── ...
│
└── admin_platform/    # 9 个模板
    ├── dashboard.html
    ├── merchants.html
    ├── roles.html
    └── spec_requests.html
```

### 6.3 `base.html` 布局结构

```
┌────────────────────────────────────────────────────────┐
│  ┌─────────────┐  ┌─────────────────────────────────┐  │
│  │  Sidebar    │  │  Topbar                         │  │
│  │  (220px)    │  │  - page_title / page_subtitle   │  │
│  │             │  └─────────────────────────────────┘  │
│  │  - Logo     │  ┌─────────────────────────────────┐  │
│  │  - Menu     │  │                                 │  │
│  │  - User Pill│  │  content-body                   │  │
│  │             │  │  (padding: 20px 24px)           │  │
│  └─────────────┘  │                                 │  │
│                   └─────────────────────────────────┘  │
│                                                        │
│  [fixed] 联系客服浮动按钮 (右下角)                       │
└────────────────────────────────────────────────────────┘
```

### 6.4 动态菜单 (`common/menu.html`)

根据 `user.user_type` 条件渲染四种角色的导航菜单：

- **`customer`**：首页、下单、我的订单、地址管理、个人中心、子账号管理
- **`merchant_admin`**：管理中心、会员管理、工厂管理、商品规格、订单管理、拼版工具、生产看板、岗位权限、子账号、账号设置
- **`merchant_staff`**：首页 + 根据 `role_name` 动态显示（designer→拼版、customer_service→订单、production→生产看板）
- **`platform_admin`**：首页、商家管理、权限预设、非标申请

### 6.5 核心前端交互

| 页面 | 主要交互技术 | 复杂度 |
|------|-------------|--------|
| `customer/place_order.html` | 动态规格组 DOM 操作、四级联动 select、拖拽上传、Fetch API AJAX 识别、实时价格计算 | 高 |
| `merchant/orders.html` | 复选框批量操作、双 Tab 筛选、动态表单 | 中 |
| `merchant/plate_layout_work.html` | CSS 绝对定位画布、`linear-gradient` 网格背景、算法建议应用 | 中 |
| `customer/my_orders.html` | ECharts 柱状图、Bootstrap Modal 文件预览 | 中 |
| 其他页面 | 表单提交、表格展示、状态徽章 | 低 |

### 6.6 CSS 变量体系

项目在 `base.html` 的 `:root` 中定义了一套完整的自定义 CSS 变量：

```css
:root {
  --sidebar-width: 220px;
  --sidebar-bg: #1976D2;
  --primary: #1976D2;
  --bg-main: #f0f2f5;
  --bg-card: #ffffff;
  --text-main: #1a1a1a;
  --border-color: #e8e8e8;
  --radius-sm: 4px;
  --radius-md: 6px;
  --green: #43A047;
  --red: #E53935;
  --orange: #FB8C00;
}
```

---

## 7. 核心业务流程

### 7.1 客户下单流程（单页快速下单）

```
┌─────────────┐     ┌─────────────┐     ┌─────────────────────────┐
│ 选择规格组   │────►│ 上传PDF文件  │────►│ AJAX后端处理            │
│(产品/材质/厚度)│    │(拖拽/点击)   │     │ - pdf_red_box: 红框识别  │
└─────────────┘     └─────────────┘     │ - pdf_processor: 面积计算│
                                        │ - 版类判断 / 版边计算    │
                                        └───────────┬─────────────┘
                                                    │
                    ┌───────────────────────────────┘
                    ▼
        ┌─────────────────────┐
        │ 实时显示:            │
        │ - 识别到的红框数量    │
        │ - 计算后的面积       │
        │ - 实时价格（含加急）  │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │ 填写配送/备注信息    │
        │ 选择地址            │
        └──────────┬──────────┘
                   │
                   ▼
        ┌─────────────────────┐
        │ 提交订单            │
        │ - 创建 Order + Item │
        │ - 信用额度检查       │
        │ - 自动拼版          │
        └─────────────────────┘
```

### 7.2 订单状态流转流程

```
客户提交订单
    │
    ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│待商家确认      │────►│ 设计/规格确认  │────►│ 已付款/待付款  │
│pending_confirm │     │design_confirmed│     │paid/pending   │
└───────┬───────┘     └───────┬───────┘     └───────┬───────┘
        │                     │                     │
   [商家可驳回]           [自动拼版]              [信用额度支付]
        │                     │                     │
        ▼                     ▼                     ▼
   info_error            plate_status            in_production
   (文件有误)            (拼版状态)              (安排生产)
                                │                     │
                                ▼                     ▼
                        confirmed/rejected      shipped
                        (确认/驳回拼版)          (发货)
                                                      │
                                                      ▼
                                               received
                                               (客户确认/7天自动)
                                                      │
                                                      ▼
                                                settled
                                                (对账结清)
```

### 7.3 智能拼版流程

```
待生产订单项（同材质 + 同厚度）
    │
    ├──► 按 (product, material, thickness) 分组
    │
    ├──► 展开 quantity 为多矩形
    │     优先使用红框尺寸（精确裁剪）
    │
    ├──► 尝试所有标准板材规格
    │     ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
    │     │ 610 × 914mm │  │ 762 × 1016mm│  │ 600 × 1000mm│
    │     └─────────────┘  └─────────────┘  └─────────────┘
    │
    ├──► rectpack 算法计算布局
    │     - MaxRectsBssf（默认，利用率最高）
    │     - GuillotineBssfSas
    │     - SkylineMwf
    │
    ├──► 选择最优方案（利用率最高且能放下全部）
    │
    ├──► 生成拼版效果图（Pillow + 版类视觉效果）
    │     - 画布 1600px 宽，按比例高度
    │     - 嵌入客户 PDF 实际内容
    │     - 画裁切标记 + 标注订单信息
    │
    └──► 生成矢量生产 PDF（plate_pdf.py）
          - show_pdf_page 嵌入原始文件
          - 红框精确裁剪
          - 支持 90° 旋转
```

### 7.4 对账流程

```
商家端生成对账单
    │
    ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 按月汇总    │────►│ 客户确认    │────►│ 客户标记付款 │
│ 已收货订单   │     │ (statements)│     │             │
└─────────────┘     └──────┬──────┘     └──────┬──────┘
                           │                    │
                           ▼                    ▼
                    ┌─────────────┐      ┌─────────────┐
                    │ 商家确认收款 │◄─────│ 客户付款    │
                    │ (mark_paid) │      │             │
                    └──────┬──────┘      └─────────────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ 对账结清    │
                    │ (settle)    │
                    │ 释放信用额度 │
                    └─────────────┘
```

---

## 8. 部署与运维

### 8.1 部署架构

```
┌─────────────────────────────────────────────────────────┐
│                      用户浏览器                          │
└─────────────────────────┬───────────────────────────────┘
                          │ HTTPS
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Nginx (反向代理)                                        │
│  - Server Name: www.zhibanhome.com, zhibanhome.com      │
│  - Client Max Body: 50M                                 │
│  - /static/ → staticfiles/ (缓存 30 天)                 │
│  - /media/ → media/ (缓存 7 天)                         │
│  - 其他 → proxy_pass http://127.0.0.1:8000              │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Gunicorn (WSGI 服务器)                                  │
│  - bind: 127.0.0.1:8000                                 │
│  - workers: CPU * 2 + 1                                 │
│  - worker_class: sync                                   │
│  - max_requests: 1000（防内存泄漏）                      │
│  - timeout: 120 秒                                      │
└─────────────────────────┬───────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│  Django Application                                      │
│  - WSGI 入口: magnesium_order_platform.wsgi             │
│  - 静态文件: WhiteNoise（开发）/ Nginx（生产）           │
│  - 媒体文件: 本地（开发）/ 阿里云 OSS（生产）            │
└─────────────────────────────────────────────────────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
    ┌─────────────────┐      ┌─────────────────┐
    │ PostgreSQL/MySQL │      │ 阿里云 OSS      │
    │ (生产数据库)      │      │ (文件存储)      │
    └─────────────────┘      └─────────────────┘
```

### 8.2 环境变量配置

生产环境通过 systemd 服务文件注入以下环境变量：

| 变量 | 说明 | 生产建议 |
|------|------|---------|
| `DJANGO_DEBUG` | 调试模式 | `False` |
| `DJANGO_ALLOWED_HOSTS` | 允许域名 | `www.zhibanhome.com,zhibanhome.com` |
| `DJANGO_SECRET_KEY` | 安全密钥 | 强随机字符串 |
| `DB_ENGINE` | 数据库引擎 | `postgresql` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | 数据库连接 | 配置具体参数 |
| `KUAIDI100_KEY` / `KUAIDI100_CUSTOMER` | 快递100 API | 配置真实密钥 |

### 8.3 开发环境启动

Windows 开发使用 `start_server.bat`：
- 自动查找并关闭占用 8000 端口的进程
- 显示本机 LAN IP，便于局域网联调
- 内置测试账号：
  - 平台管理员：`13800000000 / admin123`
  - 商户账号：`13800138000 / admin123`
  - 客户账号：`13900139000 / admin123`

### 8.4 运维脚本

| 脚本 | 功能 |
|------|------|
| `deploy/deploy.sh` | 首次部署 |
| `deploy/update.sh` | 代码更新 |
| `deploy/ssl_certbot.sh` | SSL 证书自动续期 |
| `manage.py auto_confirm_receipt` | 自动确认收货（建议每日 cron） |
| `manage.py generate_monthly_statements` | 月度对账单生成（建议每月 1 日 cron） |

---

## 9. 安全与风险

### 9.1 当前安全机制

| 机制 | 状态 | 说明 |
|------|------|------|
| CSRF 保护 | ✅ 已启用 | `CsrfViewMiddleware` |
| XSS 防护 | ✅ 已启用 | `SECURE_BROWSER_XSS_FILTER` |
| 点击劫持 | ✅ 已启用 | `XFrameOptionsMiddleware` (SAMEORIGIN) |
| MIME 嗅探防护 | ✅ 已启用 | `SECURE_CONTENT_TYPE_NOSNIFF` |
| 密码强度校验 | ✅ 已启用 | 4 种 Django 内置校验器 |
| 文件上传大小限制 | ✅ 已启用 | 50MB |

### 9.2 发现的风险与建议

| # | 风险 | 严重程度 | 建议 |
|---|------|---------|------|
| 1 | **OSS 密钥硬编码** | 🔴 高 | `settings.py` 中 `OSS_ACCESS_KEY_ID` 和 `OSS_ACCESS_KEY_SECRET` 为明文真实值，应迁移至环境变量 |
| 2 | **无日志配置** | 🟡 中 | `settings.py` 中未定义 `LOGGING`，生产环境需补充文件日志配置 |
| 3 | **DEBUG 默认 True** | 🟡 中 | 未设置 `DJANGO_DEBUG` 环境变量时默认开启 DEBUG，生产易误配 |
| 4 | **SQLite 为默认数据库** | 🟡 中 | 未设置 `DB_ENGINE` 时默认 SQLite，生产部署需显式切换 |
| 5 | **HTTPS 配置被注释** | 🟡 中 | `SECURE_SSL_REDIRECT`、`SESSION_COOKIE_SECURE` 等被注释，启用 HTTPS 后需取消注释 |
| 6 | **Nginx media 路径** | 🟢 低 | 开发环境由 Django 服务 media，生产由 Nginx 直接服务，配置已对应 |
| 7 | **开发脚本含绝对路径** | 🟢 低 | `start_server.bat` 硬编码了开发者本地路径 |

---

## 10. 附录

### 10.1 产品类型与版类映射

| 产品名称 | 对应版类 | 版边规则 | 计价方式 |
|---------|---------|---------|---------|
| 腐蚀版 | `etching_gold` / `etching_normal` | 单边 +5mm | 省份档位价 |
| 雕刻版 | `carving_normal` | 四周 +10mm（+20mm） | 固定单价 |
| 树脂版 | `resin` | 无版边 | 固定单价 |
| 菲林 | `film` | 无版边 | 固定单价 |
| 烫金版 | `etching_gold` | 单边 +5mm | 省份档位价 |
| 平雕版 | `carving_normal` | 四周 +10mm | 固定单价 |
| 激凸版 | `relief_strong` | 按扩缩规则 | 固定单价 |
| 压纹版 | `emboss_deboss` | 按扩缩规则 | 固定单价 |
| 激凹版 | `deboss_strong` | 按扩缩规则 | 固定单价 |
| 浮雕版 | `relief_gold` | 按扩缩规则 | 固定单价 |
| 多层次浮雕版 | `relief_gold_multi` | 按扩缩规则 | 固定单价 |

### 10.2 标准板材规格

| 规格名称 | 宽度(mm) | 高度(mm) | 适用场景 |
|---------|---------|---------|---------|
| 610×914 | 610 | 914 | 标准版 |
| 762×1016 | 762 | 1016 | 大幅面 |
| 600×1000 | 600 | 1000 | 特殊规格 |

### 10.3 订单状态完整列表

| 状态码 | 显示名称 | 说明 |
|--------|---------|------|
| `draft` | 草稿 | 未提交的临时订单 |
| `pending_confirm` | 待商家确认 | 客户已提交，等待商家审核 |
| `info_error` | 信息有误 | 商家驳回，需客户修改 |
| `design_confirmed` | 设计已确认 | 商家审核通过，规格/文件确认 |
| `pending_payment` | 待付款 | 信用额度不足，需手动付款 |
| `paid` | 已付款 | 信用额度支付成功 |
| `in_production` | 生产中 | 商家已安排工厂生产 |
| `shipped` | 已发货 | 已填物流单号发货 |
| `received` | 已收货 | 客户确认或自动确认 |
| `cancelled` | 已取消 | 客户或商家取消 |

### 10.4 关键配置文件清单

| 文件路径 | 用途 |
|---------|------|
| `magnesium_order_platform/settings.py` | Django 全局配置 |
| `magnesium_order_platform/urls.py` | 根路由配置 |
| `deploy/nginx.conf` | Nginx 反向代理配置 |
| `deploy/gunicorn.conf.py` | Gunicorn WSGI 配置 |
| `deploy/magnesium.service` | systemd 服务定义 |
| `requirements.txt` | Python 依赖清单 |
| `start_server.bat` | Windows 开发启动 |

---

> **文档结束**  
> 本架构文档基于对项目代码的静态分析生成，描述了截至 2026-06-03 的系统架构全貌。
