# 镁印制版下单系统 — 拼版功能技术栈与嵌入对接指南

> 本文档供"另起项目单独开发拼版功能、后续嵌入本系统"时参考。
> 涵盖原系统技术栈、拼版核心架构、数据契约、嵌入方案与关键注意事项。

---

## 一、整体技术栈

| 层级 | 技术 | 版本/说明 |
|------|------|-----------|
| **后端语言** | Python | 3.8+ |
| **后端框架** | Django | 4.2 LTS |
| **前端渲染** | Django Template（服务端渲染） | **无 React/Vue/Angular 等 SPA 框架** |
| **UI 框架** | Bootstrap 5.3 | CDN 引入 |
| **图标库** | Bootstrap Icons | CDN 引入 |
| **数据库** | SQLite（开发）/ PostgreSQL 或 MySQL（生产） | 通过环境变量 `DB_ENGINE` 切换 |
| **部署方式** | Gunicorn + Nginx | 宝塔面板部署友好 |
| **会话机制** | Django Session + Cookie | 标准 Django 认证体系 |

### 前后端交互方式
- 传统**多页应用（MPA）**，非前后端分离。
- 页面跳转靠后端 `render(request, template.html, context)`。
- 少量异步操作用原生 `fetch` POST JSON，必须携带 `X-CSRFToken`。
- **无 RESTful API（无 DRF）、无 GraphQL、无 WebSocket。**

---

## 二、拼版功能核心架构

拼版功能完全由 **Python 后端** 驱动，前端仅负责：
1. 可视化展示拼版结果（CSS 绝对定位模拟矩形）
2. 简单的拖拽微调（可选）
3. 确认/驳回/保存操作（表单 POST）

### 2.1 核心算法文件（Python）

| 文件路径 | 职责 |
|----------|------|
| `utils/plate_layout.py` | 单订单拼版算法（Shelf / MaxRects / Guillotine / Skyline） |
| `utils/plate_batch.py` | **跨订单拼版**全流程：分组 → 拼版 → 生成效果图 PNG + 生产 PDF |
| `utils/plate_pdf.py` | 生成**矢量生产 PDF**（PyMuPDF 将客户原始文件以 Form XObject 嵌入，绝不做位图化） |
| `utils/plate_type_rules.py` | 版类规则、板材规格 `PLATE_SPECS`、间距规则 `SPACING_RULES` |
| `utils/pdf_red_box.py` | PDF 红框识别（自动提取客户文件中的红色裁切框尺寸） |
| `utils/rectpack/` | **内嵌**的矩形打包算法库（无需 pip 安装，纯 Python） |
| `utils/plate_preview_effects.py` | 拼版效果图上的版类视觉效果（腐蚀/雕刻/树脂/菲林等预览样式） |

### 2.2 关键板材规格（当前配置）

```python
PLATE_SPECS = [
    {'name': '610×914mm',  'width': 610,  'height': 914},
    {'name': '762×1016mm', 'width': 762,  'height': 1016},
    {'name': '600×1000mm', 'width': 600,  'height': 1000},
]
```

### 2.3 拼版间距规则

- **同厚度同材质**：按厚度查表（1.5/2.0mm → 10mm，3.0/4.0/6.0/6.35mm → 15mm）
- **不同厚度**：20mm
- **不同材质**：20mm

---

## 三、关键数据模型（Django ORM）

### 3.1 PlateBatch（跨订单拼版批次）

