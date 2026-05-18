"""
订单核心模型
包含：订单主表、订单明细、状态流转日志、沟通记录、拼版记录、生产照片
"""

import uuid
import os
from decimal import Decimal
from django.db import models, transaction
from django.conf import settings


class Order(models.Model):
    """订单主表"""
    STATUS_CHOICES = [
        ('draft', '草稿'),
        ('pending_confirm', '待确认'),
        ('design_confirmed', '设计确认并确认报价'),
        ('pending_payment', '待支付'),
        ('paid', '已支付'),
        ('in_production', '生产中'),
        ('shipped', '已发货'),
        ('received', '已收货'),
        ('info_error', '订单信息错误'),
        ('cancelled', '已取消'),
    ]
    DELIVERY_TYPE_CHOICES = [
        ('express', '快递'),
        ('flash', '跑腿'),
    ]
    PLATE_STATUS_CHOICES = [
        ('none', '未拼版'),
        ('auto_generated', '已自动拼版-待确认'),
        ('confirmed', '拼版已确认'),
        ('rejected', '拼版被驳回'),
    ]
    ORDER_TYPE_CHOICES = [
        ('normal', '正常单'),
        ('remake', '补版单'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sn = models.CharField('订单编号', max_length=30, unique=True, blank=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders',
        verbose_name='客户', limit_choices_to={'user_type': 'customer'}
    )
    merchant = models.ForeignKey(
        'accounts.Merchant', on_delete=models.CASCADE, related_name='orders',
        verbose_name='所属商家'
    )
    status = models.CharField('订单状态', max_length=30, choices=STATUS_CHOICES, default='draft')
    plate_status = models.CharField('拼版状态', max_length=20, choices=PLATE_STATUS_CHOICES, default='none')
    order_type = models.CharField('订单类型', max_length=20, choices=ORDER_TYPE_CHOICES, default='normal')
    total_amount = models.DecimalField('订单总金额', max_digits=12, decimal_places=2, default=0)
    urgent = models.BooleanField('是否加急', default=False)
    delivery_type = models.CharField('配送方式', max_length=20, choices=DELIVERY_TYPE_CHOICES, blank=True)
    delivery_address = models.ForeignKey(
        'accounts.Address', on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='配送地址'
    )
    factory = models.ForeignKey(
        'merchant_platform.Factory', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders', verbose_name='生产工厂'
    )
    special_requests = models.TextField('特殊要求备注', blank=True)
    preset_options = models.TextField('预定义选项', default='', blank=True)
    design_assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='design_orders', verbose_name='分配的设计人员',
        limit_choices_to={'user_type': 'merchant_staff'}
    )
    production_cycle = models.PositiveIntegerField('生产周期(小时)', blank=True, null=True)
    production_started_at = models.DateTimeField('生产开始时间', blank=True, null=True)
    production_completed_at = models.DateTimeField('生产完成时间', blank=True, null=True)
    delivery_date = models.DateTimeField('预计交货时间', blank=True, null=True)
    tracking_number = models.CharField('物流单号', max_length=100, blank=True)
    rejection_reason = models.TextField('驳回/拒绝原因', blank=True)
    # 补版单关联信息
    original_order = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='remake_orders', verbose_name='原订单'
    )
    remake_reason = models.TextField('补版原因', blank=True)
    remake_initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='initiated_remake_orders', verbose_name='补版发起人'
    )
    is_submitted = models.BooleanField('是否已提交', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)
    submitted_at = models.DateTimeField('提交时间', blank=True, null=True)

    class Meta:
        verbose_name = '订单'
        verbose_name_plural = '订单'
        ordering = ['-created_at']

    def __str__(self):
        return f"订单 {self.sn} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        if not self.sn:
            self.sn = self._generate_sn()
        super().save(*args, **kwargs)

    def _generate_sn(self):
        """生成唯一订单编号：年月日+6位随机"""
        from datetime import datetime
        prefix = datetime.now().strftime('%Y%m%d')
        suffix = uuid.uuid4().hex[:6].upper()
        return f"O{prefix}{suffix}"

    def calculate_total(self):
        """计算订单总金额（含加急费）"""
        total = sum(item.subtotal for item in self.items.all())
        if self.urgent:
            total = total * Decimal('1.10')
        return total.quantize(Decimal('0.01'))

    def update_total(self):
        """更新订单总金额"""
        self.total_amount = self.calculate_total()
        self.save(update_fields=['total_amount', 'updated_at'])

    def can_cancel(self):
        """用户是否可取消（进入生产前）"""
        return self.status in ['draft', 'pending_confirm', 'design_confirmed', 'pending_payment', 'paid']

    def get_customer_progress(self):
        """
        返回客户端可视化的进度信息
        把技术状态映射为用户友好的业务进度
        """
        steps = [
            {'key': 'submitted', 'label': '已下单', 'icon': 'bi-cart-check'},
            {'key': 'processing', 'label': '文件处理中', 'icon': 'bi-file-earmark-code'},
            {'key': 'file_ready', 'label': '文件处理完成', 'icon': 'bi-file-earmark-check'},
            {'key': 'producing', 'label': '生产中', 'icon': 'bi-gear'},
            {'key': 'produced', 'label': '已完成，待派送', 'icon': 'bi-box-seam'},
            {'key': 'shipping', 'label': '派送中', 'icon': 'bi-truck'},
            {'key': 'completed', 'label': '派送完成', 'icon': 'bi-check-circle'},
        ]

        # 根据状态+附加条件确定当前步骤
        if self.status in ['draft', 'pending_confirm']:
            current_key = 'submitted'
        elif self.status in ['design_confirmed', 'pending_payment', 'paid']:
            if self.plate_status == 'confirmed':
                current_key = 'file_ready'
            else:
                current_key = 'processing'
        elif self.status == 'in_production':
            if self.production_completed_at:
                current_key = 'produced'
            else:
                current_key = 'producing'
        elif self.status == 'shipped':
            current_key = 'shipping'
        elif self.status == 'received':
            current_key = 'completed'
        elif self.status in ['info_error', 'cancelled']:
            # 异常状态，返回已下单但标记异常
            return {'current_key': 'submitted', 'current_label': self.get_status_display(),
                    'steps': steps, 'is_abnormal': True, 'abnormal_status': self.status}
        else:
            current_key = 'submitted'

        current_idx = next((i for i, s in enumerate(steps) if s['key'] == current_key), 0)
        for i, step in enumerate(steps):
            step['done'] = i <= current_idx
            step['active'] = i == current_idx

        return {
            'current_key': current_key,
            'current_label': steps[current_idx]['label'],
            'steps': steps,
            'is_abnormal': False,
        }

    def transition_status(self, new_status, operator=None, remark=''):
        """订单状态流转，记录日志"""
        old_status = self.status
        if old_status == new_status:
            return False
        self.status = new_status
        self.save(update_fields=['status', 'updated_at'])
        OrderStatusLog.objects.create(
            order=self, from_status=old_status, to_status=new_status,
            operator=operator, remark=remark
        )
        return True

    @transaction.atomic
    def pay_with_credit(self):
        """信用额度支付"""
        profile = self.customer.customer_profile
        remaining = profile.credit_remaining
        if self.total_amount <= remaining:
            profile.credit_used += self.total_amount
            profile.save(update_fields=['credit_used'])
            self.transition_status('paid', operator=self.customer, remark='信用额度支付成功')
            return True, '支付成功'
        else:
            self.transition_status('pending_payment', operator=self.customer, remark='信用额度不足')
            return False, '信用额度不足，订单状态变为待支付'


