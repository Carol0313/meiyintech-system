# 镁印制版下单系统 — 全面审查报告

> 审查日期：2026-06-15  
> 项目路径：`镁印制版下单系统/`  
> 生产环境：www.zhibanhome.com / 47.100.212.79

---

## 目录

1. [项目概览](#一项目概览)
2. [优势总结](#二优势总结)
3. [问题清单与优先级](#三问题清单与优先级)
4. [严重问题详情 P0](#四严重问题详情-p0)
5. [高优先级问题 P1](#五高优先级问题-p1)
6. [中优先级问题 P2](#六中优先级问题-p2)
7. [低优先级问题 P3](#七低优先级问题-p3)
8. [安全审查摘要](#八安全审查摘要)
9. [功能完成度](#九功能完成度)
10. [架构说明](#十架构说明)
11. [修复路线图](#十一修复路线图)
12. [总体评分](#十二总体评分)

---

## 一、项目概览

| 维度 | 现状 |
|------|------|
| **定位** | B2B 制版 SaaS：客户下单 → 商户审核/拼版 → 工厂生产 → 对账结算 |
| **技术栈** | Django 4.2、PostgreSQL（生产）、Bootstrap 模板、Gunicorn + Nginx、阿里云 OSS |
| **架构** | 经典 Django 单体，7 个 app，逻辑集中在两个超大 view 文件 |
| **多租户** | 共享库 + `Merchant` FK 隔离，靠视图层查询约束，无 DB 级 RLS |
| **生产状态** | 已上线，HTTPS、OSS、systemd 均已配置 |

### Django Apps

| App | 职责 |
|-----|------|
| `accounts` | 用户认证、商户、客户档案、角色 |
| `orders` | 订单、明细、拼版批次、对账单、投诉（仅模型，无视图） |
| `products` | 商品规格、非标规格申请 |
| `customer_platform` | 客户端视图（~1,665 行） |
| `merchant_platform` | 商户端视图（~3,634 行） |
| `admin_platform` | 平台管理端 |
| `common` | 模板上下文、标签 |

### 角色体系

- `platform_admin` — 平台管理员
- `merchant_admin` — 商户管理员
- `merchant_staff` — 商户员工
- `customer` — 终端客户（含子账号）

---

## 二、优势总结

1. **生产配置 fail-closed**：`SECRET_KEY`、`ALLOWED_HOSTS` 在生产环境有强校验；`DJANGO_USE_HTTPS` 可切换 HTTP/HTTPS cookie 策略。
2. **商户数据隔离较一致**：商户端普遍 `get_merchant()` + `merchant=merchant` 过滤；客户下载文件有归属校验。
3. **业务域模型较完整**：订单、明细、拼版批次、对账单、投诉、SLA、工厂看板等模型齐全，迁移活跃（orders 29 个 migration）。
4. **PDF/OSS 基础设施**：PyMuPDF 处理、OSS 签名 URL、临时文件下载、预览图生成等链路已打通。
5. **部署文档与脚本**：`deploy/SOP_代码发布.md`、`update.sh`、Gunicorn systemd 配置较规范。
6. **产品名兼容**：`utils/product_labels.py` 可将旧编码显示为中文（需部署生效）。

---

## 三、问题清单与优先级

### 优先级定义

| 级别 | 含义 | 建议时间 |
|------|------|----------|
| **P0** | 阻塞核心功能或存在严重安全风险，立即修复 | 1–3 天 |
| **P1** | 影响业务正确性或存在较高安全风险 | 1–2 周 |
| **P2** | 技术债、可维护性、边界场景 | 2–4 周 |
| **P3** | 优化项、文档、低影响问题 | 按需 |

### 优先级总表

| ID | 优先级 | 类别 | 问题 | 位置 |
|----|--------|------|------|------|
| P0-1 | **P0** | 功能 | `create_plate_batch` 使用错误模型字段，拼版不可用 | `merchant_platform/views.py` ~3449 |
| P0-2 | **P0** | 安全 | 忘记密码无 OTP，知道手机号即可改密 | `accounts/views.py:138` |
| P0-3 | **P0** | 安全 | PDF API 路径 IDOR，可读取他人订单文件 | `customer_platform/views.py` ~1439 |
| P0-4 | **P0** | 安全 | 商户 RBAC 权限未在视图中执行 | `merchant_platform/views.py` 全局 |
| P1-1 | **P1** | 功能 | 红框坐标三套格式混用（像素/mm/PDF点） | `pdf_red_box.py`, `plate_batch.py`, `plate_pdf.py` |
| P1-2 | **P1** | 功能 | `layout_data` JSON 结构与详情页/生产 PDF 不一致 | `views.py` + `plate_pdf.py` |
| P1-3 | **P1** | 功能 | 双拼版体系并存（PlateLayout vs PlateBatch） | 多处 |
| P1-4 | **P1** | 功能 | 信用额度修复命令只统计 `paid` 状态 | `fix_credit_used.py` |
| P1-5 | **P1** | 功能 | 旧 product_name 无定价/版类映射 | `product_labels.py` vs `pricing_tiers.py` |
| P1-6 | **P1** | 安全 | SMS OTP 使用 LocMemCache，多 worker 失效 | `settings.py`, `sms.py` |
| P1-7 | **P1** | 安全 | Nginx 公开 `/media/` 目录 | `deploy/nginx.conf` |
| P1-8 | **P1** | 运维 | Gunicorn 以 root 用户运行 | `deploy/magnesium.service` |
| P1-9 | **P1** | 安全 | `.env` 含真实密钥，需确认是否泄露并轮换 | `.env` |
| P2-1 | **P2** | 架构 | `merchant_platform/views.py` 3634 行，高耦合 | `views.py` |
| P2-2 | **P2** | 架构 | `customer_platform/views.py` 1665 行 | `views.py` |
| P2-3 | **P2** | 功能 | `Order.transition_status` 无状态机校验 | `orders/models.py:193` |
| P2-4 | **P2** | 功能 | 批量下单信用支付跳过商户审核 | `customer_platform/views.py` ~445 |
| P2-5 | **P2** | 安全 | 上传文件仅校验扩展名 | 多处 upload 视图 |
| P2-6 | **P2** | 安全 | 模板 `\|safe` 存在 XSS 风险 | `order_detail.html` 等 |
| P2-7 | **P2** | 功能 | PDF 预检未接入下单/审核流程 | `pdf_preflight.py` |
| P2-8 | **P2** | 依赖 | `python-dotenv` 未写入 requirements.txt | `requirements.txt` |
| P2-9 | **P2** | 测试 | 零自动化测试 | 全部 `tests.py` |
| P3-1 | **P3** | 功能 | `pay_with_credit()` 定义但未使用 | `orders/models.py:207` |
| P3-2 | **P3** | 安全 | 登录无速率限制/CAPTCHA | `accounts/views.py` |
| P3-3 | **P3** | 安全 | GET 方式可触发登出 | `accounts/views.py:55` |
| P3-4 | **P3** | 文档 | 文档/脚本硬编码测试密码 | README, deploy 脚本 |
| P3-5 | **P3** | 配置 | Session 7 天无浏览器关闭失效 | `settings.py:233` |
| P3-6 | **P3** | 配置 | HSTS 未启用 | `settings.py` |

---

## 四、严重问题详情（P0）

### P0-1：拼版功能核心路径不可用

**文件：** `apps/merchant_platform/views.py` ~3378–3517

**问题：** `create_plate_batch()` 使用了不存在的模型字段，且 import 错误。

```python
# 错误写法
PlateBatch.objects.create(
    algorithm=algorithm,        # ❌ 模型无此字段
    plate_spec=...,             # ❌ 应为 plate_spec_name
)
PlateBatchItem.objects.create(
    batch=batch,                # ❌ 应为 plate_batch
    # ❌ 缺少 x/y/width/height
)
# ❌ get_spacing_mm、generate_plate_production_pdf 从 plate_batch 导入（未导出）
```

**正确参考：** `utils/plate_batch.py` → `auto_generate_plate_batches()`

**影响：** 「待拼版 → 开始拼版 → 确认」主流程无法正常工作。

**修复建议：** 对齐 `auto_generate_plate_batches` 的字段、import、layout JSON、FileField 保存方式。

---

### P0-2：忘记密码无身份验证

**文件：** `apps/accounts/views.py:138–151`

**问题：** 只需手机号 + 新密码即可重置，无短信 OTP、无邮件 token。

**风险：** 账号可被接管。

**修复建议：** 复用 `verify_sms_code`，重置前必须验证短信验证码。

---

### P0-3：PDF 文件路径 IDOR（越权访问）

**文件：** `apps/customer_platform/views.py` ~1439, ~1536, ~1628

**问题：** `api_pdf_red_boxes`、`api_preview_effect`、`api_preview_3d` 接受任意 `file_path`，未校验是否属于当前用户。

**风险：** 任意已登录客户可读取他人订单 PDF。

**修复建议：** 校验 `file_path.startswith(f"order_files/{request.user.id}/")` 或通过 DB 查 `OrderItem` 归属。

---

### P0-4：商户 RBAC 未真正生效

**文件：** `apps/merchant_platform/views.py`（全局）

**问题：** `Role.has_permission()` 已定义，但视图层几乎不调用。员工角色 UI 存在，实际任意员工可访问审核、财务、下载等。

**修复建议：** 添加 `@staff_permission('order_audit')` 等装饰器，在关键视图强制执行。

---

## 五、高优先级问题（P1）

### 业务逻辑

| ID | 问题 | 说明 |
|----|------|------|
| P1-1 | 红框坐标三套格式 | PDF 点、mm、Canvas 像素混存于 `red_box_data`，计价/拼版/生产 PDF 各用不同字段 |
| P1-2 | layout_data 结构不一致 | `create_plate_batch` 存的 JSON 与详情页、生产 PDF 期望格式不匹配 |
| P1-3 | 双拼版体系并存 | 旧 `PlateLayout`（单订单）与新 `PlateBatch`（跨订单）并行 |
| P1-4 | 信用额度统计错误 | `fix_credit_used` 只统计 `status='paid'`，忽略生产中/已发货订单 |
| P1-5 | 旧 product_name 无定价 | `carving_flat_gold` 等仅显示中文，定价/版类规则返回 0 |

### 安全与运维

| ID | 问题 | 说明 |
|----|------|------|
| P1-6 | SMS LocMemCache | Gunicorn 多 worker 下验证码跨进程失效，限流无效 → 需 Redis |
| P1-7 | Nginx 公开 media | 本地/OSS 回退文件可能被直接访问 |
| P1-8 | Gunicorn root 运行 | 进程被攻破即整机沦陷 |
| P1-9 | 密钥暴露风险 | `.env` 含 OSS/DB/SECRET_KEY，若曾泄露需轮换 |

---

## 六、中优先级问题（P2）

### 代码质量

- `merchant_platform/views.py`：**3,634 行**，几乎所有商户 HTTP 逻辑
- `customer_platform/views.py`：**1,665 行**
- `orders/views.py`、`products/views.py`：空 scaffold（3 行）
- `Order.transition_status()` 无状态机校验
- `Order.pay_with_credit()` 定义但未使用，支付逻辑在 views 中重复

### PDF / 拼版细节

- `pdf_red_box.py`：黑色描边可能被误识别；厚度 ≥3mm 版边 10mm 与前端预估 5mm 不一致
- `pdf_preflight.py`：转曲/字体检测不完整，未接入下单/审核流程
- `calculate_plate_layout()` 静默丢弃放不下的矩形
- 模板中 `report_html|safe`、`layout_data|safe` 存在 XSS 风险

### 测试与依赖

- **零自动化测试**
- `python-dotenv` 在 `manage.py` 使用但未写入 `requirements.txt`

---

## 七、低优先级问题（P3）

| ID | 问题 |
|----|------|
| P3-1 | `pay_with_credit()` 死代码 |
| P3-2 | 登录无速率限制 / CAPTCHA |
| P3-3 | GET 方式可触发登出（CSRF logout） |
| P3-4 | 文档/脚本硬编码 `admin123` 等测试密码 |
| P3-5 | Session 7 天，无浏览器关闭失效 |
| P3-6 | HSTS 未启用 |

---

## 八、安全审查摘要

| 等级 | 数量 | 代表项 |
|------|------|--------|
| **Critical** | 4 | 无验证改密、PDF IDOR、RBAC 未执行、密钥暴露风险 |
| **High** | 8 | 公开 media、SMS 缓存、Gunicorn root、硬编码凭据 |
| **Medium** | 12 | 登录无速率限制、上传仅扩展名校验、XSS、7 天 session |
| **Low** | 6 | GET 登出、debug 模板处理器等 |

### 已有防护

- CSRF 中间件
- 生产 SECRET_KEY / ALLOWED_HOSTS 校验
- 租户 scoped 文件下载（正确使用的端点）
- OSS 签名 URL
- PDF 页数/像素上限

---

## 九、功能完成度

| 模块 | 完成度 | 备注 |
|------|--------|------|
| 登录/注册/角色分流 | ✅ 90% | 忘记密码有严重漏洞 |
| 客户下单 + PDF 预览 | ✅ 85% | 红框坐标、多框计价仍有边界问题 |
| 商户订单审核 | ✅ 80% | RBAC 未落地 |
| **跨订单拼版** | ❌ 40% | `create_plate_batch` 损坏 |
| 生产看板 / SLA | ✅ 75% | 基本可用 |
| 对账 / 信用额度 | ⚠️ 70% | 统计与修复命令有 bug |
| 3D 预览 / 版类效果 | ✅ 80% | 受 IDOR 影响面扩大 |
| 数据分析 | ✅ 75% | 旧 product_name 统计标签不准 |
| 自动化测试 | ❌ 0% | 无 |

---

## 十、架构说明

```
客户端
├── /customer/  → customer_platform/views.py (~1665行)
├── /merchant/  → merchant_platform/views.py (~3634行)
├── /platform/  → admin_platform/views.py
└── /accounts/  → accounts/views.py

领域模型
├── orders/     → Order, OrderItem, PlateBatch, Statement...
├── products/   → ProductSpec
└── accounts/   → User, Merchant, Role

工具层
├── pdf_red_box.py, pdf_processor.py, pdf_preflight.py
├── plate_batch.py, plate_layout.py, plate_pdf.py
├── oss_storage.py, sms.py, pricing_tiers.py
└── product_labels.py
```

**主要瓶颈：** 业务逻辑在 views 与 utils 间重复、拼版双轨、坐标格式不统一。

---

## 十一、修复路线图

### 第一阶段（1–3 天）— 止血 P0

| 顺序 | 任务 | 优先级 |
|------|------|--------|
| 1 | 修复 `create_plate_batch`，使拼版可用 | P0-1 |
| 2 | 忘记密码加 SMS OTP | P0-2 |
| 3 | PDF API 路径归属校验 | P0-3 |
| 4 | 部署 `product_labels` 中文名修复 | 已完成代码，待部署 |
| 5 | 确认并轮换泄露密钥 | P1-9 |

### 第二阶段（1–2 周）— 稳定 P1

| 顺序 | 任务 | 优先级 |
|------|------|--------|
| 6 | 引入 Redis 做 SMS/限流缓存 | P1-6 |
| 7 | RBAC 装饰器 + 关键视图强制执行 | P0-4 |
| 8 | 统一 red_box_data 格式 | P1-1 |
| 9 | Gunicorn 改为非 root 用户 | P1-8 |
| 10 | Nginx `/media/` 鉴权或仅 OSS 签名 | P1-7 |
| 11 | 修复信用额度统计 | P1-4 |

### 第三阶段（2–4 周）— 重构 P2

| 顺序 | 任务 | 优先级 |
|------|------|--------|
| 12 | 拆分 merchant_platform/views.py | P2-1 |
| 13 | 合并 PlateLayout → PlateBatch | P1-3 |
| 14 | Order 状态机校验 | P2-3 |
| 15 | 核心路径单元测试 | P2-9 |
| 16 | 旧 product_name 数据迁移 + 定价映射 | P1-5 |

---

## 十二、总体评分

| 维度 | 评分 | 说明 |
|------|------|------|
| **业务完整度** | 7/10 | 下单→生产→对账链路齐全，拼版是明显短板 |
| **代码可维护性** | 4/10 | 巨型 view、双拼版体系、零测试 |
| **安全性** | 5/10 | 生产 settings 较好，auth/RBAC/IDOR 有硬伤 |
| **运维成熟度** | 7/10 | 部署文档、systemd、OSS 已就绪 |
| **生产可用性** | 6/10 | 下单/审核/看板可用；手动拼版不可用 |

### 结论

业务功能丰富、已具备生产部署能力，但在**拼版核心路径、安全关键项、代码结构**上存在明显技术债。建议按 P0 → P1 → P2 顺序推进，优先修复拼版与账号安全。

---

## 附录：推荐立即执行的 Top 5

1. **P0-1** — 修复 `create_plate_batch`（用户反馈「拼版不能做」的直接原因）
2. **P0-2** — 忘记密码加 OTP（账号安全）
3. **P0-3** — PDF IDOR 修复（客户文件泄露）
4. **P0-4** — RBAC 强制执行（员工权限）
5. **P1-6** — Redis 缓存（SMS 登录稳定性）

---

*本报告由代码审查自动生成，审查范围涵盖 apps/、utils/、templates/、deploy/、settings.py。*
