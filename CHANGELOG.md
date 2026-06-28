# 镁印制版下单系统 - 变更日志

> 记录系统每日的改进、修改、修复等变更
> 格式：日期 - 版本 - 变更类型 - 详细描述

---

## 变更类型说明

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 |
| `docs` | 文档更新 |
| `style` | 样式/UI调整 |
| `refactor` | 重构 |
| `perf` | 性能优化 |
| `chore` | 构建/部署/配置 |
| `data` | 数据库/数据变更 |

---

## 2026-06-28

### 1. 修复下单页 PDF 红框识别精度问题 [fix]
- **颜色阈值**：收紧红色判定（R>0.7 且 R 比 G/B 高 0.2），减少橙/褐误判；提高白色/近白色阈值，减少浅灰/淡网点误判
- **过滤优化**：文字重叠阈值从 90% 调至 85%；嵌套内边框检查扩展到全部候选框
- **单位统一**：`red_box_data` 中 `x/y/width/height` 统一为 PDF pt，`length_mm/width_mm` 为毫米；拼版代码统一读取 mm 字段
- **数量识别**：新增 "做3块"/"要3个"/"Qty:3"/"3PCS" 等口语化/英文表达匹配
- **影响文件**：`utils/pdf_red_box.py`、`utils/plate_layout.py`、`utils/plate_batch.py`、`utils/plate_pdf.py`、`apps/customer_platform/views.py`
- **数据库**：否

### 2. 修复效果图不明显与 3D 预览失败 [fix][feat]
- **前后端 key 对齐**：下单页「压纹凹陷」从 `emboss` 改为 `emboss_deboss`，不再回退成普通效果
- **效果名称修复**：`api_preview_effect` 直接根据实际效果类型返回名称，不再总是显示「普通」
- **3D OSS 读取**：`api_preview_3d` 先调用 `_get_pdf_local_path`，解决 OSS 环境下找不到 PDF 的问题
- **3D 性能**：`generate_normal_map` 改为 numpy 向量化 Sobel，替代纯 Python 双层循环
- **3D 跨域**：前端 `TextureLoader.setCrossOrigin('anonymous')`，贴图 URL 加时间戳防缓存
- **效果图清晰度**：DPI 从 72 提升到 100，最大边长从 1200 放宽到 1400
- **影响文件**：`utils/plate_preview_effects.py`、`apps/customer_platform/views.py`、`templates/customer/place_order.html`
- **数据库**：否

### 3. 修复「我的订单」预览图与下单页效果图断裂 [fix]
- **持久化**：下单页用户选中的效果图保存为 `customer_previews/{item.id}.png` 并写入 `OrderItem.preview_image`
- **优先读取**：`my_orders` / `order_detail` 优先使用 `preview_image.url`，无效果图时回退到基础 PDF 预览
- **旧订单兼容**：没有效果图的订单继续显示普通 PDF 缩略图
- **影响文件**：`apps/customer_platform/views.py`、`templates/customer/place_order.html`
- **数据库**：否

### 4. 版类效果图向 demo 风格靠拢 [style][feat]
- **灰底背景**：浮雕/压纹/激凸/烫金效果图统一改用中灰背景（`bg_gray=180`），更接近 demo 样张质感
- **光照模型重做**：`_emboss_metal` 改为距离变换 + 固定方向光照模型，左上光源产生统一立体感，避免旧版 PIL EMBOSS 的径向纹理
- **强高光/阴影**：降低环境光（`ambient=0.18`）、保留自然明暗对比、gamma 增强，使高光更亮、暗部更深
- **边缘平滑**：`_get_content_mask` 增加 0.5px 高斯模糊后阈值化，减少文字锯齿在光照模型中的高频噪声
- **影响文件**：`utils/plate_preview_effects.py`
- **数据库**：否

---

## 2026-06-13

