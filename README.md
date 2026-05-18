# 闪电制版下单系统 (第一阶段)

## 项目简介
基于 Django + Bootstrap 5 开发的印刷制版行业 B2B 下单生产平台。

## 技术栈
- **后端**: Python 3.8+, Django 4.2 LTS
- **数据库**: SQLite (开发) / PostgreSQL (生产切换)
- **前端**: HTML/CSS/JS + Bootstrap 5
- **PDF处理**: PyMuPDF (fitz)
- **图片处理**: Pillow

## 快速启动

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 数据库迁移
```bash
python manage.py migrate
```

### 3. 初始化测试数据
```bash
python init_data.py
```

### 4. 启动开发服务器
```bash
python manage.py runserver
```

访问 http://127.0.0.1:8000/

## 测试账号
| 角色 | 手机号 | 密码 |
|------|--------|------|
| 总平台管理员 | 13800000000 | admin123 |
| 商家管理员 | 13800138000 | admin123 |
| 终端用户 | 13900139000 | admin123 |

## 切换到 PostgreSQL
修改 `magnesium_order_platform/settings.py` 中的 DATABASES 配置：
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'magnesium_order_db',
        'USER': 'db_user',
        'PASSWORD': 'db_password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

## 核心功能模块
- **终端用户平台**: 注册/登录、下单（多步骤）、订单管理、信用额度支付
- **商户平台**: 会员审核、工厂管理、商品规格、订单流转、拼版工具、子账号权限
- **总平台**: 商家审核、权限预设、非标规格审批

## 项目结构
```
magnesium_order_platform/
├── apps/
│   ├── accounts/          # 用户认证与角色
│   ├── orders/            # 订单核心模型
│   ├── products/          # 商品规格
│   ├── customer_platform/ # 终端用户平台
│   ├── merchant_platform/ # 商户平台
│   ├── admin_platform/    # 总平台
│   └── common/            # 通用组件
├── templates/             # 全局模板
├── static/                # 静态文件
├── media/                 # 上传文件
├── utils/                 # 工具函数
└── manage.py
```
