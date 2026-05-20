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
from django.db import transaction
from django.conf import settings
from django.core.files.storage import default_storage
from apps.accounts.models import User, CustomerProfile, Address
from apps.orders.models import Order, OrderItem, OrderStatusLog, CommunicationLog
from apps.products.models import ProductSpec
from apps.merchant_platform.models import Factory


def customer_required(view_func):
    """装饰器：仅终端用户可访问"""
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'customer':
            messages.error(request, '请先以终端用户身份登录')
            return redirect('login')
        profile = getattr(request.user, 'customer_profile', None)
        if not profile or profile.registration_status != 'approved':
            messages.error(request, '您的账号尚未通过商家审核')
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return wrapper


@login_required
@customer_required
def customer_dashboard(request):
    """终端用户首页"""
    profile = request.user.customer_profile
    recent_orders = request.user.orders.filter(is_submitted=True).order_by('-created_at')[:5]
    ctx = {
        'profile': profile,
        'recent_orders': recent_orders,
        'order_count': request.user.orders.filter(is_submitted=True).count(),
    }
    return render(request, 'customer/dashboard.html', ctx)


# ==================== 下单流程 ====================

@login_required
@customer_required
def place_order(request):
    """单页下单：产品选择 -> 上传文件 -> 自动识别尺寸 -> 确认提交"""
    profile = request.user.customer_profile
    from utils.pricing_tiers import get_etching_price, is_etching_product, get_product_category
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
        if is_etching_product(s.product_name):
            price = str(get_etching_price(tier, s.thickness))
        else:
            price = str(s.unit_price)
        spec_data[category]['products'][prod_key]['materials'][mat_key]['thicknesses'].append({
            'value': s.thickness,
            'label': s.get_thickness_display(),
            'price': price,
        })

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
        }
        request.session[f"draft_{draft['id']}"] = draft
        return redirect('order_step2', draft_id=draft['id'])
    # 按【产品大类→细分产品→材质→厚度】构建两级规格数据
    from utils.pricing_tiers import get_etching_price, is_etching_product, get_product_category
    profile = request.user.customer_profile
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
        # 腐蚀版按档位动态定价，其他固定价
        if is_etching_product(s.product_name):
            price = str(get_etching_price(tier, s.thickness))
        else:
            price = str(s.unit_price)
        spec_data[category]['products'][prod_key]['materials'][mat_key]['thicknesses'].append({
            'value': s.thickness,
            'label': s.get_thickness_display(),
            'price': price,
        })
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
        draft['file_standard_checked'] = request.POST.get('file_standard_checked') == 'on'
        draft['file_processed'] = request.POST.get('file_processed') == 'on'
        if request.FILES.get('pdf_file'):
            file = request.FILES['pdf_file']
            ext = os.path.splitext(file.name)[1].lower()
            if ext != '.pdf':
                messages.error(request, '仅支持PDF格式文件')
                return redirect('order_step2', draft_id=draft_id)
            filename = f"order_files/{request.user.id}/{uuid.uuid4().hex}{ext}"
            path = default_storage.save(filename, file)
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
    file_full_path = os.path.join(settings.MEDIA_ROOT, draft['file_path'])
    area = _calculate_pdf_area(file_full_path)
    draft['area'] = str(area)
    request.session[f"draft_{draft_id}"] = draft

    # 获取PDF页面尺寸，与用户填写尺寸做差异对比
    pdf_w_mm, pdf_h_mm = _get_pdf_page_dimensions(file_full_path)
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
    # 生成PDF第一页预览图
    preview_url = None
    file_full_path = os.path.join(settings.MEDIA_ROOT, draft['file_path'])
    if os.path.exists(file_full_path):
        preview_filename = f"previews/{draft_id}.png"
        preview_path = os.path.join(settings.MEDIA_ROOT, preview_filename)
        os.makedirs(os.path.dirname(preview_path), exist_ok=True)
        try:
            doc = fitz.open(file_full_path)
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            pix.save(preview_path)
            preview_url = settings.MEDIA_URL + preview_filename
            draft['preview_url'] = preview_url
            request.session[f"draft_{draft_id}"] = draft
        except Exception as e:
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
    profile = request.user.customer_profile
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
    profile = request.user.customer_profile
    merchant = profile.merchant
    created_orders = []
    total_amount = Decimal('0')
    for meta in drafts_meta:
        draft = request.session.get(f"draft_{meta['id']}")
        if not draft:
            continue
        # 获取定价（雕刻版/树脂版/菲林用固定价，腐蚀版按用户档位重新计算）
        from utils.pricing_tiers import is_etching_product, get_etching_price
        if is_etching_product(draft.get('product_name')):
            unit_price = get_etching_price(profile.pricing_tier, draft.get('thickness'))
        else:
            unit_price = Decimal(draft.get('unit_price', '0'))
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
            file_processed=draft.get('file_processed', False),
            file_standard_checked=draft.get('file_standard_checked', False),
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


