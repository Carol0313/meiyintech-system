"""
修复客户信用额度已用值
将 credit_used 修正为：所有已支付且未结清订单（含生产中/已发货/已收货）的金额总和
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum
from apps.accounts.models import CustomerProfile
from apps.orders.models import Order

# 占用信用额度、尚未结清的订单状态
CREDIT_ENCUMBERED_STATUSES = ('paid', 'in_production', 'shipped', 'received')


class Command(BaseCommand):
    help = '修复客户信用额度已用值，使其等于所有未结清已支付订单的总额'

    def handle(self, *args, **options):
        profiles = CustomerProfile.objects.all()
        fixed = 0
        for profile in profiles:
            total = Order.objects.filter(
                customer=profile.user,
                status__in=CREDIT_ENCUMBERED_STATUSES,
                is_settled=False,
            ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0')
            total = total.quantize(Decimal('0.01'))
            if profile.credit_used != total:
                old = profile.credit_used
                profile.credit_used = total
                profile.save(update_fields=['credit_used'])
                self.stdout.write(
                    self.style.WARNING(
                        f'{profile.user.phone}: {old}元 -> {total}元 (diff: {total - old}元)'
                    )
                )
                fixed += 1
            else:
                self.stdout.write(
                    f'{profile.user.phone}: {total}元 (正确)'
                )
        self.stdout.write(self.style.SUCCESS(f'共修复 {fixed} 个客户的信用额度'))
