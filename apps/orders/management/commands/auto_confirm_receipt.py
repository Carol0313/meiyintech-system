"""
自动确认收货定时任务
扫描所有已发货超过7天未确认的订单，自动将状态改为已收货
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.orders.models import Order


class Command(BaseCommand):
    help = '自动确认收货：发货后7天客户未确认的订单自动确认'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days', type=int, default=7,
            help='发货后多少天自动确认（默认7天）'
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='仅预览，不实际执行'
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']

        deadline = timezone.now() - timedelta(days=days)
        qs = Order.objects.filter(
            status='shipped',
            shipped_at__isnull=False,
            shipped_at__lte=deadline
        )

        count = qs.count()

        if dry_run:
            self.stdout.write(self.style.WARNING(f'[预览模式] 发现 {count} 笔订单满足自动确认条件（发货超过 {days} 天）：'))
            for order in qs:
                self.stdout.write(f"  - {order.sn} | 发货时间: {order.shipped_at.strftime('%Y-%m-%d %H:%M')} | 客户: {order.customer}")
            return

        if count == 0:
            self.stdout.write(self.style.SUCCESS('没有需要自动确认的订单'))
            return

        confirmed = 0
        for order in qs:
            order.transition_status(
                'received',
                operator=None,
                remark=f'系统自动确认收货（发货后{days}天）'
            )
            confirmed += 1
            self.stdout.write(f"  ✔ {order.sn} 已自动确认收货")

        self.stdout.write(self.style.SUCCESS(f'成功自动确认 {confirmed} 笔订单'))
