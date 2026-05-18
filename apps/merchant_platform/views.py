"""
商户平台视图
包含：首页、会员管理、工厂管理、商品规格、订单管理、拼版工具、权限与子账号
"""

import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.utils import timezone
from apps.accounts.models import User, CustomerProfile, Merchant, StaffProfile, Role
from apps.orders.models import Order, OrderItem, CommunicationLog, OrderStatusLog, PlateLayout, ProductionPhoto
from apps.products.models import ProductSpec, CustomSpecRequest
from .models import Factory
from utils.plate_layout import calculate_plate_layout, auto_generate_plate_layout_for_order


def merchant_required(view_func):
    """商家管理员权限装饰器"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type not in ('merchant_admin', 'merchant_staff'):
            messages.error(request, '请先登录商家账号')
            return redirect('login')
        # 商家管理员检查 managed_merchant
        if request.user.user_type == 'merchant_admin':
            if not getattr(request.user, 'managed_merchant', None):
                messages.error(request, '您没有关联的商家')
                return redirect('login')
        else:
            # 商家员工检查 staff_profile
            profile = getattr(request.user, 'staff_profile', None)
            if not profile or not profile.is_active:
                messages.error(request, '您的员工账号未启用')
                return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


def merchant_admin_required(view_func):
    """仅商家总管理员"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'merchant_admin':
            messages.error(request, '仅商家管理员可操作')
            return redirect('merchant_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_merchant(request):
    """获取当前用户关联的商家"""
    if request.user.user_type == 'merchant_admin':
        return getattr(request.user, 'managed_merchant', None)
    profile = getattr(request.user, 'staff_profile', None)
    return profile.merchant if profile else None



# ==================== 商家首页 ====================

@login_required
@merchant_required
def merchant_dashboard(request):
    """商家首页"""
    merchant = get_merchant(request)
    today = timezone.now().date()
    pending_orders = merchant.orders.filter(status='pending_confirm').count()
    in_production = merchant.orders.filter(status='in_production').count()
    recent_orders = merchant.orders.order_by('-created_at')[:5]
    customer_count = merchant.customers.filter(registration_status='approved').count()
    ctx = {
        'merchant': merchant,
        'pending_orders': pending_orders,
        'in_production': in_production,
        'customer_count': customer_count,
        'recent_orders': recent_orders,
    }
    return render(request, 'merchant/dashboard.html', ctx)


# ==================== 账号设置 ====================

@login_required
@merchant_required
def merchant_settings(request):
    """商家账号设置"""
    merchant = get_merchant(request)
    if request.method == 'POST':
        merchant.name = request.POST.get('name', merchant.name)
        merchant.address = request.POST.get('address', merchant.address)
        merchant.contact_phone = request.POST.get('contact_phone', merchant.contact_phone)
        merchant.customer_service_wechat = request.POST.get('customer_service_wechat', merchant.customer_service_wechat)
        regions = request.POST.get('service_regions', '')
        # 尝试解析JSON格式的新数据，兼容旧格式
        try:
            if regions and regions.startswith('['):
                import json
                region_data = json.loads(regions)
                # 存储为JSON字符串
                merchant.service_regions = regions
            else:
                merchant.service_regions = regions
        except:
            merchant.service_regions = regions
        merchant.save()
        messages.success(request, '商家信息已更新')
        return redirect('merchant_settings')
    return render(request, 'merchant/settings.html', {'merchant': merchant})


# ==================== 会员管理 ====================

@login_required
@merchant_required
def member_list(request):
    """会员列表与审核"""
    merchant = get_merchant(request)
    status_filter = request.GET.get('status')
    members = merchant.customers.all()
    if status_filter:
        members = members.filter(registration_status=status_filter)
    members = members.order_by('-created_at')
    return render(request, 'merchant/member_list.html', {
        'members': members,
        'status_filter': status_filter,
    })


@login_required
@merchant_required
def member_approve(request, profile_id):
    """审核通过会员"""
    merchant = get_merchant(request)
    profile = get_object_or_404(CustomerProfile, pk=profile_id, merchant=merchant)
    if request.method == 'POST':
        profile.registration_status = 'approved'
        profile.credit_limit = Decimal(request.POST.get('credit_limit', '10000'))
        profile.save(update_fields=['registration_status', 'credit_limit'])
        profile.user.is_approved = True
        profile.user.save(update_fields=['is_approved'])
        messages.success(request, f'已通过 {profile.real_name or profile.user.phone} 的注册申请')
    return redirect('member_list')


@login_required
@merchant_required
def member_reject(request, profile_id):
    """拒绝会员注册"""
    merchant = get_merchant(request)
    profile = get_object_or_404(CustomerProfile, pk=profile_id, merchant=merchant)
    if request.method == 'POST':
        profile.registration_status = 'rejected'
        profile.rejection_reason = request.POST.get('rejection_reason', '')
        profile.save(update_fields=['registration_status', 'rejection_reason'])
        messages.info(request, '已拒绝该注册申请')
    return redirect('member_list')


@login_required
@merchant_required
def member_adjust_credit(request, profile_id):
    """调整会员信用额度"""
    merchant = get_merchant(request)
    profile = get_object_or_404(CustomerProfile, pk=profile_id, merchant=merchant, registration_status='approved')
    if request.method == 'POST':
        new_limit = Decimal(request.POST.get('credit_limit', '0'))
        profile.credit_limit = new_limit
        # 确保已用额度不超过新额度
        if profile.credit_used > new_limit:
            profile.credit_used = new_limit
        profile.save(update_fields=['credit_limit', 'credit_used'])
        messages.success(request, '信用额度已调整')
    return redirect('member_list')


# ==================== 工厂管理 ====================

@login_required
@merchant_required
def factory_list(request):
    """工厂列表"""
    merchant = get_merchant(request)
    factories = merchant.factories.all()
    return render(request, 'merchant/factory_list.html', {'factories': factories})


@login_required
@merchant_required
def factory_add(request):
    """添加工厂"""
    merchant = get_merchant(request)
    if request.method == 'POST':
        Factory.objects.create(
            merchant=merchant,
            name=request.POST.get('name'),
            address=request.POST.get('address'),
            contact_person=request.POST.get('contact_person'),
            contact_phone=request.POST.get('contact_phone'),
        )
        messages.success(request, '工厂已添加')
        return redirect('factory_list')
    return render(request, 'merchant/factory_form.html', {'title': '添加工厂'})


@login_required
@merchant_required
def factory_edit(request, pk):
    """编辑工厂"""
    merchant = get_merchant(request)
    factory = get_object_or_404(Factory, pk=pk, merchant=merchant)
    if request.method == 'POST':
        factory.name = request.POST.get('name', factory.name)
        factory.address = request.POST.get('address', factory.address)
        factory.contact_person = request.POST.get('contact_person', factory.contact_person)
        factory.contact_phone = request.POST.get('contact_phone', factory.contact_phone)
        factory.is_active = request.POST.get('is_active') == 'on'
        factory.save()
        messages.success(request, '工厂信息已更新')
        return redirect('factory_list')
    return render(request, 'merchant/factory_form.html', {'factory': factory, 'title': '编辑工厂'})


# ==================== 商品规格管理 ====================

@login_required
@merchant_required
def spec_list(request):
    """商品规格列表"""
    merchant = get_merchant(request)
    # 平台预设规格
    preset_specs = ProductSpec.objects.filter(is_platform_preset=True)
    # 商家自己的规格状态（上下架）
    merchant_specs = {s.product_name+'_'+s.material+'_'+s.thickness: s for s in ProductSpec.objects.filter(merchant=merchant)}
    specs = []
    from utils.pricing_tiers import is_etching_product, TIER_PRICES
    for ps in preset_specs:
        key = ps.product_name+'_'+ps.material+'_'+ps.thickness
        ms = merchant_specs.get(key)
        # 价格显示文本
        if is_etching_product(ps.product_name):
            price_1 = TIER_PRICES[1].get(ps.thickness, '-')
            price_2 = TIER_PRICES[2].get(ps.thickness, '-')
            price_3 = TIER_PRICES[3].get(ps.thickness, '-')
            price_display = f'1档¥{price_1} / 2档¥{price_2} / 3档¥{price_3}'
        else:
            price_display = f'¥{ps.unit_price}'
        specs.append({
            'preset': ps,
            'merchant': ms,
            'is_active': ms.is_active if ms else True,
            'price_display': price_display,
        })
    custom_requests = CustomSpecRequest.objects.filter(merchant=merchant).order_by('-created_at')[:5]
    return render(request, 'merchant/spec_list.html', {
        'specs': specs,
        'custom_requests': custom_requests,
    })


@login_required
@merchant_required
def spec_toggle(request):
    """上架/下架规格"""
    if request.method == 'POST':
        merchant = get_merchant(request)
        spec_id = request.POST.get('spec_id')
        preset = get_object_or_404(ProductSpec, pk=spec_id, is_platform_preset=True)
        # 查找或创建商家规格记录
        spec, created = ProductSpec.objects.get_or_create(
            merchant=merchant, product_name=preset.product_name, material=preset.material,
            thickness=preset.thickness,
            defaults={'unit_price': preset.unit_price, 'is_platform_preset': False, 'is_active': True}
        )
        spec.is_active = not spec.is_active
        spec.save(update_fields=['is_active'])
        return JsonResponse({'success': True, 'is_active': spec.is_active})
    return JsonResponse({'success': False}, status=400)


@login_required
@merchant_required
def spec_custom_request(request):
    """申请非标规格"""
    merchant = get_merchant(request)
    if request.method == 'POST':
        CustomSpecRequest.objects.create(
            merchant=merchant,
            material=request.POST.get('material'),
            process_type=request.POST.get('process_type', ''),
            thickness=request.POST.get('thickness'),
            description=request.POST.get('description', ''),
        )
        messages.success(request, '非标规格申请已提交，等待平台审核')
        return redirect('spec_list')
    return render(request, 'merchant/spec_custom_request.html')


# ==================== 订单管理 ====================

@login_required
@merchant_required
def merchant_orders(request):
    """商家订单列表"""
    merchant = get_merchant(request)
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    customer_query = request.GET.get('customer')
    orders = merchant.orders.filter(is_submitted=True)
    if status_filter:
        orders = orders.filter(status=status_filter)
    if date_from:
        orders = orders.filter(created_at__date__gte=date_from)
    if date_to:
        orders = orders.filter(created_at__date__lte=date_to)
    if customer_query:
        orders = orders.filter(customer__phone__icontains=customer_query)
    orders = orders.order_by('-created_at')
    return render(request, 'merchant/orders.html', {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'status_filter': status_filter,
    })


@login_required
@merchant_required
def merchant_order_detail(request, order_id):
    """商家订单详情"""
    merchant = get_merchant(request)
    order = get_object_or_404(Order, pk=order_id, merchant=merchant)
    factories = merchant.factories.filter(is_active=True)
    designers = StaffProfile.objects.filter(merchant=merchant, is_active=True, role__name='designer')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'communicate':
            content = request.POST.get('content', '')
            if content:
                CommunicationLog.objects.create(order=order, sender=request.user, content=content)
                messages.success(request, '沟通记录已添加')
        elif action == 'audit':
            # 审核通过 -> 待设计/已确认
            order.transition_status('design_confirmed', operator=request.user, remark='商家审核通过')
            # 自动拼版：为该订单生成拼版建议
            auto_generate_plate_layout_for_order(order)
            order.plate_status = 'auto_generated'
            order.save(update_fields=['plate_status'])
            messages.success(request, '订单已审核通过，系统已自动拼版，请设计师确认')
        elif action == 'assign_design':
            designer_id = request.POST.get('designer_id')
            if designer_id:
                order.design_assigned_to_id = designer_id
                order.save(update_fields=['design_assigned_to'])
                order.transition_status('design_confirmed', operator=request.user, remark='已分配设计岗')
                messages.success(request, '已分配给设计人员')
        elif action == 'arrange_production':
            factory_id = request.POST.get('factory_id')
            cycle = request.POST.get('production_cycle')
            if factory_id and cycle:
                # 检查是否已完成拼版
                plate_layout = getattr(order, 'plate_layout', None)
                if not plate_layout or not plate_layout.layout_data:
                    messages.error(request, '该订单尚未完成拼版，请先安排设计师拼版')
                    return redirect('merchant_order_detail', order_id=order_id)
                order.factory_id = factory_id
                order.production_cycle = int(cycle)
                order.save(update_fields=['factory', 'production_cycle'])
                order.transition_status('in_production', operator=request.user, remark='已安排生产')
                messages.success(request, '生产已安排，工厂将在下个整点收到订单')
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            order.rejection_reason = reason
            order.save(update_fields=['rejection_reason'])
            order.transition_status('info_error', operator=request.user, remark=f'无法生产: {reason}')
            messages.info(request, '订单已驳回')
        elif action == 'ship':
            order.tracking_number = request.POST.get('tracking_number', '')
            order.save(update_fields=['tracking_number'])
            order.transition_status('shipped', operator=request.user, remark='已发货')
            messages.success(request, '订单已发货')
        elif action == 'mark_paid':
            order.transition_status('paid', operator=request.user, remark='线下支付已确认')
            # 扣除信用额度或记录
            profile = order.customer.customer_profile
            if profile.credit_remaining >= order.total_amount:
                profile.credit_used += order.total_amount
                profile.save(update_fields=['credit_used'])
            messages.success(request, '已标记为已支付')
        return redirect('merchant_order_detail', order_id=order_id)
    return render(request, 'merchant/order_detail.html', {
        'order': order,
        'factories': factories,
        'designers': designers,
    })


@login_required
@merchant_required
def upload_production_photo(request, order_id):
    """上传生产/质检照片"""
    merchant = get_merchant(request)
    order = get_object_or_404(Order, pk=order_id, merchant=merchant)
    if request.method == 'POST' and request.FILES.get('photo'):
        ProductionPhoto.objects.create(
            order=order,
            photo_type=request.POST.get('photo_type', 'front'),
            image=request.FILES['photo'],
            uploaded_by=request.user,
        )
        messages.success(request, '照片已上传')
    return redirect('merchant_order_detail', order_id=order_id)


# ==================== 拼版工具 ====================

@login_required
@merchant_required
def plate_layout_orders(request):
    """设计岗：获取待拼版/待确认订单"""
    merchant = get_merchant(request)
    # 需要拼版的订单状态：design_confirmed（商家审核后）或 paid（客户信用额度支付后直接到账）
    eligible_statuses = ['design_confirmed', 'paid']
    # 设计岗只能看到自己的，管理员看到所有
    if request.user.user_type == 'merchant_staff' and request.user.staff_profile.role.name == 'designer':
        orders = merchant.orders.filter(design_assigned_to=request.user, status__in=eligible_statuses)
    else:
        orders = merchant.orders.filter(status__in=eligible_statuses)
    orders = orders.order_by('-created_at')
    # 分组：待确认拼版（系统自动生成） vs 待手动拼版（还未生成）
    pending_confirm = orders.filter(plate_status='auto_generated')
    pending_work = orders.filter(plate_status='none')
    return render(request, 'merchant/plate_layout_orders.html', {
        'pending_confirm': pending_confirm,
        'pending_work': pending_work,
    })


@login_required
@merchant_required
def plate_layout_work(request, order_id):
    """拼版工作台"""
    merchant = get_merchant(request)
    order = get_object_or_404(Order, pk=order_id, merchant=merchant)
    items = order.items.all()
    # 获取尺寸信息用于拼版算法
    rects = []
    for item in items:
        if item.length_mm and item.width_mm:
            rects.append({
                'id': str(item.id),
                'width': float(item.length_mm),
                'height': float(item.width_mm),
                'label': f"{item.get_material_display()}",
            })
    # 拼版建议
    suggestion = None
    if rects:
        suggestion = calculate_plate_layout(rects, plate_width=600, plate_height=1000)
    layout = getattr(order, 'plate_layout', None)

    # 解析已保存的拼版数据（JSON字符串 -> dict）用于模板展示
    layout_data_parsed = {}
    if layout and layout.layout_data:
        try:
            layout_data_parsed = json.loads(layout.layout_data)
        except Exception:
            layout_data_parsed = {}
    # 如果已有保存的拼版数据，优先用它作为画布展示
    if layout_data_parsed:
        suggestion = layout_data_parsed

    if request.method == 'POST':
        action = request.POST.get('action', 'save')

        if action == 'save':
            data = json.loads(request.POST.get('layout_data', '{}'))
            note = request.POST.get('designer_note', '')
            layout_json = json.dumps(data, ensure_ascii=False)
            if layout:
                layout.layout_data = layout_json
                layout.designer_note = note
                layout.designer = request.user
                layout.save()
            else:
                PlateLayout.objects.create(order=order, layout_data=layout_json, designer_note=note, designer=request.user)
            messages.success(request, '拼版布局已保存')
            return redirect('plate_layout_orders')

        elif action == 'confirm_plate':
            # 设计师确认拼版：保存当前布局，确认拼版，自动下发到工厂
            data = json.loads(request.POST.get('layout_data', '{}'))
            note = request.POST.get('designer_note', '')
            layout_json = json.dumps(data, ensure_ascii=False)
            if layout:
                layout.layout_data = layout_json
                layout.designer_note = note
                layout.designer = request.user
                layout.save()
            else:
                PlateLayout.objects.create(order=order, layout_data=layout_json, designer_note=note, designer=request.user)
            # 确认拼版状态
            order.plate_status = 'confirmed'
            # 自动分配给第一个活跃工厂
            default_factory = merchant.factories.filter(is_active=True).first()
            if default_factory:
                order.factory = default_factory
            order.save(update_fields=['plate_status', 'factory'])
            # 状态变为生产中，工厂立刻收到
            order.transition_status('in_production', operator=request.user, remark='设计师已确认拼版，自动下发工厂生产')
            messages.success(request, f'订单 {order.sn} 拼版已确认，已自动下发到工厂生产')
            return redirect('plate_layout_orders')

        elif action == 'reject_plate':
            reason = request.POST.get('reject_reason', '')
            order.plate_status = 'rejected'
            order.save(update_fields=['plate_status'])
            OrderStatusLog.objects.create(
                order=order, from_status=order.status, to_status=order.status,
                operator=request.user, remark=f'设计师驳回拼版: {reason}'
            )
            messages.warning(request, f'订单 {order.sn} 拼版已驳回，原因：{reason}')
            return redirect('plate_layout_orders')

    # PDF预检报告
    preflight_reports = []
    import os
    from django.conf import settings
    from utils.pdf_preflight import preflight_pdf, generate_preflight_report_html
    for item in items:
        if item.file:
            try:
                file_path = os.path.join(settings.MEDIA_ROOT, item.file.name)
                if os.path.exists(file_path):
                    report = preflight_pdf(file_path, min_line_width_mm=0.12)
                    preflight_reports.append({
                        'item_id': str(item.id),
                        'item_label': f"{item.get_product_name_display()} #{item.id[:8]}",
                        'report_html': generate_preflight_report_html(report),
                        'pass': report['pass'],
                    })
            except Exception as e:
                pass

    return render(request, 'merchant/plate_layout_work.html', {
        'order': order,
        'items': items,
        'suggestion': suggestion,
        'suggestion_json': json.dumps(suggestion, ensure_ascii=False) if suggestion else '{}',
        'layout': layout,
        'layout_data_parsed': layout_data_parsed,
        'preflight_reports': preflight_reports,
    })


# ==================== 岗位权限与子账号 ====================

@login_required
@merchant_admin_required
def role_list(request):
    """岗位与权限管理"""
    merchant = get_merchant(request)
    roles = merchant.roles.all()
    return render(request, 'merchant/role_list.html', {'roles': roles})


@login_required
@merchant_admin_required
def role_edit(request, role_id):
    """编辑角色权限"""
    merchant = get_merchant(request)
    role = get_object_or_404(Role, pk=role_id, merchant=merchant)
    if request.method == 'POST':
        perms = request.POST.getlist('permissions')
        role.permissions = {p: True for p in perms}
        role.save(update_fields=['permissions'])
        messages.success(request, '权限已更新')
        return redirect('role_list')
    all_permissions = [
        ('order_view', '查看订单'),
        ('order_audit', '审核订单'),
        ('order_production', '安排生产'),
        ('order_ship', '发货管理'),
        ('design_layout', '拼版设计'),
        ('member_manage', '会员管理'),
        ('factory_manage', '工厂管理'),
        ('spec_manage', '商品规格管理'),
        ('subaccount_manage', '子账号管理'),
        ('finance_manage', '财务管理'),
    ]
    current_perms = role.permissions or {}
    return render(request, 'merchant/role_edit.html', {
        'role': role,
        'all_permissions': all_permissions,
        'current_perms': current_perms,
    })


@login_required
@merchant_admin_required
def subaccount_list(request):
    """子账号管理"""
    merchant = get_merchant(request)
    staff = merchant.staff.filter(user__user_type='merchant_staff')
    return render(request, 'merchant/subaccount_list.html', {
        'staff': staff,
        'max_count': merchant.max_sub_accounts,
        'current_count': staff.count(),
    })


@login_required
@merchant_admin_required
def subaccount_add(request):
    """新增子账号"""
    merchant = get_merchant(request)
    if merchant.staff.filter(user__user_type='merchant_staff').count() >= merchant.max_sub_accounts:
        messages.error(request, f'子账号数量已达上限 ({merchant.max_sub_accounts})')
        return redirect('subaccount_list')
    roles = merchant.roles.all()
    if request.method == 'POST':
        phone = request.POST.get('phone')
        username = request.POST.get('username')
        password = request.POST.get('password')
        role_id = request.POST.get('role_id')
        if User.objects.filter(phone=phone).exists():
            messages.error(request, '该手机号已被注册')
        else:
            user = User.objects.create_user(
                username=username, phone=phone, password=password,
                user_type='merchant_staff', is_approved=True
            )
            StaffProfile.objects.create(
                user=user, merchant=merchant,
                role_id=role_id if role_id else None
            )
            messages.success(request, '子账号创建成功')
            return redirect('subaccount_list')
    return render(request, 'merchant/subaccount_form.html', {'roles': roles, 'title': '新增子账号'})


@login_required
@merchant_admin_required
def subaccount_edit(request, staff_id):
    """编辑子账号"""
    merchant = get_merchant(request)
    staff = get_object_or_404(StaffProfile, pk=staff_id, merchant=merchant)
    roles = merchant.roles.all()
    if request.method == 'POST':
        staff.is_active = request.POST.get('is_active') == 'on'
        staff.role_id = request.POST.get('role_id') or None
        staff.save()
        messages.success(request, '子账号已更新')
        return redirect('subaccount_list')
    return render(request, 'merchant/subaccount_form.html', {
        'staff': staff, 'roles': roles, 'title': '编辑子账号'
    })


# ==================== 工厂生产看板 ====================

@login_required
@merchant_required
def factory_production_board(request):
    """工厂生产看板 - 显示待生产/生产中/已完成的订单"""
    merchant = get_merchant(request)
    # 当前用户可见的工厂（merchant_admin看全部，staff看全部工厂的订单）
    factories = merchant.factories.filter(is_active=True)
    factory_ids = list(factories.values_list('id', flat=True))

    # 按生产状态分组
    base_qs = Order.objects.filter(merchant=merchant, factory_id__in=factory_ids, status='in_production')

    # 待生产：未开始
    pending_orders = base_qs.filter(production_started_at__isnull=True).order_by('created_at')
    # 生产中：已开始但未完成
    active_orders = base_qs.filter(production_started_at__isnull=False, production_completed_at__isnull=True).order_by('production_started_at')
    # 已完成：生产完成待发货
    completed_orders = base_qs.filter(production_completed_at__isnull=False).order_by('-production_completed_at')

    # 处理POST操作
    if request.method == 'POST':
        action = request.POST.get('action')
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, pk=order_id, merchant=merchant)

        if action == 'start':
            order.production_started_at = timezone.now()
            order.save(update_fields=['production_started_at'])
            OrderStatusLog.objects.create(
                order=order, from_status='in_production', to_status='in_production',
                operator=request.user, remark='工厂开始生产'
            )
            messages.success(request, f'订单 {order.sn} 已开始生产')
        elif action == 'complete':
            order.production_completed_at = timezone.now()
            order.save(update_fields=['production_completed_at'])
            # 上传生产照片
            if request.FILES.get('photo'):
                ProductionPhoto.objects.create(
                    order=order,
                    photo_type='inspection',
                    image=request.FILES['photo'],
                    uploaded_by=request.user
                )
            OrderStatusLog.objects.create(
                order=order, from_status='in_production', to_status='in_production',
                operator=request.user, remark='工厂生产完成'
            )
            messages.success(request, f'订单 {order.sn} 已标记生产完成')
        return redirect('factory_production_board')

    # 计算下次刷新时间（整点刷新，下午1点开始工作）
    now = timezone.now()
    next_refresh = now.replace(minute=0, second=0, microsecond=0)
    if next_refresh <= now:
        next_refresh = next_refresh.replace(hour=(next_refresh.hour + 1) % 24)
    seconds_until_refresh = int((next_refresh - now).total_seconds())

    ctx = {
        'pending_orders': pending_orders,
        'active_orders': active_orders,
        'completed_orders': completed_orders,
        'factories': factories,
        'now': now,
        'next_refresh': next_refresh,
        'seconds_until_refresh': seconds_until_refresh,
        'stats': {
            'pending': pending_orders.count(),
            'active': active_orders.count(),
            'completed': completed_orders.count(),
        }
    }
    return render(request, 'merchant/factory_production_board.html', ctx)


