"""
终端用户平台视图
包含：首页、下单流程（多步骤）、订单管理、支付
"""

import json, uuid, os, fitz
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction, models
from django.db.models import Sum, Count
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpResponse
from django.utils import timezone
from apps.accounts.models import User, CustomerProfile, Address
from apps.orders.models import Order, OrderItem, OrderStatusLog, CommunicationLog, Statement, OrderComplaint
from apps.products.models import ProductSpec
from apps.merchant_platform.models import Factory


def customer_required(view_func):
    """装饰器：仅终端用户可访问"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, '请先以终端用户身份登录')
            return redirect('login')
        if request.user.user_type != 'customer':
            return render(request, 'common/account_unauthorized.html', {
                'message': '请先以终端用户身份登录',
                'can_logout': True,
            })
        profile = getattr(request.user, 'customer_profile', None)
        if not profile or profile.registration_status != 'approved':
            msg = '您的账号尚未通过商家审核，请联系商家管理员处理。'
            if profile and profile.registration_status == 'rejected':
                msg = '您的账号审核未通过，请联系商家管理员了解原因。'
            elif profile and profile.registration_status == 'pending':
                msg = '您的账号正在审核中，请耐心等待商家管理员审核。'
            return render(request, 'common/account_unauthorized.html', {
                'message': msg,
                'can_logout': True,
            })
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@customer_required
def customer_dashboard(request):
    """终端用户首页"""
    profile = request.user.get_effective_customer_profile()
    recent_orders = request.user.orders.filter(is_submitted=True).order_by('-created_at')[:5]

    # 每日一句（印刷制版行业）
    import datetime
    quotes = [
        "品质是印刷的生命，细节决定成败。",
        "每一张版都是承诺，每一次印刷都是信任。",
        "好的制版，是成功印刷的第一步。",
        "精准制版，成就完美印刷。",
        "用心做版，以质取胜。",
        "工匠精神，铸就卓越品质。",
        "印刷有价，信誉无价。",
        "版材虽轻，责任千斤。",
        "精益求精，版版出色。",
        "以质量求生存，以信誉求发展。",
        "色差一分，客户伤心；精准一毫，客户放心。",
        "好版出好活，精工出细活。",
        "客户的要求是标准，自己的要求是品质。",
        "今天的高品质，是明天的好口碑。",
        "做版如做人，认真是根本。",
    ]
    day_index = datetime.date.today().toordinal() % len(quotes)
    daily_quote = quotes[day_index]

    ctx = {
        'profile': profile,
        'recent_orders': recent_orders,
        'order_count': request.user.orders.filter(is_submitted=True).count(),
        'daily_quote': daily_quote,
    }
    return render(request, 'customer/dashboard.html', ctx)


# ==================== 下单流程 ====================

@login_required
@customer_required
def place_order(request):
    """单页下单：产品选择 -> 上传文件 -> 自动识别尺寸 -> 确认提交"""
    profile = request.user.get_effective_customer_profile()
    from utils.pricing_tiers import get_customer_price, is_etching_product, get_product_category
    tier = profile.pricing_tier

    if request.method == 'POST':
        return _handle_quick_order_post(request, profile, tier)

    # GET: 构建规格数据
    specs = ProductSpec.objects.filter(is_platform_preset=True, is_active=True)
    spec_data = {}
    for s in specs:
        category = get_product_category(s.product_name)
        if category not in spec_data:
            spec_data[category] = {'label': category, 'products': {}}
        prod_key = s.product_name
        if prod_key not in spec_data[category]['products']:
            spec_data[category]['products'][prod_key] = {
                'label': s.get_product_name_display(),
                'materials': {}
            }
        mat_key = s.material
        if mat_key not in spec_data[category]['products'][prod_key]['materials']:
            spec_data[category]['products'][prod_key]['materials'][mat_key] = {
                'label': s.get_material_display(),
                'thicknesses': []
            }
        price = str(get_customer_price(profile, s.product_name, s.material, s.thickness))
        spec_data[category]['products'][prod_key]['materials'][mat_key]['thicknesses'].append({
            'value': s.thickness,
            'label': s.get_thickness_display(),
            'price': price,
        })

    # 排序：腐蚀版放第一
    if '腐蚀版' in spec_data:
        ordered = {'腐蚀版': spec_data.pop('腐蚀版')}
        ordered.update(spec_data)
        spec_data = ordered

    addresses = request.user.addresses.all()
    default_address = addresses.filter(is_default=True).first()
    import json
    return render(request, 'customer/place_order.html', {
        'spec_data_json': json.dumps(spec_data),
        'addresses': addresses,
        'default_address': default_address,
        'last_note': profile.last_order_note,
    })


@login_required
@customer_required
def order_step1(request):
    """步骤1：参数规格选择（产品名称→材质→厚度→自动价格）"""
    if request.method == 'POST':
        draft = {
            'id': str(uuid.uuid4()),
            'product_name': request.POST.get('product_name'),
            'material': request.POST.get('material'),
            'thickness': request.POST.get('thickness'),
            'length_mm': request.POST.get('length_mm'),
            'width_mm': request.POST.get('width_mm'),
            'quantity': int(request.POST.get('quantity', 1)),
            'unit_price': request.POST.get('unit_price', '0'),
            'boxes_json': request.POST.get('boxes_json', ''),
        }
        request.session[f"draft_{draft['id']}"] = draft
        return redirect('order_step2', draft_id=draft['id'])
    # 按【产品大类→细分产品→材质→厚度】构建两级规格数据
    from utils.pricing_tiers import get_customer_price, is_etching_product, get_product_category
    profile = request.user.get_effective_customer_profile()
    tier = profile.pricing_tier
    specs = ProductSpec.objects.filter(is_platform_preset=True, is_active=True)
    spec_data = {}
    for s in specs:
        category = get_product_category(s.product_name)
        if category not in spec_data:
            spec_data[category] = {'label': category, 'products': {}}
        prod_key = s.product_name
        if prod_key not in spec_data[category]['products']:
            spec_data[category]['products'][prod_key] = {
                'label': s.get_product_name_display(),
                'materials': {}
            }
        mat_key = s.material
        if mat_key not in spec_data[category]['products'][prod_key]['materials']:
            spec_data[category]['products'][prod_key]['materials'][mat_key] = {
                'label': s.get_material_display(),
                'thicknesses': []
            }
        price = str(get_customer_price(profile, s.product_name, s.material, s.thickness))
        spec_data[category]['products'][prod_key]['materials'][mat_key]['thicknesses'].append({
            'value': s.thickness,
            'label': s.get_thickness_display(),
            'price': price,
        })
    # 排序：腐蚀版放第一
    if '腐蚀版' in spec_data:
        ordered = {'腐蚀版': spec_data.pop('腐蚀版')}
        ordered.update(spec_data)
        spec_data = ordered
    import json
    return render(request, 'customer/order_step1.html', {'spec_data_json': json.dumps(spec_data)})


@login_required
@customer_required
def order_step2(request, draft_id):
    """步骤2：文件上传"""
    draft = request.session.get(f"draft_{draft_id}")
    if not draft:
        messages.error(request, '订单草稿已过期，请重新下单')
        return redirect('place_order')
    if request.method == 'POST':
        file_type = request.POST.get('file_type', 'processed')
        draft['file_standard_checked'] = (file_type == 'standard')
        draft['file_processed'] = (file_type == 'processed')
        draft['is_image_file'] = (file_type == 'image')
        if request.FILES.get('pdf_file'):
            file = request.FILES['pdf_file']
            ext = os.path.splitext(file.name)[1].lower()
            if ext != '.pdf':
                messages.error(request, '仅支持PDF格式文件')
                return redirect('order_step2', draft_id=draft_id)
            filename = f"order_files/{request.user.id}/{uuid.uuid4().hex}{ext}"
            path = default_storage.save(filename, file)
            # PDF转纯黑处理（制版需要）
            try:
                from utils.pdf_processor import convert_pdf_to_black, _get_pdf_local_path
                local_path = _get_pdf_local_path(path)
                if local_path:
                    convert_pdf_to_black(local_path)
                    # 如果原始文件在 OSS，把处理后的文件上传回去
                    if local_path != os.path.join(settings.MEDIA_ROOT, path):
                        with open(local_path, 'rb') as f:
                            default_storage.save(path, f)
                        os.unlink(local_path)
            except Exception:
                pass
            draft['file_path'] = path
            draft['file_name'] = file.name
        request.session[f"draft_{draft_id}"] = draft
        if draft['file_processed']:
            return redirect('order_step3', draft_id=draft_id)
        else:
            return redirect('order_step5', draft_id=draft_id)
    return render(request, 'customer/order_step2.html', {'draft': draft})


@login_required
@customer_required
def order_step3(request, draft_id):
    """步骤3：面积计算（仅处理文件时）"""
    draft = request.session.get(f"draft_{draft_id}")
    if not draft or not draft.get('file_path'):
        messages.error(request, '文件信息缺失')
        return redirect('place_order')
    # 计算PDF面积（优先红框，其次页面尺寸）
    area = _calculate_pdf_area(draft['file_path'])
    draft['area'] = str(area)
    request.session[f"draft_{draft_id}"] = draft

    # 获取PDF页面尺寸，与用户填写尺寸做差异对比
    pdf_w_mm, pdf_h_mm = _get_pdf_page_dimensions(draft['file_path'])
    user_l = float(draft.get('length_mm', 0) or 0)
    user_w = float(draft.get('width_mm', 0) or 0)

    # 差异预警：如果PDF页面尺寸与用户填写尺寸相差超过20%，提示核对
    size_mismatch = False
    mismatch_msg = ''
    if pdf_w_mm and pdf_h_mm and user_l > 0 and user_w > 0:
        pdf_ratio = max(pdf_w_mm, pdf_h_mm) / min(pdf_w_mm, pdf_h_mm)
        user_ratio = max(user_l, user_w) / min(user_l, user_w)
        # 对比长边和短边
        pdf_sides = sorted([pdf_w_mm, pdf_h_mm])
        user_sides = sorted([user_l, user_w])
        long_diff = abs(pdf_sides[1] - user_sides[1]) / user_sides[1] if user_sides[1] > 0 else 0
        short_diff = abs(pdf_sides[0] - user_sides[0]) / user_sides[0] if user_sides[0] > 0 else 0
        if long_diff > 0.20 or short_diff > 0.20:
            size_mismatch = True
            mismatch_msg = (
                f'PDF页面尺寸为 {pdf_w_mm/10:.1f}×{pdf_h_mm/10:.1f}cm，'
                f'与您填写的 {user_l/10:.1f}×{user_w/10:.1f}cm 差异较大。'
                f'系统优先按红框识别或PDF页面计算参考面积，实际制版尺寸以您填写的规格为准。'
            )

    return render(request, 'customer/order_step3.html', {
        'draft': draft,
        'area': area,
        'pdf_width_cm': round(pdf_w_mm / 10, 1) if pdf_w_mm else None,
        'pdf_height_cm': round(pdf_h_mm / 10, 1) if pdf_h_mm else None,
        'size_mismatch': size_mismatch,
        'mismatch_msg': mismatch_msg,
    })


@login_required
@customer_required
def order_step4(request, draft_id):
    """步骤4：效果预览（仅处理文件时）"""
    draft = request.session.get(f"draft_{draft_id}")
    if not draft or not draft.get('file_path'):
        messages.error(request, '文件信息缺失')
        return redirect('place_order')
    # 生成PDF第一页纯黑预览图
    preview_url = None
    preview_filename = f"previews/{draft_id}.png"
    preview_path = os.path.join(settings.MEDIA_ROOT, preview_filename)
    os.makedirs(os.path.dirname(preview_path), exist_ok=True)
    try:
        from utils.pdf_processor import generate_pdf_preview
        preview_url = generate_pdf_preview(draft['file_path'], preview_filename, dpi=150, black_only=True)
        draft['preview_url'] = preview_url
        request.session[f"draft_{draft_id}"] = draft
    except Exception:
        pass
    return render(request, 'customer/order_step4.html', {'draft': draft, 'preview_url': preview_url})


@login_required
@customer_required
def order_step5(request, draft_id):
    """步骤5：特殊要求填写"""
    draft = request.session.get(f"draft_{draft_id}")
    if not draft:
        messages.error(request, '订单草稿已过期')
        return redirect('place_order')
    profile = request.user.get_effective_customer_profile()
    preset_options = [
        ('urgent', '加急'),
        ('no_cut', '不需要裁切'),
        ('double_check', '要求复检'),
        ('special_pack', '特殊包装'),
    ]
    if request.method == 'POST':
        draft['special_requests'] = request.POST.get('special_requests', '')
        draft['preset_options'] = request.POST.getlist('preset_options')
        # 保存最后备注
        if draft['special_requests']:
            profile.last_order_note = draft['special_requests']
            profile.save(update_fields=['last_order_note'])
        request.session[f"draft_{draft_id}"] = draft
        return redirect('order_step6', draft_id=draft_id)
    return render(request, 'customer/order_step5.html', {
        'draft': draft,
        'preset_options': preset_options,
        'last_note': profile.last_order_note,
    })


@login_required
@customer_required
def order_step6(request, draft_id):
    """步骤6：交货时间选择"""
    draft = request.session.get(f"draft_{draft_id}")
    if not draft:
        messages.error(request, '订单草稿已过期')
        return redirect('place_order')
    if request.method == 'POST':
        draft['urgent'] = request.POST.get('urgent') == 'on'
        request.session[f"draft_{draft_id}"] = draft
        return redirect('order_step7', draft_id=draft_id)
    return render(request, 'customer/order_step6.html', {'draft': draft})


@login_required
@customer_required
def order_step7(request, draft_id):
    """步骤7：配送方式选择"""
    draft = request.session.get(f"draft_{draft_id}")
    if not draft:
        messages.error(request, '订单草稿已过期')
        return redirect('place_order')
    addresses = request.user.addresses.all()
    default_address = addresses.filter(is_default=True).first()
    if request.method == 'POST':
        draft['delivery_type'] = request.POST.get('delivery_type')
        draft['address_id'] = request.POST.get('address_id')
        request.session[f"draft_{draft_id}"] = draft
        # 添加到草稿列表
        session_key = f"order_drafts_{request.user.id}"
        drafts = request.session.get(session_key, [])
        draft_id_str = str(draft_id)
        if draft_id_str not in [str(d['id']) for d in drafts]:
            drafts.append({'id': draft_id_str, 'summary': _draft_summary(draft)})
            request.session[session_key] = drafts
        messages.success(request, '订单草稿已保存')
        return redirect('place_order')
    return render(request, 'customer/order_step7.html', {
        'draft': draft,
        'addresses': addresses,
        'default_address': default_address,
    })


@login_required
@customer_required
def remove_draft(request, draft_id):
    """移除草稿"""
    session_key = f"order_drafts_{request.user.id}"
    drafts = request.session.get(session_key, [])
    drafts = [d for d in drafts if d['id'] != str(draft_id)]
    request.session[session_key] = drafts
    request.session.pop(f"draft_{draft_id}", None)
    messages.success(request, '草稿已移除')
    return redirect('place_order')


@login_required
@customer_required
@transaction.atomic
def submit_orders(request):
    """批量提交所有草稿订单"""
    if request.method != 'POST':
        return redirect('place_order')
    session_key = f"order_drafts_{request.user.id}"
    drafts_meta = request.session.get(session_key, [])
    if not drafts_meta:
        messages.error(request, '没有待提交的订单')
        return redirect('place_order')
    profile = request.user.get_effective_customer_profile()
    merchant = profile.merchant
    created_orders = []
    total_amount = Decimal('0')
    for meta in drafts_meta:
        draft = request.session.get(f"draft_{meta['id']}")
        if not draft:
            continue
        # 获取定价（优先使用商户自定义价格，否则按标准规则）
        from utils.pricing_tiers import get_customer_price
        unit_price = get_customer_price(profile, draft.get('product_name'), draft.get('material'), draft.get('thickness'))
        # 创建订单
        order = Order.objects.create(
            customer=request.user,
            merchant=merchant,
            status='pending_confirm',
            urgent=draft.get('urgent', False),
            delivery_type=draft.get('delivery_type', 'express'),
            special_requests=draft.get('special_requests', ''),
            preset_options=draft.get('preset_options', []),
            is_submitted=True,
        )
        # 设置地址
        addr_id = draft.get('address_id')
        if addr_id:
            try:
                order.delivery_address = Address.objects.get(pk=addr_id, user=request.user)
                order.save(update_fields=['delivery_address'])
            except Address.DoesNotExist:
                pass
        # 创建订单明细
        item = OrderItem.objects.create(
            order=order,
            product_name=draft.get('product_name'),
            material=draft.get('material'),
            thickness=draft.get('thickness'),
            length_mm=Decimal(draft.get('length_mm', 0)),
            width_mm=Decimal(draft.get('width_mm', 0)),
            quantity=int(draft.get('quantity', 1)),
            unit_price=unit_price,
            file=draft.get('file_path', ''),
            original_file_name=draft.get('file_name', ''),
            file_processed=draft.get('file_processed', False),
            file_standard_checked=draft.get('file_standard_checked', False),
            is_image_file=draft.get('is_image_file', False),
            red_box_data=draft.get('boxes_json', ''),
        )
        order.update_total()
        total_amount += order.total_amount
        created_orders.append(order)
    # 信用额度支付
    if created_orders:
        if total_amount <= profile.credit_remaining:
            profile.credit_used += total_amount
            profile.save(update_fields=['credit_used'])
            for o in created_orders:
                o.transition_status('paid', operator=request.user, remark='信用额度支付')
                # 自动拼版：订单支付成功后立即生成拼版建议
                from utils.plate_layout import auto_generate_plate_layout_for_order
                auto_generate_plate_layout_for_order(o)
                o.plate_status = 'auto_generated'
                o.save(update_fields=['plate_status'])
            messages.success(request, f'成功提交 {len(created_orders)} 个订单，已使用信用额度支付。')
        else:
            for o in created_orders:
                o.transition_status('pending_payment', operator=request.user, remark='信用额度不足')
            messages.warning(request, f'成功提交 {len(created_orders)} 个订单，但信用额度不足，订单状态为待支付。')
    # 清理session
    request.session.pop(session_key, None)
    for meta in drafts_meta:
        request.session.pop(f"draft_{meta['id']}", None)
    return redirect('my_orders')


def _draft_summary(draft):
    """生成草稿摘要"""
    materials = dict(OrderItem.MATERIAL_CHOICES)
    products = dict(OrderItem.PRODUCT_NAME_CHOICES)
    return f"{products.get(draft.get('product_name'), '')} {materials.get(draft.get('material'), '')} {draft.get('thickness', '')}mm × {draft.get('quantity', 1)}"


def _calculate_pdf_area(file_path, box_info=None):
    """
    计算PDF参考面积（cm²）
    优先使用框识别的内容区域尺寸，没有框时回退到PDF页面尺寸
    :param box_info: 已识别的框信息（可选，避免重复识别）
    """
    try:
        # 先尝试使用已识别的框信息
        if box_info:
            return box_info['total_area_cm2']

        # 否则重新识别
        from utils.pdf_red_box import smart_extract_boxes_for_order
        box_info = smart_extract_boxes_for_order(file_path)
        if box_info:
            return box_info['total_area_cm2']

        # 无框时回退到PDF页面尺寸
        doc = fitz.open(file_path)
        page = doc[0]
        rect = page.rect
        # 点转mm: 1点 = 1/72英寸 = 25.4/72 mm
        width_mm = rect.width * 25.4 / 72
        height_mm = rect.height * 25.4 / 72
        area_cm2 = (width_mm * height_mm) / 100.0
        doc.close()
        return round(area_cm2, 2)
    except Exception as e:
        return 0


def _get_pdf_page_dimensions(file_path):
    """获取PDF页面尺寸（mm），用于与用户填写尺寸对比"""
    from utils.pdf_processor import _get_pdf_local_path
    try:
        local_path = _get_pdf_local_path(file_path)
        if not local_path:
            return None, None
        doc = fitz.open(local_path)
        page = doc[0]
        rect = page.rect
        pt_to_mm = 25.4 / 72.0
        width_mm = round(rect.width * pt_to_mm, 1)
        height_mm = round(rect.height * pt_to_mm, 1)
        doc.close()
        # 清理临时文件
        if local_path != file_path and not local_path.startswith(str(settings.MEDIA_ROOT)):
            try:
                os.unlink(local_path)
            except:
                pass
        return width_mm, height_mm
    except Exception:
        return None, None


# ==================== 订单管理 ====================

@login_required
@customer_required
def my_orders(request):
    """我的订单列表（带统计看板、日期筛选、自动确认收货）"""
    from django.utils import timezone
    from datetime import timedelta

    status_filter = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')

    orders = request.user.orders.filter(is_submitted=True).prefetch_related('items')
    if status_filter:
        orders = orders.filter(status=status_filter)
    if start_date:
        orders = orders.filter(created_at__date__gte=start_date)
    if end_date:
        orders = orders.filter(created_at__date__lte=end_date)
    orders = orders.order_by('-created_at')

    # 为每个 OrderItem 生成预览缩略图
    from utils.pdf_processor import generate_pdf_preview
    for order in orders:
        for item in order.items.all():
            item.preview_url = None
            if item.file:
                preview_rel = f"customer_previews/{item.id}.png"
                preview_path = os.path.join(settings.MEDIA_ROOT, preview_rel)
                if not os.path.exists(preview_path):
                    generate_pdf_preview(item.file.name, preview_rel, dpi=72)
                if os.path.exists(preview_path):
                    item.preview_url = settings.MEDIA_URL + preview_rel

    # ===== 自动确认收货：已发货超过7天未确认的订单 =====
    seven_days_ago = timezone.now() - timedelta(days=7)
    auto_confirm_orders = request.user.orders.filter(
        status='shipped',
        shipped_at__isnull=False,
        shipped_at__lte=seven_days_ago
    )
    for o in auto_confirm_orders:
        o.transition_status('received', operator=None, remark='系统自动确认收货（发货后7天）')

    # ===== 统计看板数据（基于全部已提交订单） =====
    all_orders = request.user.orders.filter(is_submitted=True)

    # 总订单数、总金额
    total_orders = all_orders.count()
    total_amount = all_orders.aggregate(s=Sum('total_amount'))['s'] or 0

    # 总版数（所有OrderItem的quantity之和）
    from apps.orders.models import OrderItem
    total_plates = OrderItem.objects.filter(
        order__customer=request.user, order__is_submitted=True
    ).aggregate(s=Sum('quantity'))['s'] or 0

    # 产品类型分布（按product_name分组）
    product_stats = OrderItem.objects.filter(
        order__customer=request.user, order__is_submitted=True
    ).values('product_name').annotate(
        order_count=Count('order', distinct=True),
        total_qty=Sum('quantity')
    ).order_by('-total_qty')[:5]
    from apps.products.models import ProductSpec
    product_name_map = {p[0]: p[1] for p in ProductSpec.PRODUCT_NAME_CHOICES}
    # 兼容旧数据中的非标准值
    extra_name_map = {
        'pingdiao': '雕刻版 - 平雕版',
    }
    for s in product_stats:
        s['label'] = product_name_map.get(s['product_name']) or extra_name_map.get(s['product_name'], s['product_name'])

    # 状态分组统计
    status_stats = {
        'pending': all_orders.filter(status__in=['pending_confirm', 'design_confirmed', 'pending_payment']).count(),
        'producing': all_orders.filter(status__in=['paid', 'in_production']).count(),
        'shipped': all_orders.filter(status='shipped').count(),
        'completed': all_orders.filter(status='received').count(),
    }

    # ===== 当前列表汇总 =====
    list_count = orders.count()
    list_amount = orders.aggregate(s=Sum('total_amount'))['s'] or 0

    import json
    return render(request, 'customer/my_orders.html', {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'current_status': status_filter,
        'start_date': start_date,
        'end_date': end_date,
        'total_orders': total_orders,
        'total_amount': total_amount,
        'total_plates': total_plates,
        'product_stats': product_stats,
        'product_stats_json': json.dumps(list(product_stats), ensure_ascii=False),
        'status_stats': status_stats,
        'list_count': list_count,
        'list_amount': list_amount,
    })


@login_required
@customer_required
def order_detail(request, order_id):
    """订单详情（含物流轨迹）"""
    order = get_object_or_404(Order, pk=order_id, customer=request.user, is_submitted=True)

    # 为每个 item 检查文件是否存在并生成预览图
    from utils.pdf_processor import generate_pdf_preview
    for item in order.items.all():
        item.file_exists = False
        item.preview_url = None
        if item.file:
            # 检查文件是否在存储后端（OSS 或本地）存在
            item.file_exists = default_storage.exists(item.file.name)
            if item.file_exists:
                preview_rel = f"customer_previews/{item.id}.png"
                preview_path = os.path.join(settings.MEDIA_ROOT, preview_rel)
                if not os.path.exists(preview_path):
                    generate_pdf_preview(item.file.name, preview_rel, dpi=72)
                if os.path.exists(preview_path):
                    item.preview_url = settings.MEDIA_URL + preview_rel

    # 查询快递100物流轨迹
    tracking_data = None
    if order.tracking_number:
        from utils.kuaidi100 import query_tracking, format_tracking_data
        result = query_tracking(order.tracking_number, company_code=order.tracking_company or None)
        if result['success']:
            tracking_data = format_tracking_data(result['data'])
    # 同时检查商户端是否也有查询（兼容商户端已查询的数据）
    if not tracking_data and order.tracking_number:
        from utils.kuaidi100 import query_tracking, format_tracking_data
        result = query_tracking(order.tracking_number, company_code=order.tracking_company or None)
        if result['success']:
            tracking_data = format_tracking_data(result['data'])

    return render(request, 'customer/order_detail.html', {
        'order': order,
        'tracking_data': tracking_data,
    })


@login_required
@customer_required
def cancel_order(request, order_id):
    """取消订单（生产前可取消）"""
    order = get_object_or_404(Order, pk=order_id, customer=request.user)
    if not order.can_cancel():
        messages.error(request, '该订单当前状态无法取消，请联系商家处理')
        return redirect('order_detail', order_id=order_id)
    # 退回信用额度（仅未结清的订单）
    if order.status == 'paid' and not order.is_settled:
        profile = request.user.get_effective_customer_profile()
        profile.credit_used -= order.total_amount
        if profile.credit_used < 0:
            profile.credit_used = 0
        profile.save(update_fields=['credit_used'])
    order.transition_status('cancelled', operator=request.user, remark='用户主动取消')
    messages.success(request, '订单已取消')
    return redirect('my_orders')


@login_required
@customer_required
def confirm_receipt(request, order_id):
    """用户确认收货"""
    order = get_object_or_404(Order, pk=order_id, customer=request.user, status='shipped')
    order.transition_status('received', operator=request.user, remark='用户确认收货')
    messages.success(request, '已确认收货')
    return redirect('my_orders')


# ==================== 快捷单页下单 ====================

@login_required
@customer_required
def quick_order(request):
    """兼容旧入口，重定向到统一下单页"""
    return redirect('place_order')


@login_required
@customer_required
def quick_order_upload(request):
    """AJAX：上传PDF并返回识别的尺寸信息"""
    if request.method != 'POST' or not request.FILES.get('pdf_file'):
        return JsonResponse({'success': False, 'error': '请上传PDF文件'})

    file = request.FILES['pdf_file']
    ext = os.path.splitext(file.name)[1].lower()
    if ext != '.pdf':
        return JsonResponse({'success': False, 'error': '仅支持PDF格式文件'})

    try:
        filename = f"order_files/{request.user.id}/{uuid.uuid4().hex}{ext}"
        path = default_storage.save(filename, file)

        # 获取本地文件路径（OSS 文件会下载到临时文件）
        from utils.pdf_processor import _get_pdf_local_path
        local_path = _get_pdf_local_path(path)
        if not local_path:
            return JsonResponse({'success': False, 'error': '文件保存失败'})

        # 【修复】先识别红框（必须在转纯黑之前！）
        from utils.pdf_red_box import smart_extract_boxes_for_order
        box_info = smart_extract_boxes_for_order(local_path)

        # 计算面积（复用已识别的框信息）
        area = _calculate_pdf_area(local_path, box_info)

        # 获取页面尺寸
        pdf_w_mm, pdf_h_mm = _get_pdf_page_dimensions(local_path)

        # 【临时关闭】PDF转纯黑（耗时太长，通过异步任务或单独接口处理）
        # 预览图恢复生成
        preview_url = None
        try:
            preview_filename = f"previews/{uuid.uuid4().hex}.png"
            preview_path = os.path.join(settings.MEDIA_ROOT, preview_filename)
            os.makedirs(os.path.dirname(preview_path), exist_ok=True)
            from utils.pdf_processor import generate_pdf_preview
            preview_url = generate_pdf_preview(local_path, preview_filename, dpi=150, black_only=True)
            print(f"[预览图生成] 结果: {preview_url}, 文件: {file.name}")
        except Exception as e:
            import traceback
            print(f"[预览图生成] 失败: {e}")
            traceback.print_exc()

        # 清理临时文件
        if local_path != os.path.join(settings.MEDIA_ROOT, path):
            try:
                os.unlink(local_path)
            except:
                pass

        response_data = {
            'success': True,
            'file_path': path,
            'file_name': file.name,
            'area': area,
            'pdf_width_mm': pdf_w_mm,
            'pdf_height_mm': pdf_h_mm,
            'preview_url': preview_url,
        }

        # 如果有识别到框，返回框信息
        if box_info:
            response_data['box_count'] = box_info['box_count']
            response_data['first_length'] = box_info['first_length']
            response_data['first_width'] = box_info['first_width']
            response_data['first_quantity'] = box_info['first_quantity']
            response_data['boxes'] = box_info['boxes']

        return JsonResponse(response_data)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@customer_required
def batch_upload_files(request):
    """AJAX：批量上传PDF并返回每个文件的识别结果"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': '请使用POST请求'})

    files = request.FILES.getlist('pdf_files')
    if not files:
        return JsonResponse({'success': False, 'error': '请上传PDF文件'})

    results = []
    for file in files:
        ext = os.path.splitext(file.name)[1].lower()
        if ext != '.pdf':
            results.append({'success': False, 'error': '仅支持PDF格式', 'file_name': file.name})
            continue

        try:
            filename = f"order_files/{request.user.id}/{uuid.uuid4().hex}{ext}"
            path = default_storage.save(filename, file)

            # 获取本地文件路径（OSS 文件会下载到临时文件）
            from utils.pdf_processor import _get_pdf_local_path
            local_path = _get_pdf_local_path(path)
            if not local_path:
                results.append({'success': False, 'error': '文件保存失败', 'file_name': file.name})
                continue

            # 【修复】先识别红框（必须在转纯黑之前！）
            from utils.pdf_red_box import smart_extract_boxes_for_order
            box_info = smart_extract_boxes_for_order(local_path)

            # 计算面积（复用已识别的框信息）
            area = _calculate_pdf_area(local_path, box_info)

            # 获取页面尺寸
            pdf_w_mm, pdf_h_mm = _get_pdf_page_dimensions(local_path)

            # 【临时关闭】PDF转纯黑（耗时太长，通过异步任务或单独接口处理）
            # 预览图恢复生成
            preview_url = None
            try:
                preview_filename = f"previews/{uuid.uuid4().hex}.png"
                from utils.pdf_processor import generate_pdf_preview
                preview_url = generate_pdf_preview(local_path, preview_filename, dpi=150, black_only=True)
                print(f"[预览图生成-批量] 结果: {preview_url}, 文件: {file.name}")
            except Exception as e:
                import traceback
                print(f"[预览图生成-批量] 失败: {e}")
                traceback.print_exc()

            # 清理临时文件
            if local_path != os.path.join(settings.MEDIA_ROOT, path):
                try:
                    os.unlink(local_path)
                except:
                    pass

            file_result = {
                'success': True,
                'file_path': path,
                'file_name': file.name,
                'area': area,
                'pdf_width_mm': pdf_w_mm,
                'pdf_height_mm': pdf_h_mm,
                'preview_url': preview_url,
            }
            if box_info:
                file_result.update({
                    'box_count': box_info['box_count'],
                    'first_length': box_info['first_length'],
                    'first_width': box_info['first_width'],
                    'first_quantity': box_info['first_quantity'],
                    'boxes': box_info['boxes'],
                })
            results.append(file_result)
        except Exception as e:
            results.append({'success': False, 'error': str(e), 'file_name': file.name})

    return JsonResponse({'success': True, 'files': results})


