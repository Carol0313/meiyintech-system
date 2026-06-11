#!/usr/bin/env python
"""
将服务器本地 media/ 文件批量迁移到阿里云 OSS
用法：python migrate_to_oss.py
"""
import os
import sys

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'magnesium_order_platform.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.conf import settings
from django.core.files.storage import default_storage


def migrate_media_to_oss():
    local_media = str(settings.BASE_DIR / 'media')
    if not os.path.exists(local_media):
        print(f"❌ media 目录不存在: {local_media}")
        return

    total = 0
    success = 0
    failed = 0

    for root, dirs, files in os.walk(local_media):
        for filename in files:
            local_path = os.path.join(root, filename)
            rel_path = os.path.relpath(local_path, local_media)
            total += 1

            # 跳过已存在于 OSS 的文件
            if default_storage.exists(rel_path):
                print(f"⏭️  跳过（已存在）: {rel_path}")
                continue

            try:
                with open(local_path, 'rb') as fp:
                    default_storage.save(rel_path, fp)
                print(f"✅ 上传成功: {rel_path}")
                success += 1
            except Exception as e:
                print(f"❌ 上传失败: {rel_path} -> {e}")
                failed += 1

    print(f"\n{'='*50}")
    print(f"迁移完成！总计: {total}, 成功: {success}, 失败: {failed}")
    print(f"{'='*50}")


if __name__ == '__main__':
    # 检查 OSS 是否已启用
    storage_class = default_storage.__class__.__name__
    if 'OSS' not in storage_class:
        print(f"❌ 当前存储后端不是 OSS: {storage_class}")
        print("请先在 settings.py 中启用 DEFAULT_FILE_STORAGE = 'utils.oss_storage.AliyunOSSMediaStorage'")
        sys.exit(1)

    # 检查环境变量
    if not settings.OSS_ACCESS_KEY_ID or not settings.OSS_ACCESS_KEY_SECRET:
        print("❌ 未配置 OSS_ACCESS_KEY_ID 或 OSS_ACCESS_KEY_SECRET 环境变量")
        sys.exit(1)

    print(f"存储后端: {storage_class}")
    print(f"Bucket: {settings.OSS_BUCKET_NAME}")
    print(f"Base Dir: {settings.OSS_BASE_DIR}")
    print(f"本地 media 路径: {settings.BASE_DIR / 'media'}")
    print("-" * 50)

    confirm = input("确认开始迁移？(yes/no): ")
    if confirm.lower() in ('yes', 'y'):
        migrate_media_to_oss()
    else:
        print("已取消")
