"""
总平台管理视图
包含：首页、商家管理、权限预设、非标申请审核
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from apps.accounts.models import User, Merchant, Role
from apps.orders.models import Order
from apps.products.models import CustomSpecRequest


def platform_admin_required(view_func):
    """总平台管理员装饰器"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'platform_admin':
            messages.error(request, '仅总平台管理员可访问')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@platform_admin_required
def admin_dashboard(request):
    """总平台首页"""
    merchant_count = Merchant.objects.count()
    pending_merchants = Merchant.objects.filter(status='pending').count()
    order_count = Order.objects.filter(is_submitted=True).count()
    ctx = {
        'merchant_count': merchant_count,
        'pending_merchants': pending_merchants,
        'order_count': order_count,
    }
    return render(request, 'admin_platform/dashboard.html', ctx)


@login_required
@platform_admin_required
def admin_merchants(request):
    """商家管理"""
    status_filter = request.GET.get('status')
    merchants = Merchant.objects.all()
    if status_filter:
        merchants = merchants.filter(status=status_filter)
    merchants = merchants.order_by('-created_at')
    return render(request, 'admin_platform/merchants.html', {
        'merchants': merchants,
        'status_filter': status_filter,
    })


@login_required
@platform_admin_required
def merchant_approve(request, merchant_id):
    """审核通过商家"""
    merchant = get_object_or_404(Merchant, pk=merchant_id, status='pending')
    if request.method == 'POST':
        merchant.status = 'approved'
        merchant.annual_fee_paid = True
        merchant.save(update_fields=['status', 'annual_fee_paid'])
        if merchant.admin_user:
            merchant.admin_user.is_approved = True
            merchant.admin_user.save(update_fields=['is_approved'])
        messages.success(request, f'商家 "{merchant.name}" 已通过审核')
    return redirect('admin_merchants')


@login_required
@platform_admin_required
def merchant_reject(request, merchant_id):
    """拒绝商家入驻"""
    merchant = get_object_or_404(Merchant, pk=merchant_id, status='pending')
    if request.method == 'POST':
        merchant.status = 'rejected'
        merchant.save(update_fields=['status'])
        messages.info(request, f'商家 "{merchant.name}" 已拒绝')
    return redirect('admin_merchants')


@login_required
@platform_admin_required
def merchant_freeze(request, merchant_id):
    """冻结商家"""
    merchant = get_object_or_404(Merchant, pk=merchant_id, status='approved')
    merchant.status = 'frozen'
    merchant.save(update_fields=['status'])
    messages.warning(request, f'商家 "{merchant.name}" 已被冻结')
    return redirect('admin_merchants')


@login_required
@platform_admin_required
def merchant_add(request):
    """总平台直接添加商家"""
    if request.method == 'POST':
        from apps.accounts.models import User
        name = request.POST.get('name')
        phone = request.POST.get('admin_phone')
        password = request.POST.get('admin_password')
        address = request.POST.get('address', '')
        contact_phone = request.POST.get('contact_phone', '')
        wechat = request.POST.get('customer_service_wechat', '')
        regions = request.POST.get('service_regions', '')
        try:
            if regions and regions.startswith('['):
                import json
                json.loads(regions)
        except:
            regions = ''
        max_accounts = int(request.POST.get('max_sub_accounts', 5))

        if User.objects.filter(phone=phone).exists():
            messages.error(request, '该手机号已被注册')
            return redirect('merchant_add')

        with transaction.atomic():
            merchant = Merchant.objects.create(
                name=name,
                address=address,
                service_regions=regions,
                contact_phone=contact_phone,
                customer_service_wechat=wechat,
                status='approved',
                annual_fee_paid=True,
                max_sub_accounts=max_accounts,
            )
            user = User.objects.create_user(
                username=phone,
                phone=phone,
                password=password,
                user_type='merchant_admin',
                is_approved=True,
            )
            merchant.admin_user = user
            merchant.save()
            # 创建默认角色
            for role_name, role_label in Role.ROLE_NAME_CHOICES:
                Role.objects.create(merchant=merchant, name=role_name, custom_name=role_label, permissions='')

        messages.success(request, f'商家 "{name}" 已创建成功，邀请码：{merchant.invite_code}')
        return redirect('admin_merchants')

    return render(request, 'admin_platform/merchant_add.html')


