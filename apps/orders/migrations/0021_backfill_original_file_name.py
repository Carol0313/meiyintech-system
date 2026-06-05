"""
回填 OrderItem.original_file_name 字段
为历史数据设置默认文件名（基于文件扩展名）
"""

from django.db import migrations
import os


def backfill_original_file_name(apps, schema_editor):
    """为所有没有 original_file_name 的 OrderItem 设置默认文件名"""
    OrderItem = apps.get_model('orders', 'OrderItem')
    items = OrderItem.objects.filter(file__isnull=False).exclude(file='').filter(original_file_name='')
    
    updated = 0
    for item in items:
        # 从文件路径获取扩展名
        ext = os.path.splitext(item.file.name)[1].lower()
        if ext == '.pdf':
            default_name = '上传文件.pdf'
        elif ext in ('.ai', '.eps'):
            default_name = f'设计文件{ext}'
        elif ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'):
            default_name = f'图片文件{ext}'
        else:
            default_name = f'附件{ext}' if ext else '附件'
        
        item.original_file_name = default_name
        item.save(update_fields=['original_file_name'])
        updated += 1
    
    print(f"已回填 {updated} 条 OrderItem 的 original_file_name")


def reverse_backfill(apps, schema_editor):
    """反向迁移：清空所有默认文件名（可选）"""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0020_add_plate_file_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_original_file_name, reverse_backfill),
    ]
