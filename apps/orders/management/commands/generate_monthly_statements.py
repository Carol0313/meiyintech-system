"""
按月自动生成对账单
汇总每个客户上月所有已收货且未结清、未关联账单的订单
"""
from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import CustomerProfile
from apps.orders.models import Order, Statement


class Command(BaseCommand):
    help = '按月自动生成对账单（默认上月）'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year', type=int, help='指定年份（默认上年或本月）'
        )
        parser.add_argument(
            '--month', type=int, help='指定月份（默认上月）'
        )
        parser.add_argument(
            '--dry-run', action='store_true', help='仅预览，不实际生成'
        )

    def handle(self, *args, **options):
        year = options.get('year')
        month = options.get('month')
        dry_run = options.get('dry_run')

        today = date.today()
        if year and month:
            period_start = date(year, month, 1)
            if month == 12:
                period_end = date(year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = date(year, month + 1, 1) - timedelta(days=1)
        else:
            # 默认上月
            first_day_this_month = today.replace(day=1)
            period_end = first_day_this_month - timedelta(days=1)
            period_start = period_end.replace(day=1)

        self.stdout.write(f'账单周期: {period_start} ~ {period_end}')

        # 查找所有有符合条件的订单的客户
        candidate_orders = Order.objects.filter(
            status='received',
            is_settled=False,
            statement__isnull=True,
            created_at__date__gte=period_start,
            created_at__date__lte=period_end,
        ).select_related('customer', 'merchant')

        # 按客户分组
        customer_orders = {}
        for order in candidate_orders:
            key = (order.customer_id, order.merchant_id)
            customer_orders.setdefault(key, []).append(order)

        created_count = 0
        total_amount = Decimal('0')

        with transaction.atomic():
            for (customer_id, merchant_id), orders in customer_orders.items():
                statement = Statement(
                    customer_id=customer_id,
                    merchant_id=merchant_id,
                    period_start=period_start,
                    period_end=period_end,
                )
                if not dry_run:
                    statement.save()
                    for order in orders:
                        order.statement = statement
                        order.save(update_fields=['statement'])
                    statement.update_total()
                    amount = statement.total_amount
                else:
                    amount = sum(o.total_amount for o in orders)
                    self.stdout.write(f'[预览] 客户 {orders[0].customer.phone}: ¥{amount} ({len(orders)} 单)')

                created_count += 1
                total_amount += amount

            if dry_run:
                self.stdout.write(self.style.WARNING(f'[预览] 将生成 {created_count} 个对账单，总金额 ¥{total_amount}'))
            else:
                self.stdout.write(self.style.SUCCESS(f'成功生成 {created_count} 个对账单，总金额 ¥{total_amount}'))