@transaction.atomic
def _handle_quick_order_post(request, profile, tier):
    """处理单页下单的POST请求（支持规格组模式 / 混合规格下单）"""
    from utils.pricing_tiers import get_customer_price
    import json

    # 其他字段
    special_requests = request.POST.get('special_requests', '')
    preset_options = request.POST.getlist('preset_options')
    urgent = request.POST.get('urgent') == 'on'
    delivery_type = request.POST.get('delivery_type', 'express')
    address_id = request.POST.get('address_id')

    # 文件类型（旧兼容）
    file_type = request.POST.get('file_type', 'processed')
    file_processed = (file_type == 'processed')
    file_standard_checked = (file_type == 'standard')
    is_image_file = (file_type == 'image')

    # ========== 尝试规格组模式 ==========
    spec_groups_json = request.POST.get('spec_groups_data', '')
    spec_groups = []
    if spec_groups_json:
        try:
            spec_groups = json.loads(spec_groups_json)
        except json.JSONDecodeError:
            spec_groups = []

    # ========== 回退到旧 files_data 模式 ==========
    if not spec_groups:
        files_data_json = request.POST.get('files_data', '[]')
        try:
            files_data = json.loads(files_data_json)
        except json.JSONDecodeError:
            files_data = []

        # 兼容旧版单文件字段
        if not files_data:
            file_path = request.POST.get('file_path', '')
            if file_path:
                files_data = [{
                    'file_path': file_path,
                    'length_mm': request.POST.get('length_mm', 0) or 0,
                    'width_mm': request.POST.get('width_mm', 0) or 0,
                    'quantity': request.POST.get('quantity', 1),
                }]

        if not files_data:
            messages.error(request, '请上传至少一个文件')
            return redirect('place_order')

        product_name = request.POST.get('product_name')
        material = request.POST.get('material')
        thickness = request.POST.get('thickness')
        unit_price = get_customer_price(profile, product_name, material, thickness)

        spec_groups = [{
            'product_name': product_name,
            'material': material,
            'thickness': thickness,
            'unit_price': float(unit_price) if unit_price else 0,
            'files': files_data,
        }]

    if not spec_groups:
        messages.error(request, '请添加至少一个规格组并上传文件')
        return redirect('place_order')

    # 检查所有规格组数据
    total_files = 0
    for gi, sg in enumerate(spec_groups):
        if not sg.get('product_name'):
            messages.error(request, f'规格组 {gi+1}：请选择细分产品')
            return redirect('place_order')
        if not sg.get('material'):
            messages.error(request, f'规格组 {gi+1}：请选择材质')
            return redirect('place_order')
        if not sg.get('thickness'):
            messages.error(request, f'规格组 {gi+1}：请选择厚度')
            return redirect('place_order')
        files = sg.get('files', [])
        if not files:
            messages.error(request, f'规格组 {gi+1}：请上传至少一个文件')
            return redirect('place_order')
        total_files += len(files)

    # 创建订单
    order = Order.objects.create(
        customer=request.user,
        merchant=profile.merchant,
        status='pending_confirm',
        urgent=urgent,
        delivery_type=delivery_type,
        special_requests=special_requests,
        preset_options=preset_options,
        is_submitted=True,
    )

    # 地址
    if address_id:
        try:
            order.delivery_address = Address.objects.get(pk=address_id, user=request.user)
            order.save(update_fields=['delivery_address'])
        except Address.DoesNotExist:
            pass

    # 为每个规格组的每个文件创建订单明细
    all_items = []
    for sg in spec_groups:
        product_name = sg.get('product_name')
        material = sg.get('material')
        thickness = sg.get('thickness')
        unit_price = Decimal(str(sg.get('unit_price', 0) or 0))
        # 如果前端没传 unit_price，从定价表获取
        if not unit_price or unit_price <= 0:
            unit_price = get_customer_price(profile, product_name, material, thickness)
            if not unit_price:
                unit_price = Decimal('0')

        files = sg.get('files', [])
        for fd in files:
            item_length = Decimal(str(fd.get('length_mm', 0) or 0))
            item_width = Decimal(str(fd.get('width_mm', 0) or 0))
            item_qty = int(fd.get('quantity', 1))
            item = OrderItem.objects.create(
                order=order,
                product_name=product_name,
                material=material,
                thickness=thickness,
                length_mm=item_length,
                width_mm=item_width,
                quantity=item_qty,
                unit_price=unit_price,
                file=fd.get('file_path', ''),
                original_file_name=fd.get('file_name', ''),
                file_processed=file_processed,
                file_standard_checked=file_standard_checked,
                is_image_file=is_image_file,
                red_box_data=json.dumps(fd.get('boxes', [])),
            )
            all_items.append(item)

    order.update_total()

    # 保存常用备注
    if special_requests:
        profile.last_order_note = special_requests
        profile.save(update_fields=['last_order_note'])

    # 信用额度支付
    if order.total_amount <= profile.credit_remaining:
        profile.credit_used += order.total_amount
        profile.save(update_fields=['credit_used'])
        order.transition_status('paid', operator=request.user, remark='信用额度支付')
        from utils.plate_layout import auto_generate_plate_layout_for_order
        auto_generate_plate_layout_for_order(order)
        order.plate_status = 'auto_generated'
        order.save(update_fields=['plate_status'])
        messages.success(request, f'订单 {order.sn} 提交成功（含{total_files}个文件），已使用信用额度支付。')
    else:
        order.transition_status('pending_payment', operator=request.user, remark='信用额度不足')
        messages.warning(request, f'订单 {order.sn} 提交成功（含{total_files}个文件），但信用额度不足，订单状态为待支付。')

    return redirect('my_orders')