```python
class PlateBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    merchant = ForeignKey(Merchant)          # 所属商家
    factory = ForeignKey(Factory, null=True) # 生产工厂

    # 分组维度：只有 同产品 + 同材质 + 同厚度 才能拼到一张版
    product_name = models.CharField(max_length=50)
    material = models.CharField(max_length=50)
    thickness = models.CharField(max_length=20)

    # 板材规格
    plate_spec_name = models.CharField(max_length=50)
    plate_width = models.FloatField(default=0)
    plate_height = models.FloatField(default=0)

    # 核心数据
    layout_data = models.TextField(default='', blank=True)  # JSON 字符串
    layout_image = models.ImageField(upload_to='plate_layouts/%Y%m/')
    production_pdf = models.FileField(upload_to='plate_layouts/%Y%m/')
    usage_rate = models.FloatField(blank=True, null=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ('auto_generated', '系统自动生成'),
            ('confirmed', '已确认'),
            ('rejected', '已驳回'),
            ('in_production', '生产中'),
        ],
        default='auto_generated'
    )
```

### 3.2 PlateBatchItem（批次中的每个订单项）

```python
class PlateBatchItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    plate_batch = ForeignKey(PlateBatch, related_name='items')
    order = ForeignKey(Order)
    order_item = ForeignKey(OrderItem)

    x = models.FloatField('X坐标(mm)', default=0)
    y = models.FloatField('Y坐标(mm)', default=0)
    width = models.FloatField('放置宽度(mm)', default=0)
    height = models.FloatField('放置高度(mm)', default=0)
    rotation = models.IntegerField('旋转角度', default=0, help_text='0或90')
```

### 3.3 PlateLayout（单订单拼版建议，兼容旧数据）

```python
class PlateLayout(models.Model):
    order = models.OneToOneField(Order, related_name='plate_layout')
    layout_data = models.TextField(default='', blank=True)
    layout_file = models.FileField(upload_to='plate_layouts/%Y%m/')
    material_usage_rate = models.FloatField(blank=True, null=True)
    designer = ForeignKey(User, null=True)
    designer_note = models.TextField(blank=True)
```

### 3.4 OrderItem（订单明细，拼版的数据源）

```python
class OrderItem(models.Model):
    order = ForeignKey(Order, related_name='items')
    product_name = models.CharField(...)   # 产品类型
    material = models.CharField(...)       # 材质（镁/铜/锌/不锈钢/树脂）
    thickness = models.CharField(...)      # 厚度
    length_mm = models.FloatField()        # 长（mm）
    width_mm = models.FloatField()         # 宽（mm）
    quantity = models.PositiveIntegerField()
    file = models.FileField(...)           # 客户上传的 PDF 文件
    red_box_data = models.TextField(...)   # PDF 红框识别结果（JSON）
    plate_type = models.CharField(...)     # 版类（烫金版/压纹版/激凸版等）
    plate_batch = ForeignKey(PlateBatch, null=True)  # 所属拼版批次
```

---

## 四、核心数据契约：`layout_data` JSON 格式

无论你用任何技术重写拼版功能，**只要输出符合以下格式的 JSON 并写入 `PlateBatch.layout_data`**，原系统的以下模块都能直接复用，无需修改：

- 拼版效果图渲染（前端画布 CSS 定位）
- 生产 PDF 生成（`utils/plate_pdf.py`）
- 拼版详情页展示（`templates/merchant/plate_batch_detail.html`）

