"""
用户认证与角色体系模型
包含：统一用户表、终端用户资料、商家资料、商家员工资料、岗位角色
"""

import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """统一用户表，扩展Django内置User，支持多角色体系"""
    USER_TYPE_CHOICES = [
        ('platform_admin', '总平台管理员'),
        ('merchant_admin', '商家管理员'),
        ('merchant_staff', '商家员工'),
        ('customer', '终端用户'),
    ]
    user_type = models.CharField('用户类型', max_length=20, choices=USER_TYPE_CHOICES, default='customer')
    phone = models.CharField('手机号', max_length=20, unique=True, blank=True, null=True)
    avatar = models.ImageField('头像', upload_to='avatars/', blank=True, null=True)
    is_approved = models.BooleanField('是否审核通过', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    # 指定phone为登录字段
    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ['username']

    class Meta:
        verbose_name = '用户'
        verbose_name_plural = '用户'

    def __str__(self):
        return f"{self.phone or self.username} ({self.get_user_type_display()})"

    def get_profile(self):
        """获取用户的扩展资料对象"""
        if self.user_type == 'customer':
            return getattr(self, 'customer_profile', None)
        elif self.user_type in ('merchant_admin', 'merchant_staff'):
            return getattr(self, 'staff_profile', None)
        return None

    def get_effective_customer_profile(self):
        """获取实际业务用的 CustomerProfile（子账号返回父账号的）"""
        profile = getattr(self, 'customer_profile', None)
        if profile and not profile.is_main_account and profile.parent:
            return profile.parent
        return profile


class Merchant(models.Model):
    """商家（商户）资料"""
    STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
        ('frozen', '已冻结'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField('商家名称', max_length=200)
    address = models.TextField('商家地址', blank=True)
    service_regions = models.TextField('服务区域（省份）', default='', blank=True)
    contact_phone = models.CharField('联系电话', max_length=20, blank=True)
    customer_service_wechat = models.CharField('客服微信号', max_length=50, blank=True)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    annual_fee_paid = models.BooleanField('开户服务费已支付', default=False)
    invite_code = models.CharField('商家邀请码', max_length=20, unique=True, blank=True)
    max_sub_accounts = models.PositiveIntegerField('子账号上限', default=5)
    admin_user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='managed_merchant',
        verbose_name='商家管理员', null=True, blank=True
    )
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '商家'
        verbose_name_plural = '商家'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.invite_code:
            self.invite_code = self._generate_invite_code()
        super().save(*args, **kwargs)

    def _generate_invite_code(self):
        """生成唯一邀请码"""
        code = 'M' + uuid.uuid4().hex[:6].upper()
        while Merchant.objects.filter(invite_code=code).exists():
            code = 'M' + uuid.uuid4().hex[:6].upper()
        return code


class CustomerProfile(models.Model):
    """终端用户（客户）扩展资料"""
    REGISTRATION_STATUS_CHOICES = [
        ('pending', '待审核'),
        ('approved', '已通过'),
        ('rejected', '已拒绝'),
    ]
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='customer_profile',
        verbose_name='关联用户'
    )
    company_name = models.CharField('公司名称', max_length=200, blank=True)
    city = models.CharField('城市', max_length=100, blank=True)
    real_name = models.CharField('真实姓名', max_length=50, blank=True)
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name='customers',
        verbose_name='关联商家'
    )
    credit_limit = models.DecimalField('信用额度', max_digits=12, decimal_places=2, default=0)
    credit_used = models.DecimalField('已用额度', max_digits=12, decimal_places=2, default=0)
    invite_code = models.CharField('注册时填写的邀请码', max_length=20, blank=True)
    registration_status = models.CharField(
        '注册审核状态', max_length=20, choices=REGISTRATION_STATUS_CHOICES, default='pending'
    )
    rejection_reason = models.TextField('拒绝原因', blank=True)
    province = models.CharField('所在省份', max_length=50, blank=True)
    pricing_tier = models.PositiveSmallIntegerField('价格档位', default=3)
    custom_prices = models.TextField('客户自定义报价', default='{}', blank=True)
    last_order_note = models.TextField('上次订单备注', blank=True)  # 用于一键带入
    is_main_account = models.BooleanField('是否主账号', default=True)
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name='sub_accounts', verbose_name='所属主账号'
    )
    max_sub_accounts = models.PositiveIntegerField('子账号上限', default=10)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        verbose_name = '终端用户资料'
        verbose_name_plural = '终端用户资料'

    def __str__(self):
        return f"{self.real_name or self.user.phone} - {self.company_name}"

    @property
    def credit_remaining(self):
        """剩余信用额度"""
        return self.credit_limit - self.credit_used