# ==================== 个人中心相关模板视图 ====================

@login_required
@customer_required
def profile_view(request):
    """个人中心 - 资料修改"""
    from apps.accounts.forms import CustomerProfileForm
    profile_obj = request.user.get_effective_customer_profile()
    my_profile = request.user.customer_profile
    if request.method == 'POST':
        # 子账号只能修改自己的真实姓名
        if not my_profile.is_main_account:
            my_profile.real_name = request.POST.get('real_name', my_profile.real_name)
            my_profile.save(update_fields=['real_name'])
            messages.success(request, '个人信息已更新')
            return redirect('profile')
        form = CustomerProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, '个人信息已更新')
            return redirect('profile')
    else:
        form = CustomerProfileForm(instance=profile_obj)
    return render(request, 'customer/profile.html', {'form': form, 'profile': profile_obj, 'my_profile': my_profile})



# ==================== 客户子账号管理 ====================

def customer_main_required(view_func):
    """装饰器：仅客户主账号可操作"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'customer':
            messages.error(request, '请先以终端用户身份登录')
            return redirect('login')
        profile = getattr(request.user, 'customer_profile', None)
        if not profile or not profile.is_main_account:
            messages.error(request, '仅主账号可操作')
            return redirect('customer_dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@customer_required
@customer_main_required
def subaccount_list(request):
    """客户子账号列表"""
    profile = request.user.customer_profile
    subaccounts = profile.sub_accounts.select_related('user').all()
    return render(request, 'customer/subaccount_list.html', {
        'subaccounts': subaccounts,
        'max_count': profile.max_sub_accounts,
        'current_count': subaccounts.count(),
    })


@login_required
@customer_required
@customer_main_required
def subaccount_add(request):
    """主账号添加子账号"""
    profile = request.user.customer_profile
    if profile.sub_accounts.count() >= profile.max_sub_accounts:
        messages.error(request, f'子账号数量已达上限 ({profile.max_sub_accounts})')
        return redirect('customer_subaccount_list')

    if request.method == 'POST':
        phone = request.POST.get('phone')
        username = request.POST.get('username')
        password = request.POST.get('password')
        real_name = request.POST.get('real_name', '')

        if User.objects.filter(phone=phone).exists():
            messages.error(request, '该手机号已被注册')
        else:
            user = User.objects.create_user(
                username=username, phone=phone, password=password,
                user_type='customer', is_approved=True
            )
            CustomerProfile.objects.create(
                user=user,
                merchant=profile.merchant,
                company_name=profile.company_name,
                province=profile.province,
                city=profile.city,
                real_name=real_name,
                invite_code=profile.invite_code,
                registration_status='approved',
                pricing_tier=profile.pricing_tier,
                custom_prices=profile.custom_prices,
                is_main_account=False,
                parent=profile,
            )
            messages.success(request, '子账号创建成功')
            return redirect('customer_subaccount_list')

    return render(request, 'customer/subaccount_form.html', {
        'title': '新增子账号',
        'max_count': profile.max_sub_accounts,
        'current_count': profile.sub_accounts.count(),
    })


@login_required
@customer_required
@customer_main_required
def subaccount_edit(request, user_id):
    """主账号编辑子账号"""
    profile = request.user.customer_profile
    sub_profile = get_object_or_404(
        CustomerProfile, user_id=user_id, parent=profile
    )
    if request.method == 'POST':
        sub_profile.user.is_active = request.POST.get('is_active') == 'on'
        sub_profile.user.save(update_fields=['is_active'])
        sub_profile.real_name = request.POST.get('real_name', sub_profile.real_name)
        sub_profile.save(update_fields=['real_name'])
        messages.success(request, '子账号已更新')
        return redirect('customer_subaccount_list')
    return render(request, 'customer/subaccount_form.html', {
        'sub_profile': sub_profile,
        'title': '编辑子账号',
    })


# ==================== 对账单管理 ====================

@login_required
@customer_required
def customer_statements(request):
    """客户：我的对账单列表"""
    profile = request.user.get_effective_customer_profile()
    status_filter = request.GET.get('status')
    statements = Statement.objects.filter(customer=request.user, merchant=profile.merchant)
    if status_filter:
        statements = statements.filter(status=status_filter)
    statements = statements.order_by('-created_at')
    return render(request, 'customer/statement_list.html', {
        'statements': statements,
        'status_choices': Statement.STATUS_CHOICES,
        'status_filter': status_filter,
    })


@login_required
@customer_required
def customer_statement_detail(request, statement_id):
    """客户：对账单详情"""
    profile = request.user.get_effective_customer_profile()
    statement = get_object_or_404(Statement, pk=statement_id, customer=request.user, merchant=profile.merchant)
    return render(request, 'customer/statement_detail.html', {
        'statement': statement,
        'orders': statement.orders.all().order_by('created_at'),
    })


@login_required
@customer_required
def customer_statement_confirm(request, statement_id):
    """客户：确认对账单"""
    profile = request.user.get_effective_customer_profile()
    statement = get_object_or_404(Statement, pk=statement_id, customer=request.user, merchant=profile.merchant)
    if statement.status != 'pending':
        messages.error(request, '该对账单当前状态不支持确认操作')
        return redirect('customer_statement_detail', statement_id=statement.id)
    if request.method == 'POST':
        statement.status = 'confirmed'
        statement.confirmed_at = timezone.now()
        statement.save()
        messages.success(request, f'对账单 {statement.sn} 已确认，请按账单金额安排付款')
    return redirect('customer_statement_detail', statement_id=statement.id)


@login_required
@customer_required
def customer_statement_mark_paid(request, statement_id):
    """客户：标记已付款（线下转账后通知商户）"""
    profile = request.user.get_effective_customer_profile()
    statement = get_object_or_404(Statement, pk=statement_id, customer=request.user, merchant=profile.merchant)
    if statement.status not in ('pending', 'confirmed'):
        messages.error(request, '该对账单当前状态不支持标记付款')
        return redirect('customer_statement_detail', statement_id=statement.id)
    if request.method == 'POST':
        statement.status = 'paid'
        statement.paid_at = timezone.now()
        statement.remark = request.POST.get('remark', statement.remark)
        statement.save()
        messages.success(request, f'已通知商户对账单 {statement.sn} 已付款，请等待商户确认')
    return redirect('customer_statement_detail', statement_id=statement.id)


@login_required
@customer_required
def customer_statement_export(request, statement_id):
    """客户：导出对账单Excel"""
    profile = request.user.get_effective_customer_profile()
    statement = get_object_or_404(Statement, pk=statement_id, customer=request.user, merchant=profile.merchant)
    # 复用商户端的Excel生成函数
    from apps.merchant_platform.views import _build_statement_excel
    output = _build_statement_excel(statement)
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    filename = f"对账单_{statement.sn}_{statement.customer.phone}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@customer_required
def download_customer_file(request, order_id, item_id):
    """
    客户安全下载自己的订单文件
    """
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    item = get_object_or_404(OrderItem, id=item_id, order=order)

    if not item.file:
        messages.error(request, '该订单没有上传文件')
        return redirect('order_detail', order_id=order.id)

    try:
        with item.file.open('rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            from urllib.parse import quote
            filename = item.original_file_name or os.path.basename(item.file.name)
            response['Content-Disposition'] = f"attachment; filename*=UTF-8''{quote(filename)}"
            return response
    except Exception:
        messages.error(request, '文件不存在或已被删除')
        return redirect('order_detail', order_id=order.id)


@login_required
def complaint_create(request, order_id):
    """
    创建投诉
    订单状态为 shipped 或 received 时可投诉
    """
    if request.user.user_type != 'customer':
        messages.error(request, '无权访问')
        return redirect('login')

    order = get_object_or_404(Order, id=order_id, customer=request.user)

    # 检查订单状态
    if order.status not in ['shipped', 'received']:
        messages.error(request, '当前订单状态不可投诉')
        return redirect('order_detail', order_id=order.id)

    # 检查是否已投诉
    if order.complaints.exists():
        messages.info(request, '您已提交投诉，请查看投诉详情')
        return redirect('complaint_detail', complaint_id=order.complaints.first().id)

    if request.method == 'POST':
        description = request.POST.get('description', '').strip()
        complaint_type = request.POST.get('complaint_type', 'quality')

        if not description:
            messages.error(request, '请填写投诉描述')
            return render(request, 'customer/complaint_form.html', {'order': order})

        # 检查图片大小（每个不超过2MB）
        images = []
        for i in range(1, 4):
            img = request.FILES.get(f'image{i}')
            if img:
                if img.size > 2 * 1024 * 1024:
                    messages.error(request, f'图片{i}超过2MB限制')
                    return render(request, 'customer/complaint_form.html', {'order': order})
                images.append(img)

        # 创建投诉
        complaint = OrderComplaint.objects.create(
            order=order,
            customer=request.user,
            complaint_type=complaint_type,
            description=description,
        )

        # 保存图片
        if len(images) >= 1:
            complaint.image1 = images[0]
        if len(images) >= 2:
            complaint.image2 = images[1]
        if len(images) >= 3:
            complaint.image3 = images[2]
        complaint.save()

        messages.success(request, '投诉已提交，商家会尽快处理')
        return redirect('complaint_detail', complaint_id=complaint.id)

    return render(request, 'customer/complaint_form.html', {'order': order})


@login_required
def complaint_detail(request, complaint_id):
    """
    查看投诉详情
    """
    if request.user.user_type != 'customer':
        messages.error(request, '无权访问')
        return redirect('login')

    complaint = get_object_or_404(
        OrderComplaint, id=complaint_id, customer=request.user
    )

    return render(request, 'customer/complaint_detail.html', {
        'complaint': complaint,
        'order': complaint.order,
    })

