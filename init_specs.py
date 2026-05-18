"""
录入完整价格数据（腐蚀版 + 雕刻版 + 树脂版 + 菲林）
运行: python init_specs.py
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'magnesium_order_platform.settings')
django.setup()

from apps.products.models import ProductSpec
from utils.pricing_tiers import get_all_specs

# 清空旧数据
ProductSpec.objects.filter(is_platform_preset=True).delete()

SPECS = get_all_specs()

for product_name, material, thickness, price in SPECS:
    ProductSpec.objects.create(
        product_name=product_name,
        material=material,
        thickness=thickness,
        unit_price=price,
        is_platform_preset=True,
        is_active=True,
    )

print(f'已录入 {len(SPECS)} 条规格价格数据')
for s in ProductSpec.objects.filter(is_platform_preset=True):
    print(f'  {s.product_name} {s.material} {s.thickness}mm = {s.unit_price}')