@login_required
@platform_admin_required
def merchant_edit(request, merchant_id):
    """编辑商家信息"""
    merchant = get_object_or_404(Merchant, pk=merchant_id)
    if request.method == 'POST':
        merchant.name = request.POST.get('name', merchant.name)
        merchant.max_sub_accounts = int(request.POST.get('max_sub_accounts', merchant.max_sub_accounts))
        merchant.save()
        messages.success(request, '商家信息已更新')
        return redirect('admin_merchants')
    return render(request, 'admin_platform/merchant_edit.html', {'merchant': merchant})


# ==================== 权限预设 ====================

@login_required
@platform_admin_required
def admin_roles(request):
    """全局岗位权限预设"""
    roles = Role.objects.filter(is_platform_preset=True)
    return render(request, 'admin_platform/roles.html', {'roles': roles})


@login_required
@platform_admin_required
def admin_role_edit(request, role_id):
    """编辑全局权限预设"""
    role = get_object_or_404(Role, pk=role_id, is_platform_preset=True)
    if request.method == 'POST':
        perms = request.POST.getlist('permissions')
        role.permissions = {p: True for p in perms}
        role.save(update_fields=['permissions'])
        # 同步更新所有商家的对应角色
        for mr in Role.objects.filter(name=role.name, is_platform_preset=False):
            mr.permissions = role.permissions
            mr.save(update_fields=['permissions'])
        messages.success(request, '全局权限已更新，并同步到所有商家')
        return redirect('admin_roles')
    all_permissions = [
        ('order_view', '查看订单'), ('order_audit', '审核订单'), ('order_production', '安排生产'),
        ('order_ship', '发货管理'), ('design_layout', '拼版设计'), ('member_manage', '会员管理'),
        ('factory_manage', '工厂管理'), ('spec_manage', '商品规格管理'),
        ('subaccount_manage', '子账号管理'), ('finance_manage', '财务管理'),
    ]
    current_perms = role.permissions or {}
    return render(request, 'admin_platform/role_edit.html', {
        'role': role, 'all_permissions': all_permissions, 'current_perms': current_perms,
    })


# ==================== 非标申请审核 ====================

@login_required
@platform_admin_required
def admin_spec_requests(request):
    """非标规格申请列表"""
    status_filter = request.GET.get('status')
    requests_qs = CustomSpecRequest.objects.all()
    if status_filter:
        requests_qs = requests_qs.filter(status=status_filter)
    requests_qs = requests_qs.order_by('-created_at')
    return render(request, 'admin_platform/spec_requests.html', {
        'requests': requests_qs,
        'status_filter': status_filter,
    })


@login_required
@platform_admin_required
def spec_request_approve(request, req_id):
    """通过非标申请并创建规格"""
    req = get_object_or_404(CustomSpecRequest, pk=req_id, status='pending')
    if request.method == 'POST':
        price = request.POST.get('unit_price', '0')
        ProductSpec.objects.create(
            merchant=req.merchant,
            product_name='carving_flat_gold',
            material=req.material,
            thickness=req.thickness,
            unit_price=price,
            is_platform_preset=False,
            is_active=True,
        )
        req.status = 'approved'
        req.reviewed_by = request.user
        req.save(update_fields=['status', 'reviewed_by'])
        messages.success(request, '非标规格已开通')
    return redirect('admin_spec_requests')


@login_required
@platform_admin_required
def spec_request_reject(request, req_id):
    """拒绝非标申请"""
    req = get_object_or_404(CustomSpecRequest, pk=req_id, status='pending')
    if request.method == 'POST':
        req.status = 'rejected'
        req.reviewed_by = request.user
        req.review_note = request.POST.get('review_note', '')
        req.save(update_fields=['status', 'reviewed_by', 'review_note'])
        messages.info(request, '非标申请已拒绝')
    return redirect('admin_spec_requests')
