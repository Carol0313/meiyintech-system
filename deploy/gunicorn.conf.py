# Gunicorn 生产环境配置文件
# 用法: gunicorn -c deploy/gunicorn.conf.py magnesium_order_platform.wsgi:application

import multiprocessing

# 绑定地址和端口
bind = "127.0.0.1:8000"

# 工作进程数 = CPU核心数 × 2 + 1
workers = multiprocessing.cpu_count() * 2 + 1

# 工作模式：同步模式（Django推荐）
worker_class = "sync"

# 每个工作进程处理的最大请求数，超过后自动重启（防止内存泄漏）
max_requests = 1000
max_requests_jitter = 50

# 超时时间（秒）
timeout = 120
keepalive = 5

# 进程名称
proc_name = "magnesium_order_platform"

# 日志配置
accesslog = "/var/log/gunicorn/magnesium_access.log"
errorlog = "/var/log/gunicorn/magnesium_error.log"
loglevel = "info"

# 守护进程模式（如果使用systemd管理，建议设为False）
daemon = False

# PID文件（供systemd使用）
pidfile = "/tmp/gunicorn_magnesium.pid"

# 用户和组（生产环境建议改为非root用户）
# user = "www-data"
# group = "www-data"
