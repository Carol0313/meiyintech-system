"""
将本地 media 文件同步到阿里云 OSS

使用方法：
    python manage.py sync_files_to_oss

可选参数：
    --dry-run     只列出要同步的文件，不实际上传
    --dir         指定子目录，如 order_files、plate_layouts
    --delete      同步后删除本地文件（谨慎使用）

示例：
    python manage.py sync_files_to_oss --dry-run
    python manage.py sync_files_to_oss --dir order_files
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage

from utils.oss_storage import AliyunOSSStorage


class Command(BaseCommand):
    help = '将本地 media 文件同步到阿里云 OSS'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='只列出要同步的文件，不实际上传',
        )
        parser.add_argument(
            '--dir',
            type=str,
            default='',
            help='指定 media 下的子目录，如 order_files',
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='同步成功后删除本地文件（谨慎使用）',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        sub_dir = options['dir']
        delete_local = options['delete']

        # 检查 OSS 配置
        if not getattr(settings, 'OSS_ACCESS_KEY_ID', ''):
            self.stdout.write(self.style.ERROR('错误：未配置 OSS_ACCESS_KEY_ID，请在 settings.py 中填写阿里云 OSS 参数'))
            return
        if not getattr(settings, 'OSS_BUCKET_NAME', ''):
            self.stdout.write(self.style.ERROR('错误：未配置 OSS_BUCKET_NAME'))
            return

        # 初始化 OSS Storage
        try:
            oss_storage = AliyunOSSStorage()
            self.stdout.write(self.style.SUCCESS(f'已连接到 OSS Bucket: {oss_storage.bucket_name}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'OSS 连接失败: {e}'))
            return

        # 确定要扫描的本地目录
        media_root = str(settings.MEDIA_ROOT)
        if sub_dir:
            scan_dir = os.path.join(media_root, sub_dir)
            relative_prefix = sub_dir
        else:
            scan_dir = media_root
            relative_prefix = ''

        if not os.path.exists(scan_dir):
            self.stdout.write(self.style.ERROR(f'目录不存在: {scan_dir}'))
            return

        # 扫描文件
        files_to_sync = []
        for root, dirs, files in os.walk(scan_dir):
            for filename in files:
                local_path = os.path.join(root, filename)
                # 计算相对路径
                rel_path = os.path.relpath(local_path, media_root)
                rel_path = rel_path.replace('\\', '/')
                files_to_sync.append((local_path, rel_path))

        if not files_to_sync:
            self.stdout.write(self.style.WARNING('没有找到需要同步的文件'))
            return

        total_size = sum(os.path.getsize(lp) for lp, _ in files_to_sync)
        self.stdout.write(f'共找到 {len(files_to_sync)} 个文件，总计 {total_size / 1024 / 1024:.2f} MB')

        if dry_run:
            self.stdout.write(self.style.WARNING('【试运行模式】以下文件将被同步（未实际上传）：'))
            for local_path, rel_path in files_to_sync:
                size = os.path.getsize(local_path)
                self.stdout.write(f'  {rel_path} ({size / 1024:.1f} KB)')
            return

        # 开始同步
        success_count = 0
        skip_count = 0
        fail_count = 0
        deleted_count = 0
        total_uploaded = 0

        for local_path, rel_path in files_to_sync:
            size = os.path.getsize(local_path)

            # 检查 OSS 上是否已存在
            if oss_storage.exists(rel_path):
                self.stdout.write(f'  [跳过] {rel_path}（已存在于 OSS）')
                skip_count += 1
                if delete_local:
                    try:
                        os.remove(local_path)
                        deleted_count += 1
                    except Exception:
                        pass
                continue

            try:
                with open(local_path, 'rb') as f:
                    oss_storage.save(rel_path, f)
                success_count += 1
                total_uploaded += size
                self.stdout.write(self.style.SUCCESS(f'  [成功] {rel_path} ({size / 1024:.1f} KB)'))

                if delete_local:
                    try:
                        os.remove(local_path)
                        deleted_count += 1
                    except Exception as e:
                        self.stdout.write(self.style.WARNING(f'    删除本地文件失败: {e}'))

            except Exception as e:
                fail_count += 1
                self.stdout.write(self.style.ERROR(f'  [失败] {rel_path}: {e}'))

        # 汇总
        self.stdout.write()
        self.stdout.write(self.style.SUCCESS('========== 同步完成 =========='))
        self.stdout.write(f'  成功上传: {success_count} 个文件 ({total_uploaded / 1024 / 1024:.2f} MB)')
        self.stdout.write(f'  跳过(已存在): {skip_count} 个')
        self.stdout.write(f'  失败: {fail_count} 个')
        if delete_local:
            self.stdout.write(f'  已删除本地文件: {deleted_count} 个')

        if fail_count == 0 and success_count > 0:
            self.stdout.write()
            self.stdout.write(self.style.SUCCESS('所有文件已同步到阿里云 OSS！'))
            self.stdout.write('下一步：取消 settings.py 中 DEFAULT_FILE_STORAGE 的注释，启用 OSS 存储。')
