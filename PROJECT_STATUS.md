# 镁印制版下单系统 - 项目状态记录

> 最后更新：2026-06-22 09:15
> 此文件用于快速恢复项目上下文，每次对话开始时请将此文件内容发送给AI

---

## 一、项目基本信息

| 项目 | 内容 |
|------|------|
| 项目名称 | 镁印制版下单系统（闪电制版 / 制版家） |
| 域名 | www.zhibanhome.com ✅ 已上线 |
| 服务器IP | 47.100.212.79 |
| 技术栈 | Django 4.2, Python 3.8, Bootstrap 5.3, PostgreSQL(生产) |
| 代码仓库 | https://github.com/Carol0313/meiyintech-system (GitHub) / https://gitee.com/carol0313/zhibanhome (Gitee镜像) |
| 部署状态 | 生产阶段，HTTPS已启用；Gunicorn 127.0.0.1:8000 + PostgreSQL 13 + Nginx反向代理 + SSL证书；服务器 ECS 4核8G；OSS 100G/年 已启用；systemd 自启动已配置；SSH 端口已改为 2222，root 登录已禁用，fail2ban 已已启用 |
| 服务器配置 | 阿里云 ECS 4核8G（已升级并验证，原轻量应用服务器2GB） |

---

## 二、服务器环境

```bash
# 项目路径
cd /home/magnesium/magnesium_order_platform

# 虚拟环境
source venv/bin/activate

# 启动/重启服务
sudo systemctl restart magnesium
sudo systemctl restart nginx

# 查看服务状态
sudo systemctl status magnesium
sudo systemctl status nginx

# Nginx配置
/etc/nginx/conf.d/magnesium.conf
# 静态文件路径
/home/magnesium/magnesium_order_platform/staticfiles/
```

---

## 三、已完成功能清单（25项）

| 功能 | 完成时间 | 备注 |
|------|---------|------|
| 用户认证体系（登录/注册/权限） | 2026-05 | 手机号登录，四层角色权限 |
| 客户下单流程（单页/分步） | 2026-05 | 支持快速下单和分步下单 |
| **顺丰标快运费预估** | **2026-06-22** | **双工厂（广州/南通）自动选择，按省份分区计费，前端实时显示** |
| PDF红框智能识别 | 2026-05 | 自动检测内容框尺寸 |
| 订单状态流转与追踪 | 2026-05 | 6步进度条可视化 |
| 拼版工具（单订单/跨订单） | 2026-05 | 4种算法，版类效果预览 |
| 生产看板与工厂管理 | 2026-05 | 工厂状态、设备监控 |
| 对账单与信用额度 | 2026-05 | 月度对账、额度管理 |
| 阿里云OSS文件存储 | 2026-06-05 | 内网Endpoint配置完成；Bucket: zbhomefiles；100G/年套餐；私有Bucket，通过签名URL访问 |
| 商户端订单详情页优化 | 2026-06-05 | 移除操作面板，丰富内容 |
| 客户投诉功能 | 2026-06-05 | 客户提交投诉，支持描述+图片 |
| SSL证书申请 | 2026-06-05 | 阿里云DigiCert证书已申请并部署 |
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
| **商户端数据分析中心** | **2026-06-06** | 独立数据分析页面，8个KPI+6个图表+SLA面板 |
| **下单页PDF红框Canvas交互+版类效果预览** | **2026-06-07** | Canvas画框、点击删除、手动画框、版类效果实时切换（9种效果），支持OSS文件 |
| **效果图API支持OSS** | **2026-06-07** | `_get_pdf_local_path` 自动从阿里云OSS下载临时文件处理 |
| **多框计价修复** | **2026-06-08** | 所有产品类型统一遍历f.boxes，根据类型使用不同版边（腐蚀版5mm/其他20mm） |
| **Three.js 3D浮雕预览** | **2026-06-08** | 后端生成高度图/法线贴图，前端Three.js渲染，支持鼠标拖拽旋转和滚轮缩放 |
| **3D预览效果增强** | **2026-06-09** | 径向金色渐变、多层阴影系统、Sobel法线贴图、四灯照明系统、金属质感增强 |
| **部署文档** | **2026-06-09** | 新增 `deploy/DEPLOY_GUIDE.md` 完整部署指南 |
| **域名正式上线** | **2026-06-18** | zhibanhome.com / www.zhibanhome.com 已部署SSL，HTTPS访问正常；根路径自动跳转登录页 |
| **公安备案提交** | **2026-06-18** | 全国互联网安全管理服务平台已提交，审核中 |

---

## 四、进行中功能（0项）

暂无进行中任务。

---

## 五、待开始任务（2项）

| 任务 | 时间 | 备注 |
|------|------|------|
| 性能测试与优化 | 2026-06-16 | 并发下单、大文件上传、数据库查询优化 |
| 3D浮雕效果持续优化 | 待定 | 参考专业浮雕效果继续改进算法，优先级较低 |

---

## 六、等待审核（1项）

