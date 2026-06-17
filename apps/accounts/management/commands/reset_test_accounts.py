"""
重置内测/文档中的测试账号密码，并修复审核状态。
用法: python manage.py reset_test_accounts
可选: python manage.py reset_test_accounts --password 新密码
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Merchant, CustomerProfile, Role, StaffProfile

DEFAULT_PASSWORD = 'admin123'

TEST_ACCOUNTS = [
    {
        'phone': '13800000000',
        'user_type': 'platform_admin',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'phone': '13800138000',
        'user_type': 'merchant_admin',
    },
    {
        'phone': '13900139000',
        'user_type': 'customer',
    },
    {
        'phone': '13800138002',
        'user_type': 'merchant_staff',
    },
    {
        'phone': '13800138005',
        'user_type': 'merchant_staff',
    },
    {
        'phone': '13800138006',
        'user_type': 'merchant_staff',
    },
]

INVITE_CODE = 'MA1B2C3'


class Command(BaseCommand):
    help = '重置测试账号密码为 admin123（可自定义），并确保审核状态可登录'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password',
            default=DEFAULT_PASSWORD,
            help=f'统一密码，默认 {DEFAULT_PASSWORD}',
        )

    def handle(self, *args, **options):
        password = options['password']
        User = get_user_model()

        merchant = self._ensure_merchant(User)

        for spec in TEST_ACCOUNTS:
            phone = spec['phone']
            user, created = User.objects.get_or_create(
                phone=phone,
                defaults={
                    'username': phone,
                    'user_type': spec['user_type'],
                },
            )
            if created:
                self.stdout.write(self.style.WARNING(f'新建用户 {phone}'))

            user.username = phone
            user.user_type = spec['user_type']
            user.is_active = True
            user.is_approved = True
            user.is_staff = spec.get('is_staff', False)
            user.is_superuser = spec.get('is_superuser', False)
            user.set_password(password)
            user.save()

            if spec['user_type'] == 'merchant_admin':
                if not getattr(user, 'managed_merchant', None):
                    merchant.admin_user = user
                    merchant.save(update_fields=['admin_user'])

            elif spec['user_type'] == 'customer':
                profile, _ = CustomerProfile.objects.get_or_create(
                    user=user,
                    defaults={'merchant': merchant, 'invite_code': INVITE_CODE},
                )
                profile.merchant = merchant
                profile.invite_code = INVITE_CODE
                profile.registration_status = 'approved'
                profile.real_name = profile.real_name or '测试客户'
                if profile.credit_limit <= 0:
                    profile.credit_limit = 100000
                profile.save()

            elif spec['user_type'] == 'merchant_staff':
                role = Role.objects.filter(merchant=merchant, name='customer_service').first()
                if not role:
                    role = Role.objects.create(
                        merchant=merchant, name='customer_service', custom_name='客服岗',
                    )
                staff, _ = StaffProfile.objects.get_or_create(user=user, defaults={'merchant': merchant})
                staff.merchant = merchant
                staff.role = role
                staff.is_active = True
                staff.save()

            self.stdout.write(self.style.SUCCESS(f'✓ {phone} ({spec["user_type"]}) 密码已重置'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'全部完成，统一密码: {password}'))
        self.stdout.write(f'商家邀请码: {INVITE_CODE}')

    def _ensure_merchant(self, User):
        merchant = Merchant.objects.filter(invite_code=INVITE_CODE).first()
        if merchant:
            merchant.status = 'approved'
            merchant.annual_fee_paid = True
            merchant.save(update_fields=['status', 'annual_fee_paid'])
            return merchant

        admin = User.objects.filter(phone='13800138000').first()
        merchant = Merchant.objects.create(
            name='测试商家',
            status='approved',
            invite_code=INVITE_CODE,
            annual_fee_paid=True,
            admin_user=admin,
        )
        for role_name, role_label in Role.ROLE_NAME_CHOICES:
            Role.objects.get_or_create(
                merchant=merchant, name=role_name,
                defaults={'custom_name': role_label},
            )
        self.stdout.write(self.style.WARNING(f'已创建测试商家，邀请码 {INVITE_CODE}'))
        return merchant
