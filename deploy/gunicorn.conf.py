"""
Gunicorn 生产环境配置文件
用法: gunicorn magnesium_order_platform.wsgi:application -c deploy/gunicorn.conf.py
"""
import multiprocessing
import os

# 服务器套接字绑定
bind = "127.0.0.1:8000"

# 工作进程数: CPU核心数 * 2 + 1
workers = multiprocessing.cpu_count() * 2 + 1

# 工作进程类型: sync (适用于CPU密集型/标准Django应用)
worker_class = "sync"

# 每个工作进程处理的最大请求数，超过后自动重启（防内存泄漏）
max_requests = 1000
max_requests_jitter = 100

# 超时时间（秒）
timeout = 120
keepalive = 5

# 连接积压
backlog = 2048

# 进程名称
proc_name = "magnesium"

# 守护进程模式（由systemd管理时设为False）
daemon = False

# PID文件
pidfile = "/tmp/magnesium.pid"

# 日志配置
accesslog = "/var/log/gunicorn/magnesium_access.log"
errorlog = "/var/log/gunicorn/magnesium_error.log"
loglevel = "info"

# 捕获输出
capture_output = True
enable_stdio_inheritance = True

# 安全: 不转发Django的HTTP_X_FORWARDED_FOR（由Nginx处理）
forwarded_allow_ips = "127.0.0.1"

# 预加载应用（节省内存）
preload_app = True


def on_starting(server):
    """启动前创建日志目录"""
    os.makedirs("/var/log/gunicorn", exist_ok=True)
