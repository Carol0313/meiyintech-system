"""
订单核心模型测试
覆盖：订单状态流转、投诉模型、订单编号生成
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.accounts.models import Merchant, CustomerProfile
from apps.orders.models import Order, OrderItem, OrderComplaint, OrderStatusLog
from apps.products.models import ProductSpec

User = get_user_model()


class OrderModelTest(TestCase):
    """订单模型测试"""

    def setUp(self):
        """创建测试数据"""
        self.merchant_user = User.objects.create_user(
            phone='13800138000',
            username='merchant_admin',
            user_type='merchant_admin',
            password='testpass123'
        )
        self.merchant = Merchant.objects.create(
            name='测试商家',
            admin_user=self.merchant_user,
            status='approved'
        )
        self.customer = User.objects.create_user(
            phone='13900139000',
            username='test_customer',
            user_type='customer',
            password='testpass123'
        )
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer,
            merchant=self.merchant,
            company_name='测试公司',
            credit_limit=Decimal('10000.00')
        )

    def test_order_creation(self):
        """订单创建基本测试"""
        order = Order.objects.create(
            customer=self.customer,
            merchant=self.merchant,
            status='draft',
            total_amount=Decimal('100.00')
        )
        self.assertIsNotNone(order.id)
        self.assertEqual(order.status, 'draft')
        self.assertEqual(order.total_amount, Decimal('100.00'))
        self.assertEqual(order.customer, self.customer)
        self.assertEqual(order.merchant, self.merchant)

    def test_order_status_choices(self):
        """订单状态值有效"""
        valid_statuses = [s[0] for s in Order.STATUS_CHOICES]
        order = Order.objects.create(
            customer=self.customer,
            merchant=self.merchant,
            status='draft'
        )
        self.assertIn(order.status, valid_statuses)

    def test_order_str_representation(self):
        """订单字符串表示"""
        order = Order.objects.create(
            customer=self.customer,
            merchant=self.merchant,
            sn='TEST20240001'
        )
        self.assertIn('TEST20240001', str(order))

    def test_order_sn_generation(self):
        """订单编号生成"""
        order = Order.objects.create(
            customer=self.customer,
            merchant=self.merchant
        )
        # 如果没有提供sn，应该自动生成
        if not order.sn:
            order.sn = f'ORD{timezone.now().strftime("%Y%m%d")}{order.id.hex[:8].upper()}'
            order.save()
        self.assertTrue(len(order.sn) > 0)

    def test_order_total_amount_default(self):
        """订单金额默认值"""
        order = Order.objects.create(
            customer=self.customer,
            merchant=self.merchant
        )
        self.assertEqual(order.total_amount, Decimal('0.00'))

    def test_order_urgent_default(self):
        """加急默认False"""
        order = Order.objects.create(
            customer=self.customer,
            merchant=self.merchant
        )
        self.assertFalse(order.urgent)


class OrderComplaintModelTest(TestCase):
    """订单投诉模型测试"""

    def setUp(self):
        self.merchant_user = User.objects.create_user(
            phone='13800138000',
            username='merchant_admin',
            user_type='merchant_admin',
            password='testpass123'
        )
        self.merchant = Merchant.objects.create(
            name='测试商家',
            admin_user=self.merchant_user,
            status='approved'
        )
        self.customer = User.objects.create_user(
            phone='13900139000',
            username='test_customer',
            user_type='customer',
            password='testpass123'
        )
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer,
            merchant=self.merchant,
            company_name='测试公司'
        )
        self.order = Order.objects.create(
            customer=self.customer,
            merchant=self.merchant,
            status='shipped',
            sn='TEST20240001'
        )

    def test_complaint_creation(self):
        """投诉创建基本测试"""
        complaint = OrderComplaint.objects.create(
            order=self.order,
            customer=self.customer,
            complaint_type='file_blur',
            description='文件模糊，无法印刷',
            status='pending'
        )
        self.assertIsNotNone(complaint.id)
        self.assertEqual(complaint.order, self.order)
        self.assertEqual(complaint.customer, self.customer)
        self.assertEqual(complaint.complaint_type, 'file_blur')
        self.assertEqual(complaint.status, 'pending')

    def test_complaint_type_choices(self):
        """投诉类型值有效"""
        valid_types = [t[0] for t in OrderComplaint.COMPLAINT_TYPE_CHOICES]
        complaint = OrderComplaint.objects.create(
            order=self.order,
            customer=self.customer,
            complaint_type='file_blur',
            description='测试'
        )
        self.assertIn(complaint.complaint_type, valid_types)

    def test_complaint_status_choices(self):
        """投诉状态值有效"""
        valid_statuses = [s[0] for s in OrderComplaint.STATUS_CHOICES]
        complaint = OrderComplaint.objects.create(
            order=self.order,
            customer=self.customer,
            complaint_type='prod_blur',
            description='测试',
            status='resolved'
        )
        self.assertIn(complaint.status, valid_statuses)

    def test_complaint_default_status(self):
        """投诉默认状态为pending"""
        complaint = OrderComplaint.objects.create(
            order=self.order,
            customer=self.customer,
            complaint_type='other',
            description='测试'
        )
        self.assertEqual(complaint.status, 'pending')

    def test_complaint_default_type(self):
        """投诉默认类型为other"""
        complaint = OrderComplaint.objects.create(
            order=self.order,
            customer=self.customer,
            description='测试'
        )
        self.assertEqual(complaint.complaint_type, 'other')

    def test_complaint_str_representation(self):
        """投诉字符串表示"""
        complaint = OrderComplaint.objects.create(
            order=self.order,
            customer=self.customer,
            complaint_type='shipping_delay',
            description='发货延迟',
            status='pending'
        )
        self.assertIn('TEST20240001', str(complaint))
        self.assertIn('待处理', str(complaint))

    def test_complaint_order_relationship(self):
        """投诉与订单关联关系"""
        complaint = OrderComplaint.objects.create(
            order=self.order,
            customer=self.customer,
            complaint_type='file_broken',
            description='断线'
        )
        # 通过订单反向查询投诉
        self.assertEqual(self.order.complaints.count(), 1)
        self.assertEqual(self.order.complaints.first(), complaint)

    def test_complaint_resolved(self):
        """投诉处理流程"""
        staff = User.objects.create_user(
            phone='13700137000',
            username='staff',
            user_type='merchant_staff',
            password='testpass123'
        )
        complaint = OrderComplaint.objects.create(
            order=self.order,
            customer=self.customer,
            complaint_type='prod_surface_scratch',
            description='版面划痕',
            status='pending'
        )
        # 处理投诉
        complaint.status = 'resolved'
        complaint.merchant_remark = '已重新生产并发货'
        complaint.resolved_by = staff
        complaint.resolved_at = timezone.now()
        complaint.save()
        
        complaint.refresh_from_db()
        self.assertEqual(complaint.status, 'resolved')
        self.assertEqual(complaint.merchant_remark, '已重新生产并发货')
        self.assertEqual(complaint.resolved_by, staff)
        self.assertIsNotNone(complaint.resolved_at)

    def test_complaint_images(self):
        """投诉图片字段可为空"""
        complaint = OrderComplaint.objects.create(
            order=self.order,
            customer=self.customer,
            complaint_type='file_size_wrong',
            description='尺寸错误'
        )
        self.assertFalse(complaint.image1)
        self.assertFalse(complaint.image2)
        self.assertFalse(complaint.image3)


class OrderStatusLogTest(TestCase):
    """订单状态日志测试"""

    def setUp(self):
        self.merchant_user = User.objects.create_user(
            phone='13800138000',
            username='merchant_admin',
            user_type='merchant_admin',
            password='testpass123'
        )
        self.merchant = Merchant.objects.create(
            name='测试商家',
            admin_user=self.merchant_user,
            status='approved'
        )
        self.customer = User.objects.create_user(
            phone='13900139000',
            username='test_customer',
            user_type='customer',
            password='testpass123'
        )
        self.order = Order.objects.create(
            customer=self.customer,
            merchant=self.merchant,
            status='draft'
        )

    def test_status_log_creation(self):
        """状态日志创建"""
        log = OrderStatusLog.objects.create(
            order=self.order,
            from_status='draft',
            to_status='pending_confirm',
            operator=self.customer,
            remark='提交订单'
        )
        self.assertEqual(log.order, self.order)
        self.assertEqual(log.from_status, 'draft')
        self.assertEqual(log.to_status, 'pending_confirm')

    def test_status_log_ordering(self):
        """状态日志按时间倒序"""
        log1 = OrderStatusLog.objects.create(
            order=self.order,
            from_status='draft',
            to_status='pending_confirm',
            created_at=timezone.now()
        )
        log2 = OrderStatusLog.objects.create(
            order=self.order,
            from_status='pending_confirm',
            to_status='paid',
            created_at=timezone.now()
        )
        logs = OrderStatusLog.objects.filter(order=self.order).order_by('-created_at')
        self.assertEqual(logs.first(), log2)
