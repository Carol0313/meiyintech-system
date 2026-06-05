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
    tracking_company = models.CharField('快递公司', max_length=50, blank=True)
    shipped_at = models.DateTimeField('发货时间', blank=True, null=True)
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
    # 对账关联
    statement = models.ForeignKey(
        'Statement', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='orders', verbose_name='所属对账单'
    )
    is_settled = models.BooleanField('是否已结清', default=False, help_text='对账单结清后标记为True，额度释放')
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
            {'key': 'completed', 'label': '已派送', 'icon': 'bi-check-circle'},
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
        elif self.status in ['shipped', 'received']:
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

    def first_item_with_file(self):
        """返回第一个有上传文件的订单项"""
        return self.items.filter(file__isnull=False).exclude(file='').first()


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
    original_file_name = models.CharField('原始文件名', max_length=255, blank=True, default='')
    file_processed = models.BooleanField('是否处理文件', default=False)
    file_standard_checked = models.BooleanField('文件符合标准（转曲/矢量）', default=False)
    is_image_file = models.BooleanField('文件是图片文件', default=False)
    # 版类识别 + 红框数据
    plate_type = models.CharField('版类', max_length=50, blank=True, help_text='如:烫金版/压纹版/激凸版/平雕版等')
    red_box_data = models.TextField('红框识别数据', blank=True, help_text='JSON格式: [{x,y,width,height,area}]')
    # 拼版批次关联（快速查询）
    plate_batch = models.ForeignKey(
        'PlateBatch', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='order_items', verbose_name='所属拼版批次'
    )
    # 制版文件（工作人员上传的处理后文件）
    plate_file = models.FileField(
        '制版文件', upload_to='plate_files/%Y%m/',
        blank=True, null=True,
        help_text='工作人员上传的处理后制版文件（PDF/AI）'
    )
    plate_file_uploaded_at = models.DateTimeField('制版文件上传时间', blank=True, null=True)
    plate_file_uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='plate_uploads', verbose_name='制版文件上传人',
        limit_choices_to={'user_type__in': ['merchant_admin', 'merchant_staff']}
    )
    # 规格组特殊要求备注（每个规格组独立）
    special_requests = models.TextField('特殊要求备注', blank=True, help_text='该规格组的特殊要求')
    # 缩放比例（金属材料上机加热会膨胀，提前缩放补偿）
    scale_ratio = models.DecimalField(
        '缩放比例(%)', max_digits=6, decimal_places=3, default=Decimal('100.000'),
        help_text='默认100%不缩放，建议99.75%补偿金属加热膨胀'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '订单明细'
        verbose_name_plural = '订单明细'

    def __str__(self):
        return f"{self.get_product_name_display()} {self.get_material_display()} {self.thickness}mm"

    def save(self, *args, **kwargs):
        from utils.pricing_tiers import is_etching_product
        import json

        if is_etching_product(self.product_name):
            # ===== 腐蚀版计价逻辑 =====
            # 检查是否有红框识别数据（多框）
            boxes = []
            if self.red_box_data:
                try:
                    parsed = json.loads(self.red_box_data)
                    if isinstance(parsed, list) and len(parsed) > 0:
                        boxes = parsed
                except (json.JSONDecodeError, TypeError):
                    pass

            if boxes:
                # 多框：遍历所有框，每个框单边+5mm版边，分别乘数量后求和
                total_area = Decimal('0')
                for box in boxes:
                    bl = Decimal(str(box.get('length_mm', 0)))
                    bw = Decimal(str(box.get('width_mm', 0)))
                    bq = int(box.get('quantity', 1))
                    if bl > 0 and bw > 0:
                        box_area = ((bl + Decimal('5.0')) * (bw + Decimal('5.0'))) / Decimal('100.0') * bq
                        total_area += box_area
                self.area = total_area.quantize(Decimal('0.01'))
            else:
                # 单框或无框：单边+5mm版边
                length_with_border = self.length_mm + Decimal('5.0')
                width_with_border = self.width_mm + Decimal('5.0')
                single_area = (length_with_border * width_with_border) / Decimal('100.0')
                self.area = (single_area * self.quantity).quantize(Decimal('0.01'))
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


class PlateBatch(models.Model):
    """拼版批次：一张物理大版，可包含多个订单的items（跨订单拼版）"""
    STATUS_CHOICES = [
        ('auto_generated', '系统自动生成'),
        ('confirmed', '已确认'),
        ('rejected', '已驳回'),
        ('in_production', '生产中'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        'accounts.Merchant', on_delete=models.CASCADE, related_name='plate_batches',
        verbose_name='所属商家'
    )
    factory = models.ForeignKey(
        'merchant_platform.Factory', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='plate_batches', verbose_name='生产工厂'
    )
    # 分组维度：同产品+同材质+同厚度才能拼到一张版
    product_name = models.CharField('产品类型', max_length=50, blank=True)
    material = models.CharField('材质', max_length=50, blank=True)
    thickness = models.CharField('厚度', max_length=20, blank=True)
    # 板材规格
    plate_spec_name = models.CharField('板材规格', max_length=50, blank=True)
    plate_width = models.FloatField('板材宽度(mm)', default=0)
    plate_height = models.FloatField('板材高度(mm)', default=0)
    # 布局数据
    layout_data = models.TextField('拼版布局数据', default='', blank=True)
    layout_image = models.ImageField('拼版效果图', upload_to='plate_layouts/%Y%m/', blank=True, null=True)
    production_pdf = models.FileField('生产PDF文件', upload_to='plate_layouts/%Y%m/', blank=True, null=True)
    usage_rate = models.FloatField('材料利用率(%)', blank=True, null=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='auto_generated')
    designer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='designed_plate_batches', verbose_name='设计师'
    )
    designer_note = models.TextField('设计师备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '拼版批次'
        verbose_name_plural = '拼版批次'
        ordering = ['-created_at']

    def __str__(self):
        return f"拼版批次 {self.id.hex[:8]} ({self.plate_spec_name})"


class PlateBatchItem(models.Model):
    """拼版批次中的具体项目（关联到订单明细）"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plate_batch = models.ForeignKey(
        PlateBatch, on_delete=models.CASCADE, related_name='items',
        verbose_name='所属拼版批次'
    )
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='plate_batch_items',
        verbose_name='所属订单'
    )
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name='plate_batch_items',
        verbose_name='订单明细'
    )
    x = models.FloatField('X坐标(mm)', default=0)
    y = models.FloatField('Y坐标(mm)', default=0)
    width = models.FloatField('放置宽度(mm)', default=0)
    height = models.FloatField('放置高度(mm)', default=0)
    rotation = models.IntegerField('旋转角度', default=0, help_text='0或90')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '拼版批次项目'
        verbose_name_plural = '拼版批次项目'

    def __str__(self):
        return f"{self.order.sn} -> {self.plate_batch.id.hex[:8]}"


class PlateLayout(models.Model):
    """拼版记录（设计岗使用）【兼容旧数据，逐步迁移到PlateBatch】"""
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
        verbose_name = '拼版记录(旧)'
        verbose_name_plural = '拼版记录(旧)'

    def __str__(self):
        return f"拼版 - 订单 {self.order.sn}"


class ProductionPhoto(models.Model):
    """生产/质检照片"""
    PHOTO_TYPE_CHOICES = [
        ('front', '成品正面'),
        ('inspection', '检测结果'),
        ('express_receipt', '快递单照片'),
        ('delivery_photo', '派送照片'),
        ('production', '生产实物照片'),
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


class DeliveryExtension(models.Model):
    """交货时间延长记录"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='delivery_extensions',
        verbose_name='所属订单'
    )
    original_date = models.DateTimeField('原交货时间', blank=True, null=True)
    new_date = models.DateTimeField('新交货时间', blank=True, null=True)
    reason = models.TextField('延长原因', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_delivery_extensions', verbose_name='操作人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '交货延期记录'
        verbose_name_plural = '交货延期记录'
        ordering = ['-created_at']

    def __str__(self):
        return f"延期 {self.order.sn}: {self.original_date} -> {self.new_date}"


class Statement(models.Model):
    """月度/周期对账单"""
    STATUS_CHOICES = [
        ('pending', '待对账'),
        ('confirmed', '已确认'),
        ('paid', '已付款'),
        ('settled', '已结清'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sn = models.CharField('对账单号', max_length=30, unique=True, blank=True)
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='statements',
        verbose_name='客户'
    )
    merchant = models.ForeignKey(
        'accounts.Merchant', on_delete=models.CASCADE, related_name='statements',
        verbose_name='所属商家'
    )
    period_start = models.DateField('账单周期开始')
    period_end = models.DateField('账单周期结束')
    total_amount = models.DecimalField('账单总金额', max_digits=12, decimal_places=2, default=0)
    status = models.CharField('对账状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    confirmed_at = models.DateTimeField('客户确认时间', blank=True, null=True)
    paid_at = models.DateTimeField('客户付款时间', blank=True, null=True)
    settled_at = models.DateTimeField('结清时间', blank=True, null=True)
    settled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='settled_statements', verbose_name='结清操作人'
    )
    remark = models.TextField('备注', blank=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '对账单'
        verbose_name_plural = '对账单'
        ordering = ['-created_at']

    def __str__(self):
        return f"对账单 {self.sn} [{self.get_status_display()}]"

    def save(self, *args, **kwargs):
        if not self.sn:
            self.sn = self._generate_sn()
        super().save(*args, **kwargs)

    def _generate_sn(self):
        from datetime import datetime
        prefix = datetime.now().strftime('%Y%m%d')
        suffix = uuid.uuid4().hex[:6].upper()
        return f"S{prefix}{suffix}"

    def calculate_total(self):
        total = sum(o.total_amount for o in self.orders.all())
        return total.quantize(Decimal('0.01'))

    def update_total(self):
        self.total_amount = self.calculate_total()
        self.save(update_fields=['total_amount', 'updated_at'])


class OrderComplaint(models.Model):
    """
    订单投诉
    客户在订单完成后（已派送/已收货）可发起投诉
    """
    STATUS_CHOICES = [
        ('pending', '待处理'),
        ('processing', '处理中'),
        ('resolved', '已解决'),
        ('rejected', '已驳回'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='complaints',
        verbose_name='关联订单'
    )
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='complaints', verbose_name='投诉客户'
    )
    # 投诉内容
    complaint_type = models.CharField('投诉类型', max_length=50, default='quality')
    description = models.TextField('投诉描述')
    # 投诉图片（最多3张）
    image1 = models.ImageField('投诉图片1', upload_to='complaints/%Y%m/', blank=True, null=True)
    image2 = models.ImageField('投诉图片2', upload_to='complaints/%Y%m/', blank=True, null=True)
    image3 = models.ImageField('投诉图片3', upload_to='complaints/%Y%m/', blank=True, null=True)
    # 处理结果
    status = models.CharField('处理状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    merchant_remark = models.TextField('商家处理备注', blank=True)
    resolved_at = models.DateTimeField('处理时间', blank=True, null=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_complaints',
        verbose_name='处理人'
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '订单投诉'
        verbose_name_plural = '订单投诉'
        ordering = ['-created_at']

    def __str__(self):
        return f"投诉 {self.order.sn} [{self.get_status_display()}]"
