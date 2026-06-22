"""
Django settings for magnesium_order_platform project.
"""

import os
import logging
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

# PyMySQL 兼容（宝塔面板使用 MySQL 时无需安装 mysqlclient）
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

# 确保日志目录存在，避免新环境/容器启动时因缺少目录而失败
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# ==================== 安全设置 ====================
# 生产环境必须通过环境变量传入，严禁使用默认密钥
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')

# 生产环境必须配置具体域名
ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '').split(',')
    if h.strip()
]

# 生产环境 fail-closed 校验
if not DEBUG:
    if not SECRET_KEY or len(SECRET_KEY) < 32 or SECRET_KEY.startswith('django-insecure-'):
        raise ImproperlyConfigured(
            "生产环境必须设置强随机 DJANGO_SECRET_KEY（至少 32 位，且不能以 django-insecure- 开头）。"
        )
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "生产环境必须设置 DJANGO_ALLOWED_HOSTS，不能留空。"
        )
    if '*' in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "生产环境 DJANGO_ALLOWED_HOSTS 不允许使用通配符 '*'。"
        )

# 开发环境兜底（仅用于本地开发，不允许进入生产）
if DEBUG:
    if not SECRET_KEY:
        SECRET_KEY = 'django-insecure-dev-only-not-for-production'
        logging.getLogger(__name__).warning(
            "当前使用开发环境默认 SECRET_KEY，请勿用于生产。"
        )
    if not ALLOWED_HOSTS:
        ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

# 允许同站点嵌入（用于PDF文件预览）
X_FRAME_OPTIONS = 'SAMEORIGIN'

# 生产环境必须配置CSRF可信来源（HTTPS部署时）
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        'CSRF_TRUSTED_ORIGINS',
        'http://127.0.0.1,http://localhost,http://www.zhibanhome.com,https://www.zhibanhome.com'
    ).split(',')
    if o.strip()
]

# 备案期间用 IP + HTTP 访问时设为 false；域名 HTTPS 上线后改为 true
USE_HTTPS = os.environ.get('DJANGO_USE_HTTPS', 'true' if not DEBUG else 'false').lower() in ('true', '1', 'yes')

# 生产环境安全设置（仅 HTTPS 模式启用，HTTP 访问时须关闭否则无法登录）
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    if USE_HTTPS:
        SECURE_SSL_REDIRECT = True
        SESSION_COOKIE_SECURE = True
        CSRF_COOKIE_SECURE = True
        SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    # HSTS 谨慎启用：先短 TTL 灰度，验证无 mixed-content 后再提升
    # SECURE_HSTS_SECONDS = 300
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True

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
# 自动检测是否在阿里云ECS内网环境：DEBUG=True（本地开发）时使用外网，生产环境可设环境变量覆盖
OSS_INTERNAL = os.environ.get('OSS_INTERNAL', 'false' if DEBUG else 'true').lower() in ('true', '1', 'yes')  # ECS同区域部署默认True，本地开发/非阿里云服务器设 OSS_INTERNAL=false
OSS_CUSTOM_DOMAIN = ''           # CDN 加速域名（可选）

# 启用 OSS：所有上传文件将自动存入阿里云 OSS
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
KUAIDI100_KEY = os.environ.get('KUAIDI100_KEY', '')           # 快递100授权Key
KUAIDI100_CUSTOMER = os.environ.get('KUAIDI100_CUSTOMER', '')      # 快递100 Customer ID
KUAIDI100_CACHE_SECONDS = 300  # 物流数据缓存时间（秒）
# 快递100推送回调地址（用于订阅物流状态变更推送）
# 格式：https://您的域名/webhook/kuaidi100/
# 需要在快递100后台配置回调URL，并确保公网可访问
KUAIDI100_CALLBACK_URL = os.environ.get('KUAIDI100_CALLBACK_URL', '')

# ==================== 阿里云短信配置（手机号验证码登录） ====================
SMS_ACCESS_KEY_ID = os.environ.get('SMS_ACCESS_KEY_ID', '')
SMS_ACCESS_KEY_SECRET = os.environ.get('SMS_ACCESS_KEY_SECRET', '')
SMS_SIGN_NAME = os.environ.get('SMS_SIGN_NAME', '')          # 短信签名，如：闪电制版
SMS_TEMPLATE_CODE = os.environ.get('SMS_TEMPLATE_CODE', '')  # 验证码模板CODE，如：SMS_xxxxxxx

# ==================== 日志配置 ====================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'error.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
    },
    'root': {
        'handlers': ['console', 'file', 'error_file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file', 'error_file'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['error_file'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}