### 1. 阿里云OSS私有Bucket签名URL [feat][security]
- **功能**：启用私有Bucket，通过签名URL安全访问OSS文件
- **影响文件**：`magnesium_order_platform/settings.py`、文件存储相关工具函数
- **安全**：避免Bucket设置为公共读，保护客户上传文件

### 2. 生产环境配置与安全加固 [chore][security]
- **start.sh**：清理硬编码密钥，改为从 `.env` 读取
- **生产环境**：补充生产环境配置说明，移除测试环境残留配置
- **影响文件**：`start.sh`、`.env`、部署相关文档

---

## 2026-06-11

### 1. 生产环境部署配置 [chore]
- **配置**：新增生产环境部署参数
- **登录**：手机号验证码登录流程适配生产环境
- **影响文件**：部署配置、`apps/common` 相关登录逻辑

---

## 2026-06-10

### 1. 投诉功能全面升级 [feat]
- **客户端**：投诉提交支持描述+图片
- **商户端**：投诉列表页+详情处理页完整实现
- **状态流转**：待处理 → 处理中 → 已处理
- **影响文件**：`apps/customer_platform/views.py`、`apps/merchant_platform/views.py`、相关模板

### 2. 客户端投诉表单精简 [fix]
- **改动**：移除投诉类型选择字段，仅保留描述和照片
- **目的**：降低客户提交成本，聚焦核心信息
- **影响文件**：客户端投诉相关模板

---

## 2026-06-09

### 1. 部署指南文档 [docs]
- **文档**：新增 `deploy/DEPLOY_GUIDE.md` 完整部署指南
- **内容**：环境准备、依赖安装、数据库配置、Nginx/Gunicorn、SSL、OSS配置

### 2. 3D浮雕预览效果增强 [feat][style]
- **效果**：径向金色渐变、多层阴影系统、Sobel法线贴图、四灯照明系统
- **材质**：metalness 0.6、displacementScale 0.8、normalScale 3.0
- **交互**：鼠标拖拽旋转、滚轮缩放、触摸支持、自动旋转
- **影响文件**：`utils/plate_preview_effects.py`、Three.js前端代码

---

## 2026-06-08

### 1. Three.js 3D浮雕预览 [feat]
- **后端**：`generate_3d_preview_maps()` 生成 color/displacement/normal 贴图
- **前端**：Three.js 渲染，支持 PlaneGeometry + displacementMap + normalMap
- **算法**：scipy 距离变换生成圆润浮雕形状，Sobel 算子生成精确法线贴图

### 2. 多框计价修复 [fix]
- **问题**：所有产品类型统一遍历 `f.boxes`，根据类型使用不同版边
- **版边**：腐蚀版 5mm / 其他 20mm
- **影响文件**：计价相关工具函数

---

## 2026-06-07

### 1. 下单页PDF红框Canvas交互+版类效果预览 [feat][style]
- **Canvas交互**：自动识别红框、hover高亮、点击删除、手动画框
- **版类效果**：根据产品类型实时切换 2-3 个相关效果
- **9种效果**：普通 / 烫金光泽 / 金色平雕 / 激凸浮雕 / 压纹凹陷 / 激凹凹陷 / 金色浮雕 / 多层金色浮雕 / 菲林半透明
- **自动回填**：识别后生成默认效果图，尺寸数据自动回填

### 2. 效果图API支持OSS [feat]
- **改动**：`_get_pdf_local_path` 自动从阿里云OSS下载临时文件处理
- **影响文件**：效果图生成相关工具函数

---

## 2026-06-06

### 7. 修复产品大类排序 [fix]
- **排序**：腐蚀版 → 雕刻版 → 树脂版 → 菲林
- **改动**：修改 `apps/customer_platform/views.py` 中 `spec_data` 排序逻辑
- **影响文件**：`apps/customer_platform/views.py`
- **数据库**：否