### 4.1 `layout_data` 标准格式

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
    },
    {
      "id": "order-item-uuid_1",
      "x": 130,
      "y": 0,
      "width": 100,
      "height": 60,
      "rotation": 90,
      "label": "SN20250002",
      "order_sn": "SN20250002",
      "customer_phone": "13900139000"
    }
  ]
}
```

### 4.2 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `plate_width` | int/float | 板材宽度（mm） |
| `plate_height` | int/float | 板材高度（mm） |
| `plate_spec_name` | string | 板材规格名称（如 `"610×914mm"`） |
| `placed_count` | int | 实际放置的矩形数量 |
| `usage_rate` | float | 材料利用率（%） |
| `algorithm` | string | 使用的算法：`maxrects` / `guillotine` / `skyline` / `shelf` |
| `rectangles` | array | 每个订单项在大版上的位置和尺寸 |
| `rectangles[].id` | string | **必须唯一**，建议格式 `"{order_item.id}_{副本序号}"` |
| `rectangles[].x` | float | 矩形左上角 X 坐标（mm），原点在板材左上角 |
| `rectangles[].y` | float | 矩形左上角 Y 坐标（mm），原点在板材左上角 |
| `rectangles[].width` | float | 矩形原始宽度（mm，不含间距） |
| `rectangles[].height` | float | 矩形原始高度（mm，不含间距） |
| `rectangles[].rotation` | int | 旋转角度：`0` 或 `90`（180/270 目前未使用） |
| `rectangles[].label` | string | 显示标签（通常为订单号） |
| `rectangles[].order_sn` | string | 订单编号 |
| `rectangles[].customer_phone` | string | 客户手机号 |

### 4.3 坐标系约定（重要）

- **原点在板材左上角**，X 向右，Y 向下。
- 生产 PDF 生成时会自动转换：PDF 坐标系原点在左下角，Y 向上。
- 拼版时传入算法库的矩形尺寸是 **原始尺寸 + spacing_mm**（算法负责排布），但 `layout_data` 中存储的是 **原始尺寸**（不含间距）。

---

## 五、嵌入对接方案

### 方案 A：独立 Python 微服务 / 包（推荐，成本最低）

**适用场景**：你想优化拼版算法或交互体验，但希望复用原系统的数据层和文件存储。

**做法**：
1. 将 `utils/plate_layout.py`、`utils/plate_batch.py` 等核心算法抽成独立 Python 包/微服务。
2. 通过 HTTP API 或消息队列接收订单数据，返回 `layout_data` JSON。
3. 原系统调用你的服务后将 JSON 写入 `PlateBatch.layout_data`。

**注意**：
- 原系统依赖 `settings.MEDIA_ROOT` 读取客户 PDF 文件路径。
- 生产 PDF 生成强依赖 PyMuPDF 的 `show_pdf_page()` 矢量嵌入能力，如果替换为其他方案，必须保证矢量精度。

### 方案 B：iframe 嵌入独立前端编辑器

**适用场景**：你想做一个交互式拼版编辑器（React/Vue + Canvas/SVG/WebGL）。

**做法**：
1. 独立部署你的前端编辑器（如 `https://plate-editor.yourdomain.com`）。
2. 在原系统的 `templates/merchant/plate_batch_detail.html` 中插入 `<iframe src="你的编辑器URL?batch_id=xxx&token=xxx">`。
3. 编辑器通过 URL 参数或 postMessage 获取初始 `layout_data`。
4. 用户调整后在 iframe 内向原系统 POST JSON 到 `/merchant/plate-batches/{batch_id}/update-layout/` 保存。

**注意**：
- 必须处理 **Django CSRF Token**：iframe 内发起的 POST 请求需携带 `X-CSRFToken`。
- 必须处理 **Session 共享**：iframe 与原系统需同域，或 SSO 方案，否则请求会被 Django 的 `@login_required` 拦截。

### 方案 C：完全独立系统 + 数据库/文件共享

**适用场景**：你用完全不同的技术栈（如 Node.js / Java / Go）重写拼版全流程。

**必须对接的数据**：

| 数据 | 来源 | 方式 |
|------|------|------|
| 订单数据 | `OrderItem` | 直接读原数据库，或原系统提供数据同步/接口 |
| 客户 PDF 文件 | `MEDIA_ROOT/order_files/` | 文件系统共享，或对象存储（OSS）共享 |
| 拼版结果 | `PlateBatch.layout_data` | 必须严格匹配第 4 节的 JSON 格式 |
| 效果图 | `plate_layouts/` | 生成 PNG 后保存到 `MEDIA_ROOT/plate_layouts/` |
| 生产 PDF | `plate_layouts/` | 生成 PDF 后保存到 `MEDIA_ROOT/plate_layouts/` |