def _calculate_pdf_area(file_path):
    """
    计算PDF参考面积（cm²）
    优先使用红框识别的内容区域尺寸，没有红框时回退到PDF页面尺寸
    """
    try:
        # 先尝试红框识别（更准确的制版内容区域）
        from utils.pdf_red_box import extract_red_box_area_mm
        red_box_mm = extract_red_box_area_mm(file_path)
        if red_box_mm:
            length_mm, width_mm = red_box_mm
            return round((length_mm * width_mm) / 100.0, 2)

        # 无红框时回退到PDF页面尺寸
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
    try:
        doc = fitz.open(file_path)
        page = doc[0]
        rect = page.rect
        pt_to_mm = 25.4 / 72.0
        width_mm = round(rect.width * pt_to_mm, 1)
        height_mm = round(rect.height * pt_to_mm, 1)
        doc.close()
        return width_mm, height_mm
    except Exception:
        return None, None


# ==================== 订单管理 ====================

@login_required
@customer_required
def my_orders(request):
    """我的订单列表"""
    status_filter = request.GET.get('status')
    orders = request.user.orders.filter(is_submitted=True)
    if status_filter:
        orders = orders.filter(status=status_filter)
    orders = orders.order_by('-created_at')
    return render(request, 'customer/my_orders.html', {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'current_status': status_filter,
    })


@login_required
@customer_required
def order_detail(request, order_id):
    """订单详情"""
    order = get_object_or_404(Order, pk=order_id, customer=request.user, is_submitted=True)
    return render(request, 'customer/order_detail.html', {'order': order})


@login_required
@customer_required
def cancel_order(request, order_id):
    """取消订单（生产前可取消）"""
    order = get_object_or_404(Order, pk=order_id, customer=request.user)
    if not order.can_cancel():
        messages.error(request, '该订单当前状态无法取消，请联系商家处理')
        return redirect('order_detail', order_id=order_id)
    # 退回信用额度
    if order.status == 'paid':
        profile = request.user.customer_profile
        profile.credit_used -= order.total_amount
        if profile.credit_used < 0:
            profile.credit_used = 0
        profile.save(update_fields=['credit_used'])
    order.transition_status('cancelled', operator=request.user, remark='用户主动取消')
    messages.success(request, '订单已取消')
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
        full_path = os.path.join(settings.MEDIA_ROOT, path)

        # 计算面积
        area = _calculate_pdf_area(full_path)

        # 获取页面尺寸
        pdf_w_mm, pdf_h_mm = _get_pdf_page_dimensions(full_path)

        # 生成预览图
        preview_url = None
        try:
            preview_filename = f"previews/{uuid.uuid4().hex}.png"
            preview_path = os.path.join(settings.MEDIA_ROOT, preview_filename)
            os.makedirs(os.path.dirname(preview_path), exist_ok=True)
            doc = fitz.open(full_path)
            page = doc[0]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            pix.save(preview_path)
            preview_url = settings.MEDIA_URL + preview_filename
            doc.close()
        except Exception:
            pass

        return JsonResponse({
            'success': True,
            'file_path': path,
            'file_name': file.name,
            'area': area,
            'pdf_width_mm': pdf_w_mm,
            'pdf_height_mm': pdf_h_mm,
            'preview_url': preview_url,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@transaction.atomic
def _handle_quick_order_post(request, profile, tier):
    """处理单页下单的POST请求"""
    from utils.pricing_tiers import is_etching_product, get_etching_price

    # 基础字段
    product_name = request.POST.get('product_name')
    material = request.POST.get('material')
    thickness = request.POST.get('thickness')
    quantity = int(request.POST.get('quantity', 1))
    length_mm = Decimal(request.POST.get('length_mm', 0) or 0)
    width_mm = Decimal(request.POST.get('width_mm', 0) or 0)
    unit_price_str = request.POST.get('unit_price', '0')

    # 文件
    file_path = request.POST.get('file_path', '')
    file_processed = request.POST.get('file_processed') == 'on'
    file_standard_checked = request.POST.get('file_standard_checked') == 'on'

    # 其他
    special_requests = request.POST.get('special_requests', '')
    preset_options = request.POST.getlist('preset_options')
    urgent = request.POST.get('urgent') == 'on'
    delivery_type = request.POST.get('delivery_type', 'express')
    address_id = request.POST.get('address_id')

    # 定价
    if is_etching_product(product_name):
        unit_price = get_etching_price(profile.pricing_tier, thickness)
    else:
        unit_price = Decimal(unit_price_str or '0')

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

    # 创建订单明细
    item = OrderItem.objects.create(
        order=order,
        product_name=product_name,
        material=material,
        thickness=thickness,
        length_mm=length_mm,
        width_mm=width_mm,
        quantity=quantity,
        unit_price=unit_price,
        file=file_path,
        file_processed=file_processed,
        file_standard_checked=file_standard_checked,
    )
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
        messages.success(request, f'订单 {order.sn} 提交成功，已使用信用额度支付。')
    else:
        order.transition_status('pending_payment', operator=request.user, remark='信用额度不足')
        messages.warning(request, f'订单 {order.sn} 提交成功，但信用额度不足，订单状态为待支付。')

    return redirect('my_orders')


# ==================== 个人中心相关模板视图 ====================

@login_required
@customer_required
def profile_view(request):
    """个人中心 - 资料修改"""
    from apps.accounts.forms import CustomerProfileForm
    profile_obj = request.user.customer_profile
    if request.method == 'POST':
        form = CustomerProfileForm(request.POST, instance=profile_obj)
        if form.is_valid():
            form.save()
            messages.success(request, '个人信息已更新')
            return redirect('profile')
    else:
        form = CustomerProfileForm(instance=profile_obj)
    return render(request, 'customer/profile.html', {'form': form, 'profile': profile_obj})