### 1. UI全面改版 [feat][style]
- **侧边栏**：深蓝底 → 白色底 + 蓝色active指示条
- **图标库**：Bootstrap Icons → Font Awesome 6.4（CDN引入）
- **菜单图标**：全部替换为Font Awesome图标，增加hover变色效果
- **统计卡片**：右上角小图标 → 左侧大图标(52px) + 右侧数字标签
- **按钮样式**：增加图标前缀（如 🖨️ 打印预览、📄 导出）
- **影响文件**：`templates/base.html`, `templates/common/menu.html`, 全部模板文件

### 2. 产品分类重新调整 [feat][data]
- **腐蚀版**（4种）：凹版、凸版、镁凹树凸、双面镁激凸
- **雕刻版**（5种）：平雕（凸版）、平雕（凹版）、浮雕（激凸/烫凸一体）、浮雕（多层次激凸/烫凸一体）、多层次浮雕
- **树脂版**（2种）：倒模树脂版、水洗树脂版
- **菲林**（2种）：对位菲林、UV菲林
- **数据库迁移**：`orders.0025`, `orders.0026`, `products.0007`, `products.0008`
- **价格体系**：更新 `utils/pricing_tiers.py` 中 `CARVING_PRICE_TABLE`
- **版类映射**：更新 `utils/plate_type_rules.py`
- **视觉效果**：更新 `utils/plate_preview_effects.py`

### 3. 红框尺寸修改功能 [feat]
- **功能**：商户后台可修改红框尺寸
- **支持**：添加框、删除框、修改长/宽/数量
- **自动计算**：修改后自动更新订单金额
- **影响文件**：`apps/merchant_platform/views.py`, `templates/merchant/order_detail.html`

### 4. 上传文件区域布局优化 [style]
- **第一行**：预览图(120px) + 文件名 + 删除按钮 + 内容框信息
- **第二行**：长(mm)/宽(mm)/数量 输入框（带分隔线）
- **影响文件**：`templates/customer/place_order.html`

### 5. Nginx反向代理配置 [chore]
- **配置文件**：`/etc/nginx/conf.d/magnesium.conf`
- **配置内容**：80端口 → 127.0.0.1:8000 反向代理
- **静态文件**：`/static/` → `staticfiles/`
- **媒体文件**：`/media/` → `media/`
- **上传限制**：`client_max_body_size 50M`

### 6. 商户端投诉管理验证 [docs]
- **状态**：功能已存在，验证通过
- **包含**：投诉列表页、投诉详情页、处理流程

---

## 2026-06-05

### 1. 阿里云OSS文件存储 [feat]
- **配置**：内网Endpoint
- **状态**：配置完成

### 2. 商户端订单详情页优化 [style]
- **改动**：移除操作面板，丰富内容展示

### 3. 客户投诉功能 [feat]
- **功能**：客户提交投诉，支持描述+图片

### 4. SSL证书申请 [chore]
- **工具**：Certbot
- **状态**：证书已申请

### 5. 规格组特殊要求备注 [feat]
- **功能**：每个规格组独立备注

### 6. 规格组缩放比例设置 [feat]
- **默认值**：100%（不缩放）
- **推荐值**：99.75%（补偿金属加热膨胀）
- **支持**：自定义比例

---

## 2026-05（历史功能）

| 功能 | 类型 | 说明 |
|------|------|------|
| 用户认证体系 | feat | 手机号登录，四层角色权限 |
| 客户下单流程 | feat | 单页/分步下单 |
| PDF红框智能识别 | feat | 自动检测内容框尺寸 |
| 订单状态流转与追踪 | feat | 6步进度条可视化 |
| 拼版工具 | feat | 4种算法，版类效果预览 |
| 生产看板与工厂管理 | feat | 工厂状态、设备监控 |
| 对账单与信用额度 | feat | 月度对账、额度管理 |

---

## 待开始任务

| 任务 | 预计时间 | 类型 |
|------|---------|------|
| PostgreSQL数据库迁移 | 6月10日-11日 | chore |
| Gunicorn+Nginx生产部署 | 6月12日-13日 | chore |
| 域名备案完成 | 6月8日 | chore |

---

*此文件应在每次变更后更新*