**风险点**：
- 生产 PDF 的矢量嵌入逻辑（`utils/plate_pdf.py`）非常专业，用其他语言/库重写时极易出现位图化、精度丢失、字体缺失等问题。
- 建议保留 `utils/plate_pdf.py` 的调用逻辑，只替换拼版算法和交互层。

---

## 六、关键依赖清单

```txt
Django>=4.2,<5.0
psycopg2-binary>=2.9          # PostgreSQL（生产）
PyMySQL>=1.1                  # MySQL（宝塔面板默认）
PyMuPDF>=1.24                 # PDF处理（红框识别、矢量嵌入）
Pillow>=10.0                  # 拼版效果图生成
matplotlib>=3.7               # 报表/图表
openpyxl>=3.1                 # Excel 导出
requests>=2.31                # HTTP 请求
gunicorn>=21.0                # WSGI 服务器
django-storages>=1.14         # 对象存储（可选）
oss2>=2.18                    # 阿里云 OSS（可选）
```

**特别说明**：
- `rectpack` **不是 pip 包**，而是内嵌在 `utils/rectpack/` 下的纯 Python 库。
- 如果另起项目需要同等算法能力，可以直接拷贝 `utils/rectpack/` 目录使用，或用 pip 安装 `rectpack` 包（注意 API 略有差异）。

---

## 七、关键 URL 路由（商户端拼版相关）

```python
# apps/merchant_platform/urls.py

path('plate-batches/', views.plate_batch_list, name='plate_batch_list')
path('plate-batches/generate/', views.plate_batch_generate, name='plate_batch_generate')
path('plate-batches/<uuid:batch_id>/', views.plate_batch_detail, name='plate_batch_detail')
path('plate-batches/<uuid:batch_id>/confirm/', views.plate_batch_confirm, name='plate_batch_confirm')
path('plate-batches/<uuid:batch_id>/reject/', views.plate_batch_reject, name='plate_batch_reject')
path('plate-batches/<uuid:batch_id>/update-layout/', views.plate_batch_update_layout, name='plate_batch_update_layout')

path('plate-layout/', views.plate_layout_orders, name='plate_layout_orders')
path('plate-layout/<uuid:order_id>/work/', views.plate_layout_work, name='plate_layout_work')
```

---

## 八、建议与注意事项

### 8.1 强烈建议

1. **继续用 Python**：原系统的拼版算法与 `PyMuPDF` / `Pillow` / `rectpack` 深度绑定，用其他语言重写成本极高。
2. **优先优化交互层**：如果核心诉求是"拼版体验不好"，建议保留后端算法，只把前端画布从"CSS div 拼接"升级为"Canvas/SVG 交互式编辑器"。
3. **以 `layout_data` JSON 为契约**：无论你改哪一层，只要保证输出格式一致，原系统的其他模块无需改动。

### 8.2 特别注意

| 注意点 | 说明 |
|--------|------|
| **红框识别** | 拼版尺寸优先使用 `red_box_data`（PDF红框），但会做合理性校验（面积不超过用户填写面积的4倍，尺寸不超过 1100mm），异常时回退到用户填写尺寸。 |
| **版类识别** | 拼版前会先调用 `get_plate_type_by_product()` 自动识别版类（烫金版/压纹版/激凸版等），并写入 `OrderItem.plate_type`。版类影响效果图的视觉样式。 |
| **矢量嵌入** | 生产 PDF 必须保持矢量嵌入，**绝对不能将客户 PDF 位图化**，否则印刷精度会严重下降。 |
| **CSRF 保护** | 所有 POST 请求（包括 AJAX）都必须携带有效的 CSRF Token。 |
| **权限体系** | 拼版功能仅对 `merchant` 角色开放，受 `@merchant_required` 装饰器保护。 |

---

## 九、文档信息

- **针对系统**：镁印制版下单系统（magnesium_order_platform）
- **生成时间**：2026-05-28
- **适用范围**：独立开发拼版功能模块、后续嵌入原系统的技术参考