class Role(models.Model):
    """岗位角色（商家员工角色，支持全局预设和商家自定义）"""
    ROLE_NAME_CHOICES = [
        ('customer_service', '客服岗'),
        ('designer', '设计岗'),
        ('finance', '财务岗'),
        ('production', '生产岗'),
        ('admin', '总管理员'),
    ]
    VALID_PERMISSIONS = {
        'order_view', 'order_audit', 'order_production', 'order_ship',
        'design_layout', 'member_manage', 'factory_manage', 'spec_manage',
        'subaccount_manage', 'finance_manage',
    }
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name='roles',
        verbose_name='所属商家', null=True, blank=True
    )
    name = models.CharField('角色名称', max_length=50, choices=ROLE_NAME_CHOICES)
    custom_name = models.CharField('自定义名称', max_length=50, blank=True)
    permissions = models.JSONField('权限配置', default=dict, blank=True)
    is_platform_preset = models.BooleanField('是否平台预设', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '岗位角色'
        verbose_name_plural = '岗位角色'
        unique_together = ['merchant', 'name']

    def __str__(self):
        prefix = '[平台]' if self.is_platform_preset else f'[{self.merchant}]'
        return f"{prefix} {self.get_name_display()}"

    def has_permission(self, code):
        """校验角色是否拥有指定权限码"""
        if not code or code not in self.VALID_PERMISSIONS:
            return False
        perms = self.permissions or {}
        if not isinstance(perms, dict):
            return False
        return bool(perms.get(code))

    def set_permissions(self, codes):
        """根据权限码列表设置权限，自动过滤非法 key"""
        valid = {c for c in (codes or []) if c in self.VALID_PERMISSIONS}
        self.permissions = {c: True for c in valid}


class StaffProfile(models.Model):
    """商家员工（含商家管理员）扩展资料"""
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='staff_profile',
        verbose_name='关联用户'
    )
    merchant = models.ForeignKey(
        Merchant, on_delete=models.CASCADE, related_name='staff',
        verbose_name='所属商家'
    )
    role = models.ForeignKey(
        Role, on_delete=models.SET_NULL, related_name='staff',
        verbose_name='岗位角色', null=True, blank=True
    )
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '员工资料'
        verbose_name_plural = '员工资料'

    def __str__(self):
        return f"{self.user.phone or self.user.username} - {self.merchant.name}"


class Address(models.Model):
    """收货地址"""
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='addresses',
        verbose_name='所属用户'
    )
    contact_name = models.CharField('联系人姓名', max_length=50)
    phone = models.CharField('联系电话', max_length=20)
    province = models.CharField('省份', max_length=50)
    city = models.CharField('城市', max_length=50)
    district = models.CharField('区县', max_length=50, blank=True)
    detail = models.TextField('详细地址')
    is_default = models.BooleanField('默认地址', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '收货地址'
        verbose_name_plural = '收货地址'
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        return f"{self.contact_name} {self.phone} {self.province}{self.city}"

    def save(self, *args, **kwargs):
        # 确保只有一个默认地址
        if self.is_default:
            Address.objects.filter(user=self.user).update(is_default=False)
        super().save(*args, **kwargs)