| 事项 | 预计时间 | 状态 |
|------|---------|------|
| 公安备案 | 2026-06-18 | 已提交，审核中；数据码有效期至2026-07-17 |

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
orders.0027_orderitem_preview_image  - OrderItem新增preview_image字段
orders.0028_order_customer_service_processed_at_and_more  - Order新增SLA时效字段
```

---

## 八、已知问题

1. **Python 3.8 弃用警告** - PyMySQL的cryptography库提示Python 3.8不再支持，不影响运行但建议后续升级
2. **GitHub推送间歇性超时** — 国内网络不稳定，需要多次重试或等待网络恢复
3. ~~域名备案审核中~~ ✅ 已通过，已上线
4. ~~DEBUG模式未关闭~~ ✅ 已关闭，`DEBUG=False`

---

## 九、环境变量

```bash
# .env文件路径
/home/magnesium/magnesium_order_platform/.env

# 关键配置
OSS_INTERNAL=true  # ECS内网访问OSS
DB_ENGINE=postgresql  # 已切换PostgreSQL
DB_NAME=magnesium_db
DB_USER=magnesium_user
DB_HOST=localhost
DB_PORT=5432
DJANGO_DEBUG=False  # 生产环境已关闭
DJANGO_USE_HTTPS=true  # HTTPS已启用
DJANGO_ALLOWED_HOSTS=127.0.0.1,47.100.212.79,www.zhibanhome.com,zhibanhome.com
CSRF_TRUSTED_ORIGINS=https://www.zhibanhome.com,https://zhibanhome.com,http://www.zhibanhome.com,http://zhibanhome.com,http://47.100.212.79
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
# IP: 47.100.212.79，端口: 2222

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

# 7. 重启Nginx
sudo nginx -s reload
# 或
sudo systemctl restart nginx

# 8. 重启Django服务（Gunicorn）
sudo systemctl restart magnesium

# 9. 确认服务状态
sudo systemctl status magnesium
sudo systemctl status nginx
sudo ss -tlnp | grep -E '80|443|8000'
```

---

## 十二、本次对话关键决策

1. **UI全面改版** — 已完成：白色侧边栏+蓝色active指示、Font Awesome 6.4图标、统计卡片左侧大图标布局
2. **产品分类重新调整** — 已完成：腐蚀版4种（凹版/凸版/镁凹树凸/双面镁激凸）+ 雕刻版5种（平雕凸/平雕凹/浮雕激凸烫凸一体/浮雕多层次激凸烫凸一体/多层次浮雕）+ 树脂版 + 菲林
3. **红框尺寸修改功能** — 已完成：商户后台可修改，支持添加/删除框，修改后自动重新计算订单金额
4. **上传文件区域2行布局** — 已完成：第一行预览图+文件名，第二行尺寸数量输入
5. **Nginx反向代理配置** — 已完成：`/etc/nginx/conf.d/magnesium.conf` 配置完成
6. **域名备案** — ✅ 已通过，2026-06-02
7. **SLA时效追踪系统** — 已完成：客服30分钟处理+工厂30分钟下载时效追踪
8. **商户端数据分析中心** — 已完成：独立数据分析页面，8个KPI+6个图表+SLA面板
9. **下单页PDF红框识别+版类效果预览** — 已完成：
   - Canvas交互式红框展示（自动识别、hover高亮、点击删除、手动画框）
   - 版类效果实时切换（根据产品类型显示2-3个相关效果）
   - 9种版类效果：普通/烫金光泽/金色平雕/激凸浮雕/压纹凹陷/激凹凹陷/金色浮雕/多层金色浮雕/菲林半透明
   - 自动识别后生成默认效果图，数据自动回填尺寸字段
10. **Three.js 3D浮雕预览** — 已完成：
    - 后端：generate_3d_preview_maps() 生成color/displacement/normal贴图
    - 后端：scipy距离变换生成圆润浮雕形状，Sobel算子生成精确法线贴图
    - 前端：Three.js场景，PlaneGeometry+displacementMap+normalMap
    - 前端：鼠标拖拽旋转、滚轮缩放、触摸支持、自动旋转
    - 灯光系统：环境光+主光+补光+轮廓光四灯照明
    - 材质参数：displacementScale 0.8, metalness 0.6, normalScale 3.0
11. **域名正式上线** — ✅ 已完成：
    - DNS解析：zhibanhome.com / www.zhibanhome.com → 47.100.212.79
    - SSL证书：阿里云DigiCert已部署，HTTPS访问正常
    - Nginx配置：80端口自动跳转443，反向代理到Gunicorn
    - 根路径重定向：/ → /accounts/login/
    - 生产环境配置：DEBUG=False，ALLOWED_HOSTS包含域名，USE_HTTPS=true
12. **公安备案** — ⏳ 已提交，审核中：
    - 主体：上海镁印科技有限公司
    - 网站：制版之家（zhibanhome.com）
    - 备案号：沪ICP备2023003293号-3
    - 数据码：b49f08c6ca9174d2995f01a4dad4b345

---

*此文件应在每次重要变更后更新*