class OrderItem(models.Model):
    """订单明细（每个独立产品）"""
    PRODUCT_NAME_CHOICES = [
        ('etching_concave', '腐蚀版 - 蚀刻凹版（压纹）'),
        ('etching_convex', '腐蚀版 - 蚀刻凸版（烫金/压凹）'),
        ('etching_bump_set', '腐蚀版 - 蚀刻击凸/凹版（配套）'),
        ('carving_flat_gold', '雕刻版 - 平雕版（烫金版）'),
        ('carving_flat_bump', '雕刻版 - 平雕版（击凸版）'),
        ('carving_relief_gold_bump', '雕刻版 - 浮雕版（烫金击凸版/烫凸一体）'),
        ('carving_relief_bump_set', '雕刻版 - 浮雕版（浮雕击凸/凹版）'),
        ('resin_mold', '树脂版 - 倒模树脂版'),
        ('resin_water', '树脂版 - 水洗树脂版'),
        ('film_alignment', '菲林 - 对位菲林'),
        ('film_uv', '菲林 - UV菲林'),
    ]
    MATERIAL_CHOICES = [
        ('magnesium', '镁'),
        ('copper', '铜'),
        ('zinc', '锌'),
        ('stainless_steel', '不锈钢'),
        ('resin', '树脂'),
        ('film', '菲林'),
    ]
    THICKNESS_CHOICES = [
        ('1.5', '1.5mm'),
        ('2.0', '2.0mm'),
        ('3.0', '3.0mm'),
        ('4.0', '4.0mm'),
        ('6.0', '6.0mm'),
        ('6.35', '6.35mm'),
        ('-', '不适用'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items',
        verbose_name='所属订单'
    )
    product_name = models.CharField('产品名称', max_length=50, choices=PRODUCT_NAME_CHOICES, default='etching_convex')
    material = models.CharField('材质', max_length=20, choices=MATERIAL_CHOICES)
    thickness = models.CharField('厚度', max_length=10, choices=THICKNESS_CHOICES)
    length_mm = models.DecimalField('长度(mm)', max_digits=10, decimal_places=2)
    width_mm = models.DecimalField('宽度(mm)', max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField('数量', default=1)
    unit_price = models.DecimalField('单价(元/cm²)', max_digits=10, decimal_places=2, default=0)
    area = models.DecimalField('面积(cm²)', max_digits=12, decimal_places=2, default=0)
    subtotal = models.DecimalField('小计(元)', max_digits=12, decimal_places=2, default=0)
    file = models.FileField('上传文件', upload_to='order_files/%Y%m/', blank=True, null=True)
    file_processed = models.BooleanField('是否处理文件', default=False)
    file_standard_checked = models.BooleanField('文件符合标准（转曲/矢量）', default=False)
    # 版类识别 + 红框数据
    plate_type = models.CharField('版类', max_length=50, blank=True, help_text='如:烫金版/压纹版/激凸版/平雕版等')
    red_box_data = models.TextField('红框识别数据', blank=True, help_text='JSON格式: [{x,y,width,height,area}]')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '订单明细'
        verbose_name_plural = '订单明细'

    def __str__(self):
        return f"{self.get_product_name_display()} {self.get_material_display()} {self.thickness}mm"

    def save(self, *args, **kwargs):
        from utils.pricing_tiers import is_etching_product
        
        if is_etching_product(self.product_name):
            # ===== 腐蚀版计价逻辑 =====
            # 四周各增加5mm版边
            length_with_border = self.length_mm + Decimal('10.0')
            width_with_border = self.width_mm + Decimal('10.0')
            single_area = (length_with_border * width_with_border) / Decimal('100.0')
            # 同一个文件制作多块版，按合拼面积计价（不按数量乘）
            self.area = single_area.quantize(Decimal('0.01'))
        else:
            # ===== 雕刻版计价逻辑 =====
            # 四周各增加10mm版边
            length_with_border = self.length_mm + Decimal('20.0')
            width_with_border = self.width_mm + Decimal('20.0')
            single_area = (length_with_border * width_with_border) / Decimal('100.0')
            # 按数量计价
            self.area = (single_area * self.quantity).quantize(Decimal('0.01'))
        
        self.subtotal = (self.area * self.unit_price).quantize(Decimal('0.01'))
        super().save(*args, **kwargs)


class OrderStatusLog(models.Model):
    """订单状态流转日志"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='status_logs',
        verbose_name='所属订单'
    )
    from_status = models.CharField('原状态', max_length=30)
    to_status = models.CharField('新状态', max_length=30)
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='操作人'
    )
    remark = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('操作时间', auto_now_add=True)

    class Meta:
        verbose_name = '状态流转日志'
        verbose_name_plural = '状态流转日志'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.order.sn}: {self.from_status} -> {self.to_status}"


class CommunicationLog(models.Model):
    """商家-客户沟通记录"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='communications',
        verbose_name='所属订单'
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        verbose_name='发送人'
    )
    content = models.TextField('沟通内容')
    created_at = models.DateTimeField('发送时间', auto_now_add=True)

    class Meta:
        verbose_name = '沟通记录'
        verbose_name_plural = '沟通记录'
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.created_at.strftime('%m-%d %H:%M')}] {self.sender}: {self.content[:30]}"


