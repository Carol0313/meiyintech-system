"""
测试阿里云 OSS 连接
运行方式：python test_oss_connection.py
"""
import os
import oss2

# 1. 验证环境变量
access_key_id = os.environ.get('OSS_ACCESS_KEY_ID', '')
access_key_secret = os.environ.get('OSS_ACCESS_KEY_SECRET', '')

print("=" * 50)
print("Step 1: 检查环境变量")
print("=" * 50)
print("OSS_ACCESS_KEY_ID: %s (长度: %d)" % ('已设置' if access_key_id else '未设置', len(access_key_id)))
print("OSS_ACCESS_KEY_SECRET: %s (长度: %d)" % ('已设置' if access_key_secret else '未设置', len(access_key_secret)))

if not access_key_id or not access_key_secret:
    print("\n[错误] 环境变量未正确读取，请检查系统环境变量配置并重启终端/VS Code")
    exit(1)

# 2. 读取 settings.py 中的 OSS 配置
print("\n" + "=" * 50)
print("Step 2: 读取 Django settings 中的 OSS 配置")
print("=" * 50)

import django
from django.conf import settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'magnesium_order_platform.settings')
django.setup()

endpoint = settings.OSS_ENDPOINT
bucket_name = settings.OSS_BUCKET_NAME
use_internal = settings.OSS_INTERNAL
base_dir = settings.OSS_BASE_DIR

print("Endpoint: %s" % endpoint)
print("Bucket: %s" % bucket_name)
print("Internal: %s" % use_internal)
print("Base Dir: %s" % base_dir)

# 如果启用内网，转换 endpoint
if use_internal and '.aliyuncs.com' in endpoint and '-internal' not in endpoint:
    endpoint = endpoint.replace('.aliyuncs.com', '-internal.aliyuncs.com')
    print("使用内网 Endpoint: %s" % endpoint)

# 3. 连接 OSS
print("\n" + "=" * 50)
print("Step 3: 连接 OSS Bucket")
print("=" * 50)
try:
    auth = oss2.Auth(access_key_id, access_key_secret)
    bucket = oss2.Bucket(auth, "https://%s" % endpoint, bucket_name)

    # 测试连接：获取 Bucket 信息
    bucket_info = bucket.get_bucket_info()
    print("[成功] 连接成功！")
    print("   Bucket 名称: %s" % bucket_info.name)
    print("   创建时间: %s" % bucket_info.creation_date)
    print("   存储区域: %s" % bucket_info.location)

    # 测试上传一个小文件
    test_key = "%s/test/connection_test.txt" % base_dir.rstrip('/')
    print("\nStep 4: 测试上传文件到 %s" % test_key)
    bucket.put_object(test_key, b"Hello OSS from magnesium_order_platform!")
    print("[成功] 测试文件上传成功")

    # 验证文件存在
    exists = bucket.object_exists(test_key)
    print("   文件存在检查: %s" % ('通过' if exists else '未通过'))

    # 删除测试文件
    bucket.delete_object(test_key)
    print("[成功] 测试文件已清理")

    print("\n[完成] OSS 配置完全正常，可以开始使用了！")

except oss2.exceptions.NoSuchBucket:
    print("\n[错误] Bucket '%s' 不存在，请检查 OSS_BUCKET_NAME 配置" % bucket_name)
except oss2.exceptions.AccessDenied:
    print("\n[错误] 没有访问该 Bucket 的权限，请检查 RAM 授权")
except oss2.exceptions.RequestError as e:
    print("\n[错误] 网络请求失败: %s" % e)
    print("\n常见原因：")
    print("1. 如果在外地/非阿里云服务器开发，请将 settings.py 中的 OSS_INTERNAL 改为 False")
    print("2. Endpoint 与 Bucket 实际地域不匹配")
    print("3. 网络连接问题（公司网络/防火墙限制）")
except Exception as e:
    print("\n[错误] 连接失败: %s: %s" % (type(e).__name__, e))
    print("\n常见原因：")
    print("1. 如果在外地/非阿里云服务器开发，请将 settings.py 中的 OSS_INTERNAL 改为 False")
    print("2. Endpoint 与 Bucket 实际地域不匹配")
    print("3. 网络连接问题（公司网络/防火墙限制）")
