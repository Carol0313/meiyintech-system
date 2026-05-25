"""
修复客户信用额度已用值
将 credit_used 修正为：所有 status='paid' 且 is_settled=False 的订单金额总和
"""
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db.models import Sum
from apps.accounts.models import CustomerProfile
from apps.orders.models import Order


class Command(BaseCommand):
    help = '修复客户信用额度已用值，使其等于所有未结清已支付订单的总额'

    def handle(self, *args, **options):
        profiles = CustomerProfile.objects.all()
        fixed = 0
        for profile in profiles:
            total = Order.objects.filter(
                customer=profile.user,
                status='paid',
                is_settled=False
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