# ==================== 补版管理 ====================

def _can_initiate_remake(user):
    """判断当前用户是否有权限发起补版（客服/设计/管理员）"""
    if user.user_type == 'merchant_admin':
        return True
    if user.user_type == 'merchant_staff':
        profile = getattr(user, 'staff_profile', None)
        if profile and profile.is_active and profile.role:
            return profile.role.name in ('customer_service', 'designer', 'admin')
    return False


@login_required
@merchant_required
def remake_order_create(request, order_id):
    """发起补版单：复制原订单项，金额设为0，由客服/设计岗操作"""
    merchant = get_merchant(request)
    original_order = get_object_or_404(Order, pk=order_id, merchant=merchant)

    if not _can_initiate_remake(request.user):
        messages.error(request, '仅客服/设计/管理员可发起补版')
        return redirect('merchant_order_detail', order_id=order_id)

    # 补版仅对已完成或已发货的订单开放
    if original_order.status not in ('shipped', 'received', 'in_production'):
        messages.error(request, '当前订单状态不支持补版')
        return redirect('merchant_order_detail', order_id=order_id)

    if request.method == 'POST':
        item_ids = request.POST.getlist('item_ids')
        remake_reason = request.POST.get('remake_reason', '').strip()
        if not item_ids:
            messages.error(request, '请至少选择一项需要补做的产品')
            return redirect('remake_order_create', order_id=order_id)
        if not remake_reason:
            messages.error(request, '请填写补版原因')
            return redirect('remake_order_create', order_id=order_id)

        with transaction.atomic():
            # 创建补版订单
            remake_order = Order.objects.create(
                customer=original_order.customer,
                merchant=merchant,
                order_type='remake',
                original_order=original_order,
                remake_reason=remake_reason,
                remake_initiator=request.user,
                status='pending_confirm',
                is_submitted=True,
                urgent=False,
                delivery_type=original_order.delivery_type,
                delivery_address=original_order.delivery_address,
                total_amount=Decimal('0'),
            )
            # 复制选中的订单明细，金额强制为0
            for item in original_order.items.filter(id__in=item_ids):
                new_item = OrderItem.objects.create(
                    order=remake_order,
                    product_name=item.product_name,
                    material=item.material,
                    thickness=item.thickness,
                    length_mm=item.length_mm,
                    width_mm=item.width_mm,
                    quantity=item.quantity,
                    unit_price=Decimal('0'),
                    area=item.area,  # 面积按原尺寸正常计算
                    subtotal=Decimal('0'),
                    file=item.file,
                    file_processed=item.file_processed,
                    file_standard_checked=item.file_standard_checked,
                    plate_type=item.plate_type,
                )
            # 记录日志
            OrderStatusLog.objects.create(
                order=remake_order,
                from_status='',
                to_status='pending_confirm',
                operator=request.user,
                remark=f'补版单：关联原订单 {original_order.sn}，原因：{remake_reason}'
            )
            # 同时在原订单也记录
            OrderStatusLog.objects.create(
                order=original_order,
                from_status=original_order.status,
                to_status=original_order.status,
                operator=request.user,
                remark=f'发起补版单 {remake_order.sn}，原因：{remake_reason}'
            )
        messages.success(request, f'补版单 {remake_order.sn} 已创建，金额为0元')
        return redirect('merchant_order_detail', order_id=remake_order.id)

    return render(request, 'merchant/remake_form.html', {
        'original_order': original_order,
        'items': original_order.items.all(),
    })
