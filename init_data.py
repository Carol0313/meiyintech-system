"""
初始化测试数据脚本
运行方式: python init_data.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'magnesium_order_platform.settings')
django.setup()

from decimal import Decimal
from apps.accounts.models import User, Merchant, CustomerProfile, StaffProfile, Role
from apps.products.models import ProductSpec


def init():
    print("开始初始化数据...")

    # 1. 总平台管理员
    admin, _ = User.objects.get_or_create(
        phone='13800000000',
        defaults={
            'username': 'platform_admin',
            'user_type': 'platform_admin',
            'is_staff': True,
            'is_superuser': True,
            'is_approved': True,
        }
    )
    admin.set_password('admin123')
    admin.save()
    print("[OK] 总平台管理员: 13800000000 / admin123")

    # 2. 商家
    merchant, _ = Merchant.objects.get_or_create(
        name='上海闪电科技有限公司',
        defaults={
            'address': '上海市浦东新区',
            'service_regions': '上海,江苏,浙江',
            'contact_phone': '13800138000',
            'customer_service_wechat': 'magnesium_kefu',
            'status': 'approved',
            'annual_fee_paid': True,
            'max_sub_accounts': 5,
        }
    )

    # 3. 商家管理员
    madmin, _ = User.objects.get_or_create(
        phone='13800138000',
        defaults={
            'username': 'merchant_admin',
            'user_type': 'merchant_admin',
            'is_approved': True,
        }
    )
    madmin.set_password('admin123')
    madmin.save()
    merchant.admin_user = madmin
    merchant.save()
    print("[OK] 商家管理员: 13800138000 / admin123")

    # 4. 创建商家角色
    for role_name, role_label in Role.ROLE_NAME_CHOICES:
        Role.objects.get_or_create(
            merchant=merchant, name=role_name,
            defaults={'custom_name': role_label, 'permissions': ''}
        )
    print("[OK] 商家角色已创建")

    # 5. 平台预设商品规格
    specs_data = [
        ('magnesium', 'etching', '1.5', Decimal('12.00')),
        ('magnesium', 'etching', '2.0', Decimal('12.50')),
        ('magnesium', 'etching', '3.0', Decimal('13.00')),
        ('magnesium', 'engraving', '1.5', Decimal('35.00')),
        ('magnesium', 'engraving', '3.0', Decimal('38.00')),
        ('copper', 'etching', '1.5', Decimal('15.00')),
        ('copper', 'etching', '2.0', Decimal('16.00')),
        ('copper', 'engraving', '1.5', Decimal('40.00')),
        ('magnesium', 'resin', '1.5', Decimal('10.00')),
        ('magnesium', 'film', '1.5', Decimal('5.00')),
    ]
    for mat, proc, thick, price in specs_data:
        ProductSpec.objects.get_or_create(
            material=mat, process_type=proc, thickness=thick, merchant=None,
            defaults={'base_price': price, 'is_platform_preset': True, 'is_active': True}
        )
    print("[OK] 平台预设规格已创建")

    # 6. 终端用户（已审核）
    customer, _ = User.objects.get_or_create(
        phone='13900139000',
        defaults={
            'username': 'customer001',
            'user_type': 'customer',
            'is_approved': True,
        }
    )
    customer.set_password('admin123')
    customer.save()
    cprofile, _ = CustomerProfile.objects.get_or_create(
        user=customer,
        defaults={
            'company_name': '客户测试公司',
            'city': '上海',
            'real_name': '张三',
            'merchant': merchant,
            'credit_limit': Decimal('10000.00'),
            'credit_used': Decimal('0'),
            'invite_code': merchant.invite_code,
            'registration_status': 'approved',
        }
    )
    print("[OK] 终端用户: 13900139000 / admin123")

    print("\n初始化完成！")
    print("=" * 40)
    print("总平台管理员: 13800000000 / admin123")
    print("商家管理员  : 13800138000 / admin123")
    print("终端用户    : 13900139000 / admin123")
    print("=" * 40)


if __name__ == '__main__':
    init()
