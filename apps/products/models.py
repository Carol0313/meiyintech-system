"""
商品规格管理模型
包含：平台预设规格、商家自定义非标规格申请
价格体系：产品名称(工艺) + 材质 + 厚度 → 单价
"""

import uuid
from django.db import models


class ProductSpec(models.Model):
    """商品规格（产品名称-材质-厚度-单价）"""
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
    product_name = models.CharField('产品名称', max_length=50, choices=PRODUCT_NAME_CHOICES, default='etching_convex')
    material = models.CharField('材质', max_length=20, choices=MATERIAL_CHOICES)
    thickness = models.CharField('厚度', max_length=10, choices=THICKNESS_CHOICES)
    unit_price = models.DecimalField('单价(元/cm²)', max_digits=10, decimal_places=2, default=0)
    description = models.TextField('规格说明', blank=True)
    is_platform_preset = models.BooleanField('是否平台预设', default=True)
    is_active = models.BooleanField('是否上架', default=True)
    merchant = models.ForeignKey(
        'accounts.Merchant', on_delete=models.CASCADE, related_name='product_specs',
        verbose_name='所属商家', null=True, blank=True
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '商品规格'
        verbose_name_plural = '商品规格'
        unique_together = ['product_name', 'material', 'thickness', 'merchant']

    def __str__(self):
        return f"{self.get_product_name_display()} {self.get_material_display()} {self.thickness}mm ¥{self.unit_price}"


class CustomSpecRequest(models.Model):
    """非标规格开通申请"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        'accounts.Merchant', on_delete=models.CASCADE, related_name='custom_spec_requests',
        verbose_name='申请商家'
    )
    material = models.CharField('材料', max_length=50)
    process_type = models.CharField('加工方式', max_length=50)
    thickness = models.CharField('厚度', max_length=20)
    description = models.TextField('申请说明', blank=True)
    status = models.CharField('审核状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    reviewed_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_specs', verbose_name='审核人', limit_choices_to={'user_type': 'platform_admin'}
    )
    review_note = models.TextField('审核备注', blank=True)
    created_at = models.DateTimeField('申请时间', auto_now_add=True)
    reviewed_at = models.DateTimeField('审核时间', blank=True, null=True)

    class Meta:
        verbose_name = '非标规格申请'
        verbose_name_plural = '非标规格申请'
        ordering = ['-created_at']

    def __str__(self):
        return f"非标申请 - {self.merchant.name} {self.material}"