class PlateLayout(models.Model):
    """拼版记录（设计岗使用）"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.OneToOneField(
        Order, on_delete=models.CASCADE, related_name='plate_layout',
        verbose_name='所属订单'
    )
    layout_data = models.TextField('拼版布局数据', default='', blank=True)
    layout_file = models.FileField('拼版文件', upload_to='plate_layouts/%Y%m/', blank=True, null=True)
    material_usage_rate = models.FloatField('材料利用率(%)', blank=True, null=True)
    designer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='设计师'
    )
    designer_note = models.TextField('设计师备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '拼版记录'
        verbose_name_plural = '拼版记录'

    def __str__(self):
        return f"拼版 - 订单 {self.order.sn}"


class ProductionPhoto(models.Model):
    """生产/质检照片"""
    PHOTO_TYPE_CHOICES = [
        ('front', '成品正面'),
        ('inspection', '检测结果'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='production_photos',
        verbose_name='所属订单'
    )
    photo_type = models.CharField('照片类型', max_length=20, choices=PHOTO_TYPE_CHOICES)
    image = models.ImageField('图片', upload_to='production_photos/%Y%m/')
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        verbose_name='上传人'
    )
    uploaded_at = models.DateTimeField('上传时间', auto_now_add=True)

    class Meta:
        verbose_name = '生产照片'
        verbose_name_plural = '生产照片'

    def __str__(self):
        return f"{self.get_photo_type_display()} - {self.order.sn}"
