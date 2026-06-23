"""
测试配置 - 使用SQLite内存数据库，快速运行测试
"""
from .settings import *

# 使用SQLite内存数据库加速测试
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# 测试时关闭邮件发送
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'

# 使用本地文件存储（避免OSS依赖）
DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'
MEDIA_ROOT = BASE_DIR / 'test_media'

# 测试时关闭缓存或内存缓存
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# 关闭DEBUG模式以测试生产环境行为
DEBUG = False

# 允许所有host（测试环境）
ALLOWED_HOSTS = ['*']

# 使用快速密码哈希器加速测试
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

# 日志输出到控制台
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
        },
    },
}

# 快递100测试配置
KUAIDI100_KEY = 'test_key'
KUAIDI100_CUSTOMER = 'test_customer'
KUAIDI100_CALLBACK_URL = 'http://test.example.com/webhook/kuaidi100/'

# 阿里云OSS测试配置（使用本地存储）
OSS_ACCESS_KEY_ID = 'test'
OSS_ACCESS_KEY_SECRET = 'test'
OSS_BUCKET_NAME = 'test-bucket'
OSS_ENDPOINT = 'oss-cn-hangzhou.aliyuncs.com'

# 关闭CSRF验证（测试视图时）
# 注意：只在特定测试中使用，不要全局关闭
