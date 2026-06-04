#!/usr/bin/env python
"""
服务器数据库更新脚本
用途：同步客服角色修改 + 创建终端测试账号
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'magnesium_order_platform.settings')
django.setup()

from apps.accounts.models import User, StaffProfile, Role, CustomerProfile, Merchant

print("=" * 50)
print("  服务器数据库更新")
print("=" * 50)

# -------------------- 1. 修改3个客服账号为admin角色 --------------------
print("\n[1/2] 修改客服账号角色为 admin...")
phones = ['13800138002', '13800138005', '13800138006']
for phone in phones:
    try:
        user = User.objects.get(phone=phone)
        staff = user.staff_profile
        merchant = staff.merchant
        admin_role = Role.objects.get(merchant=merchant, name='admin')
        staff.role = admin_role
        staff.save()
        print(f"  [OK] {phone} -> admin")
    except Exception as e:
        print(f"  [SKIP/FAIL] {phone}: {e}")

# -------------------- 2. 创建4个终端测试账号 --------------------
print("\n[2/2] 创建终端测试账号...")
merchant = Merchant.objects.first()
if not merchant:
    print("  [FAIL] 未找到任何商家，无法创建终端账号")
else:
    customers = [
        ('13900139001', '终端客户A', '测试公司A', '张三'),
        ('13900139002', '终端客户B', '测试公司B', '李四'),
        ('13900139003', '终端客户C', '测试公司C', '王五'),
        ('13900139004', '终端客户D', '测试公司D', '赵六'),
    ]
    for phone, username, company, real_name in customers:
        try:
            if User.objects.filter(phone=phone).exists():
                print(f"  [SKIP] {phone} 已存在")
                continue
            user = User.objects.create_user(
                username=username,
                phone=phone,
                password='admin123',
                user_type='customer',
                is_approved=True
            )
            CustomerProfile.objects.create(
                user=user,
                merchant=merchant,
                registration_status='approved',
                company_name=company,
                real_name=real_name
            )
            print(f"  [OK] {phone} / admin123 -> {real_name}")
        except Exception as e:
            print(f"  [FAIL] {phone}: {e}")

print("\n" + "=" * 50)
print("  数据库更新完成")
print("=" * 50)
