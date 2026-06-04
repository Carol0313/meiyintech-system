"""
Django settings for magnesium_order_platform project.
"""

import os
from pathlib import Path

# PyMySQL 兼容（宝塔面板使用 MySQL 时无需安装 mysqlclient）
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# ==================== 安全设置 ====================
# 生产环境必须通过环境变量传入，严禁使用默认密钥
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-b0kloytxexei@ms7yq&zd#y08li&^x41d6rkya!!w*p@he#s@0')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

# 生产环境必须配置具体域名
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

# 允许同站点嵌入（用于PDF文件预览）
X_FRAME_OPTIONS = 'SAMEORIGIN'

# 生产环境必须配置CSRF可信来源（HTTPS部署时）
CSRF_TRUSTED_ORIGINS = os.environ.get(
    'CSRF_TRUSTED_ORIGINS',
    'http://127.0.0.1,http://localhost,http://www.zhibanhome.com,https://www.zhibanhome.com'
).split(',')

# 生产环境安全设置
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    # 使用HTTPS时取消下面注释
    # SECURE_SSL_REDIRECT = True
    # SESSION_COOKIE_SECURE = True
    # CSRF_COOKIE_SECURE = True

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Local apps
    'apps.accounts',
    'apps.orders',
    'apps.products',
    'apps.customer_platform',
    'apps.merchant_platform',
    'apps.admin_platform',
    'apps.common',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'magnesium_order_platform.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.common.context_processors.global_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'magnesium_order_platform.wsgi.application'

# ==================== 数据库配置 ====================
# 开发环境默认SQLite，生产环境通过环境变量切换PostgreSQL
DB_ENGINE = os.environ.get('DB_ENGINE', 'sqlite3')

if DB_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'magnesium_order_db'),
            'USER': os.environ.get('DB_USER', 'magnesium_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
elif DB_ENGINE == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'magnesium_order_db'),
            'USER': os.environ.get('DB_USER', 'magnesium_user'),
            'PASSWORD': os.environ.get('DB_PASSWORD', ''),
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {
                'charset': 'utf8mb4',
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'zh-hans'
TIME_ZONE = 'Asia/Shanghai'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
# 生产环境执行 collectstatic 后收集到此目录
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==================== 阿里云 OSS 存储配置 ====================
# 使用说明：
#   1. 登录阿里云控制台 https://oss.console.aliyun.com/
#   2. 创建 Bucket（建议选择"标准存储" + "公共读"）
#   3. 在"访问控制 RAM"中创建 AccessKey，获取 ID 和 Secret
#   4. 将下方配置填入真实值
#   5. 如需启用 OSS，取消下面 DEFAULT_FILE_STORAGE 的注释
#   6. 如需保持本地存储（开发环境），保持注释状态即可
#
# 可选：配置 CDN 加速域名，降低流量费用
#   OSS_CUSTOM_DOMAIN = 'https://cdn.yourdomain.com'

OSS_ACCESS_KEY_ID = os.environ.get('OSS_ACCESS_KEY_ID', '')           # AccessKey ID
OSS_ACCESS_KEY_SECRET = os.environ.get('OSS_ACCESS_KEY_SECRET', '')       # AccessKey Secret
OSS_ENDPOINT = 'oss-cn-shanghai.aliyuncs.com'  # Bucket 所在地域的 Endpoint
OSS_BUCKET_NAME = 'zbhomefiles'             # Bucket 名称
OSS_BASE_DIR = 'magnesium/'      # 文件在 Bucket 中的根目录
OSS_INTERNAL = True             # ECS 同区域建议使用 True（走内网，免费且更快）
OSS_CUSTOM_DOMAIN = ''           # CDN 加速域名（可选）

# 启用 OSS：取消下面一行的注释，所有上传文件将自动存入阿里云 OSS
DEFAULT_FILE_STORAGE = 'utils.oss_storage.AliyunOSSMediaStorage'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Login / Logout redirects
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

# Session settings
SESSION_COOKIE_AGE = 86400 * 7  # 7 days

# File upload limits
DATA_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800  # 50MB

# ==================== 快递100 物流查询配置 ====================
# 接入步骤：
# 1. 访问 https://www.kuaidi100.com/openapi/apply.shtml 注册企业账号
# 2. 在"我的接口"中获取：授权Key 和 Customer ID
# 3. 将下面的空字符串替换为你的真实值
# 4. 可选：调整 KUAIDI100_CACHE_SECONDS（物流缓存秒数，默认300秒）
KUAIDI100_KEY = ''           # 快递100授权Key
KUAIDI100_CUSTOMER = ''      # 快递100 Customer ID
KUAIDI100_CACHE_SECONDS = 300  # 物流数据缓存时间（秒）
