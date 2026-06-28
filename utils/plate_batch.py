"""
跨订单拼版算法 + 拼版效果图生成

核心功能：
1. 按 (product_name, material, thickness) 分组聚合待拼版订单
2. 使用 rectpack 算法将多个订单的 items 拼到一张/多张物理大版上
3. 生成高清拼版效果图（Pillow）
4. 保存 PlateBatch / PlateBatchItem 记录
"""

import json
import os
import math
import random
from io import BytesIO
from decimal import Decimal
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageDraw, ImageFont
import fitz  # PyMuPDF

from apps.orders.models import OrderItem, PlateBatch, PlateBatchItem
from utils.plate_type_rules import PLATE_SPECS, get_spacing_mm


def get_items_for_plate_batching(merchant, status_filter=None):
    """
    获取商户下所有待拼版的 OrderItem
    按 (product_name, material, thickness) 分组
    
    返回: dict[(product_name, material, thickness), [OrderItem, ...]]
    """
    from apps.orders.models import Order

    if status_filter is None:
        status_filter = ['design_confirmed', 'paid']

    # 只取已提交、状态符合、且未确认拼版的订单
    orders = merchant.orders.filter(
        status__in=status_filter,
        is_submitted=True,
    ).exclude(
        plate_status='confirmed'
    ).prefetch_related('items')

    groups = {}
    for order in orders:
        for item in order.items.all():
            # 必须有有效尺寸
            if not item.length_mm or not item.width_mm:
                continue
            if float(item.length_mm) <= 0 or float(item.width_mm) <= 0:
                continue
            # 已属于某个确认的拼版批次，跳过
            if item.plate_batch and item.plate_batch.status == 'confirmed':
                continue
            key = (item.product_name, item.material, item.thickness)
            groups.setdefault(key, []).append(item)

    return groups


def build_rects_from_items(item_list, spacing_mm=10):
    """
    从 OrderItem 列表构建 rectpack 需要的矩形列表
    如果 quantity > 1，会展开为多个矩形
    
    返回: [{id, width, height, label, original_item, order_sn, customer_phone}, ...]
    """
    rects = []
    # 最大允许尺寸（超过任何板材规格即视为异常）
    MAX_PLATE_DIM = 1100  # mm

    for item in item_list:
        user_length = float(item.length_mm) if item.length_mm else 0
        user_width = float(item.width_mm) if item.width_mm else 0
        # 优先使用红框尺寸，但做合理性校验
        length = user_length
        width = user_width
        if item.red_box_data:
            try:
                boxes = json.loads(item.red_box_data)
                if isinstance(boxes, list) and len(boxes) > 0:
                    # 使用第一个红框的尺寸（统一读取 mm 字段）
                    rb = boxes[0]
                    rb_w = float(rb.get('length_mm', 0) or rb.get('width', 0))
                    rb_h = float(rb.get('width_mm', 0) or rb.get('height', 0))
                    # 校验1：红框尺寸不能超过最大板材规格
                    # 校验2：红框面积不能超过用户填写面积的4倍（容错空间）
                    user_area = user_length * user_width
                    red_box_area = rb_w * rb_h
                    is_reasonable = (
                        0 < rb_w <= MAX_PLATE_DIM and
                        0 < rb_h <= MAX_PLATE_DIM and
                        (user_area <= 0 or red_box_area <= user_area * 4)
                    )
                    if is_reasonable:
                        length = rb_w
                        width = rb_h
                    else:
                        # 异常：回退到用户填写尺寸
                        print(f"[拼版] 红框尺寸异常 {rb_w:.1f}×{rb_h:.1f}，"
                              f"回退到用户填写尺寸 {user_length:.1f}×{user_width:.1f} "
                              f"(订单 {item.order.sn})")
            except (json.JSONDecodeError, TypeError):
                pass

        # 加上间距后的有效尺寸
        eff_w = length + spacing_mm
        eff_h = width + spacing_mm

        qty = item.quantity or 1
        for i in range(qty):
            rects.append({
                'id': f"{item.id}_{i}",
                'width': eff_w,
                'height': eff_h,
                'orig_width': length,
                'orig_height': width,
                'label': f"{item.order.sn}",
                'original_item': item,
                'order_sn': item.order.sn,
                'customer_phone': item.order.customer.phone if item.order.customer else '',
                'product_display': item.get_product_name_display(),
            })
    return rects


def pack_rects_into_plates(rects, plate_specs=None, algorithm='maxrects'):
    """
    将矩形列表拼到板材上，自动选择最优板材规格。
    如果一张放不下，会生成多张版（多个 bin）。
    
    返回: [
        {
            'spec': {'name': '610×914mm', 'width': 610, 'height': 914},
            'placed': [{'id', 'x', 'y', 'width', 'height', ...}, ...],
            'unplaced': [...],
            'usage_rate': float,
        },
        ...
    ]
    """
    from utils.rectpack import newPacker, PackingMode
    from utils.rectpack.maxrects import MaxRectsBssf
    from utils.rectpack.guillotine import GuillotineBssfSas
    from utils.rectpack.skyline import SkylineMwf

    if not rects:
        return []

    if plate_specs is None:
        plate_specs = PLATE_SPECS

    algo_map = {
        'maxrects': MaxRectsBssf,
        'guillotine': GuillotineBssfSas,
        'skyline': SkylineMwf,
    }
    pack_algo = algo_map.get(algorithm, MaxRectsBssf)

    # 排序：按面积从大到小
    sorted_rects = sorted(rects, key=lambda r: r['width'] * r['height'], reverse=True)

    best_result = None
    best_spec = None
    best_usage = -1

    # 策略1：尝试所有板材规格，选利用率最高且能放下全部的
    for spec in plate_specs:
        packer = newPacker(mode=PackingMode.Offline, pack_algo=pack_algo)
        # 先加一个大版 bin
        packer.add_bin(spec['width'], spec['height'])
        for r in sorted_rects:
            packer.add_rect(r['width'], r['height'], r['id'])
        packer.pack()

        # 统计
        placed = []
        unplaced_ids = set(r['id'] for r in sorted_rects)
        total_area = spec['width'] * spec['height']
        used_area = 0
        num_bins_used = 0

        for abin in packer:
            num_bins_used += 1
            for rect in abin:
                rid = rect.rid
                unplaced_ids.discard(rid)
                orig = next((r for r in sorted_rects if r['id'] == rid), None)
                if orig:
                    placed.append({
                        'id': rid,
                        'x': round(rect.x, 2),
                        'y': round(rect.y, 2),
                        'width': round(rect.width, 2),
                        'height': round(rect.height, 2),
                        'orig_width': orig['orig_width'],
                        'orig_height': orig['orig_height'],
                        'label': orig['label'],
                        'original_item': orig['original_item'],
                        'order_sn': orig['order_sn'],
                        'customer_phone': orig['customer_phone'],
                        'product_display': orig['product_display'],
                        'bin_index': num_bins_used - 1,
                    })
                    used_area += orig['orig_width'] * orig['orig_height']

        usage_rate = round((used_area / (total_area * num_bins_used)) * 100, 2) if num_bins_used > 0 else 0

        if not unplaced_ids:
            # 全部放下了
            if usage_rate > best_usage:
                best_usage = usage_rate
                best_spec = spec
                best_result = {
                    'spec': spec,
                    'placed': placed,
                    'unplaced': [],
                    'usage_rate': usage_rate,
                    'num_bins': num_bins_used,
                }

    if best_result:
        return [best_result]

    # 策略2：如果单规格单 bin 放不下，尝试多 bin（同规格）
    # 尝试每个规格，用尽可能多的 bin 放下所有矩形
    best_multi = None
    best_multi_bins = float('inf')
    best_multi_usage = -1

    for spec in plate_specs:
        packer = newPacker(mode=PackingMode.Offline, pack_algo=pack_algo)
        # 先加足够多 bin（最多 len(rects) 个，理论上限）
        for _ in range(len(rects)):
            packer.add_bin(spec['width'], spec['height'])
        for r in sorted_rects:
            packer.add_rect(r['width'], r['height'], r['id'])
        packer.pack()

        placed = []
        unplaced_ids = set(r['id'] for r in sorted_rects)
        total_area = spec['width'] * spec['height']
        used_area = 0
        num_bins_used = 0

        for abin in packer:
            if not list(abin):
                continue
            num_bins_used += 1
            for rect in abin:
                rid = rect.rid
                unplaced_ids.discard(rid)
                orig = next((r for r in sorted_rects if r['id'] == rid), None)
                if orig:
                    placed.append({
                        'id': rid,
                        'x': round(rect.x, 2),
                        'y': round(rect.y, 2),
                        'width': round(rect.width, 2),
                        'height': round(rect.height, 2),
                        'orig_width': orig['orig_width'],
                        'orig_height': orig['orig_height'],
                        'label': orig['label'],
                        'original_item': orig['original_item'],
                        'order_sn': orig['order_sn'],
                        'customer_phone': orig['customer_phone'],
                        'product_display': orig['product_display'],
                        'bin_index': num_bins_used - 1,
                    })
                    used_area += orig['orig_width'] * orig['orig_height']

        if not unplaced_ids:
            usage_rate = round((used_area / (total_area * num_bins_used)) * 100, 2) if num_bins_used > 0 else 0
            if num_bins_used < best_multi_bins or (num_bins_used == best_multi_bins and usage_rate > best_multi_usage):
                best_multi_bins = num_bins_used
                best_multi_usage = usage_rate
                # 按 bin_index 分组
                bins = {}
                for p in placed:
                    bins.setdefault(p['bin_index'], []).append(p)
                best_multi = []
                for idx in sorted(bins.keys()):
                    bin_placed = bins[idx]
                    bin_used_area = sum(b['orig_width'] * b['orig_height'] for b in bin_placed)
                    bin_usage = round((bin_used_area / total_area) * 100, 2)
                    best_multi.append({
                        'spec': spec,
                        'placed': bin_placed,
                        'unplaced': [],
                        'usage_rate': bin_usage,
                        'num_bins': 1,
                    })

    if best_multi:
        return best_multi

    # 策略3：实在放不下，返回能放最多的（按单 bin 每个规格尝试）
    best_fallback = None
    best_fallback_count = 0
    for spec in plate_specs:
        packer = newPacker(mode=PackingMode.Offline, pack_algo=pack_algo)
        packer.add_bin(spec['width'], spec['height'])
        for r in sorted_rects:
            packer.add_rect(r['width'], r['height'], r['id'])
        packer.pack()

        placed = []
        unplaced = []
        unplaced_ids = set(r['id'] for r in sorted_rects)
        total_area = spec['width'] * spec['height']
        used_area = 0

        for abin in packer:
            for rect in abin:
                rid = rect.rid
                unplaced_ids.discard(rid)
                orig = next((r for r in sorted_rects if r['id'] == rid), None)
                if orig:
                    placed.append({
                        'id': rid,
                        'x': round(rect.x, 2),
                        'y': round(rect.y, 2),
                        'width': round(rect.width, 2),
                        'height': round(rect.height, 2),
                        'orig_width': orig['orig_width'],
                        'orig_height': orig['orig_height'],
                        'label': orig['label'],
                        'original_item': orig['original_item'],
                        'order_sn': orig['order_sn'],
                        'customer_phone': orig['customer_phone'],
                        'product_display': orig['product_display'],
                        'bin_index': 0,
                    })
                    used_area += orig['orig_width'] * orig['orig_height']

        for r in sorted_rects:
            if r['id'] in unplaced_ids:
                unplaced.append(r)

        count = len(placed)
        usage_rate = round((used_area / total_area) * 100, 2) if total_area > 0 else 0
        if count > best_fallback_count:
            best_fallback_count = count
            best_fallback = {
                'spec': spec,
                'placed': placed,
                'unplaced': unplaced,
                'usage_rate': usage_rate,
                'num_bins': 1,
            }

    return [best_fallback] if best_fallback else []


def _load_customer_preview(rect, scale, temp_dir, use_plate_file=False):
    """
    为单个矩形加载客户文件并生成带版类效果的预览图
    返回处理后的 PIL Image 或 None
    
    参数:
        use_plate_file: 是否优先使用制版文件（plate_file）而非客户源文件（file）
    """
    item = rect.get('original_item')
    if not item:
        return None
    
    # 选择文件源
    file_field = item.plate_file if use_plate_file and item.plate_file else item.file
    if not file_field:
        return None

    file_path = os.path.join(settings.MEDIA_ROOT, file_field.name)
    if not os.path.exists(file_path):
        return None

    try:
        # 使用 PyMuPDF 渲染 PDF 第一页
        doc = fitz.open(file_path)
        if len(doc) == 0:
            doc.close()
            return None
        page = doc[0]

        # 计算渲染DPI：根据在拼版图中的像素尺寸反推，保证清晰度
        target_w = rect['orig_width'] * scale
        target_h = rect['orig_height'] * scale
        # 目标DPI：至少150，最高300
        render_dpi = min(300, max(150, int(max(target_w, target_h) / 2)))
        zoom = render_dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()

        # 缩放到拼版图中的目标尺寸
        if abs(img.width - target_w) > 2 or abs(img.height - target_h) > 2:
            img = img.resize((max(1, int(target_w)), max(1, int(target_h))), Image.LANCZOS)

        # 应用版类视觉效果
        from utils.plate_preview_effects import apply_plate_effect, get_effect_type
        effect_type = get_effect_type(item.product_name, getattr(item, 'plate_type', None))
        img = apply_plate_effect(img, effect_type)

        return img
    except Exception as e:
        # 失败时静默回退（不阻塞整体拼版图生成）
        print(f"[generate_plate_image] 加载客户预览失败 {rect.get('order_sn')}: {e}")
        return None


def generate_plate_image(plate_result, output_filename=None, dpi=150, use_plate_file=False):
    """
    生成拼版效果图（Pillow）
    改进版：每个矩形位置直接嵌入客户文件的实际内容，并根据版类应用视觉效果

    参数:
        plate_result: pack_rects_into_plates 返回的单个 plate dict
        output_filename: 输出文件名（不含路径），如 'plate_xxx.png'
        dpi: 输出分辨率
        use_plate_file: 是否优先使用制版文件

    返回:
        (image_path_relative, image_url) 或 (None, None)
    """
    spec = plate_result['spec']
    placed = plate_result['placed']
    usage_rate = plate_result.get('usage_rate', 0)

    pw = spec['width']
    ph = spec['height']

    # 画布尺寸：固定宽度 1600px，高度按比例（提高分辨率让细节更清晰）
    CANVAS_W = 1600
    scale = CANVAS_W / pw
    CANVAS_H = int(ph * scale)

    # 创建画布（浅灰色，模拟金属板材）
    img = Image.new('RGB', (CANVAS_W, CANVAS_H), (235, 235, 235))
    draw = ImageDraw.Draw(img)

    # 画板材外框 + 裁切标记（四角小L形）
    draw.rectangle([0, 0, CANVAS_W - 1, CANVAS_H - 1], outline=(60, 60, 60), width=2)
    mark_len = int(5 * scale)  # 5mm裁切标记
    draw.line([(0, 0), (mark_len, 0)], fill=(60, 60, 60), width=1)
    draw.line([(0, 0), (0, mark_len)], fill=(60, 60, 60), width=1)
    draw.line([(CANVAS_W - 1, 0), (CANVAS_W - 1 - mark_len, 0)], fill=(60, 60, 60), width=1)
    draw.line([(CANVAS_W - 1, 0), (CANVAS_W - 1, mark_len)], fill=(60, 60, 60), width=1)
    draw.line([(0, CANVAS_H - 1), (mark_len, CANVAS_H - 1)], fill=(60, 60, 60), width=1)
    draw.line([(0, CANVAS_H - 1), (0, CANVAS_H - 1 - mark_len)], fill=(60, 60, 60), width=1)
    draw.line([(CANVAS_W - 1, CANVAS_H - 1), (CANVAS_W - 1 - mark_len, CANVAS_H - 1)], fill=(60, 60, 60), width=1)
    draw.line([(CANVAS_W - 1, CANVAS_H - 1), (CANVAS_W - 1, CANVAS_H - 1 - mark_len)], fill=(60, 60, 60), width=1)

    # 字体
    font_paths = [
        "C:/Windows/Fonts/ARIALUNI.ttf",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/SimsunExtG.ttf",
        "arial.ttf",
    ]
    font_path = None
    for fp in font_paths:
        if os.path.exists(fp):
            font_path = fp
            break
    try:
        if font_path:
            font_small = ImageFont.truetype(font_path, 12)
            font_large = ImageFont.truetype(font_path, 18)
        else:
            raise Exception("No font found")
    except Exception:
        font_small = ImageFont.load_default()
        font_large = ImageFont.load_default()

    # 为每个订单分配颜色（用于文字标注背景）
    order_colors = {}
    color_pool = [
        (255, 100, 100), (100, 180, 255), (100, 220, 100), (255, 180, 60),
        (200, 100, 255), (60, 200, 200), (255, 120, 200), (180, 180, 60),
    ]
    random.shuffle(color_pool)
    color_idx = 0

    def get_order_color(order_sn):
        nonlocal color_idx
        if order_sn not in order_colors:
            order_colors[order_sn] = color_pool[color_idx % len(color_pool)]
            color_idx += 1
        return order_colors[order_sn]

    # 画每个矩形：先画内容图，再画边框和标注
    for rect in placed:
        rx = rect['x'] * scale
        ry = rect['y'] * scale
        rw = rect['orig_width'] * scale
        rh = rect['orig_height'] * scale

        # 尝试嵌入客户文件的实际内容（带版类效果）
        preview_img = _load_customer_preview(rect, scale, None, use_plate_file=use_plate_file)
        if preview_img:
            # 贴入处理后的预览图
            paste_x = int(rx)
            paste_y = int(ry)
            paste_w = min(int(rw), CANVAS_W - paste_x)
            paste_h = min(int(rh), CANVAS_H - paste_y)
            if paste_w > 0 and paste_h > 0:
                # 确保尺寸匹配
                if preview_img.width != paste_w or preview_img.height != paste_h:
                    preview_img = preview_img.resize((paste_w, paste_h), Image.LANCZOS)
                img.paste(preview_img, (paste_x, paste_y))
        else:
            # 无文件时回退到彩色色块
            color = get_order_color(rect['order_sn'])
            draw.rectangle([rx, ry, rx + rw, ry + rh], fill=color, outline=(50, 50, 50), width=1)

        # 始终画边框（让边界清晰）
        draw.rectangle([rx, ry, rx + rw, ry + rh], outline=(40, 40, 40), width=1)

        # 标注文字（半透明背景条上）
        label = rect['order_sn']
        info = f"{rect['orig_width']:.0f}×{rect['orig_height']:.0f}"

        if rw > 50 and rh > 30:
            # 顶部订单号标签
            try:
                bbox = draw.textbbox((0, 0), label, font=font_small)
                tw = bbox[2] - bbox[0] + 6
                th = bbox[3] - bbox[1] + 4
            except Exception:
                tw, th = len(label) * 7 + 6, 16

            # 左上角：订单号（白底黑字）
            draw.rectangle([rx + 1, ry + 1, rx + tw, ry + th], fill=(255, 255, 255, 200))
            draw.text((rx + 3, ry + 2), label, fill=(20, 20, 20), font=font_small)

            # 右下角：尺寸
            if rw > 80 and rh > 40:
                try:
                    bbox2 = draw.textbbox((0, 0), info, font=font_small)
                    tw2 = bbox2[2] - bbox2[0] + 6
                    th2 = bbox2[3] - bbox2[1] + 4
                except Exception:
                    tw2, th2 = len(info) * 7 + 6, 16
                draw.rectangle([rx + rw - tw2 - 1, ry + rh - th2 - 1, rx + rw - 1, ry + rh - 1],
                               fill=(255, 255, 255, 180))
                draw.text((rx + rw - tw2 + 2, ry + rh - th2 + 1), info, fill=(60, 60, 60), font=font_small)

    # 标题栏
    title_h = 40
    title_img = Image.new('RGB', (CANVAS_W, title_h), (30, 30, 30))
    title_draw = ImageDraw.Draw(title_img)
    # 获取版类信息（如果所有矩形同版类）
    effect_labels = set()
    for rect in placed:
        item = rect.get('original_item')
        if item:
            from utils.plate_preview_effects import get_effect_name
            effect_labels.add(get_effect_name(item.product_name, getattr(item, 'plate_type', None)))
    effect_str = f" | 版类效果: {', '.join(effect_labels)}" if effect_labels else ""
    title_text = f"拼版图  {spec['name']}  |  利用率: {usage_rate:.1f}%  |  共 {len(placed)} 件{effect_str}"
    title_draw.text((12, 10), title_text, fill=(255, 255, 255), font=font_large)

    # 合并
    final_img = Image.new('RGB', (CANVAS_W, title_h + CANVAS_H), (30, 30, 30))
    final_img.paste(title_img, (0, 0))
    final_img.paste(img, (0, title_h))

    # 保存
    if output_filename is None:
        import uuid
        output_filename = f"batch_{uuid.uuid4().hex[:12]}.png"

    rel_path = f"plate_layouts/{output_filename}"
    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    final_img.save(abs_path, "PNG")

    url = f"{settings.MEDIA_URL}{rel_path}"
    return rel_path, url


def persist_plate_batch(merchant, product_name, material, thickness, plate, algorithm='maxrects', use_plate_file=False):
    """
    将 pack_rects_into_plates 的单张版结果写入 PlateBatch / PlateBatchItem。
    返回 PlateBatch 实例。
    """
    spec = plate['spec']
    placed = plate['placed']
    if not placed:
        return None

    layout_data = {
        'plate_width': spec['width'],
        'plate_height': spec['height'],
        'plate_spec_name': spec['name'],
        'placed_count': len(placed),
        'usage_rate': plate.get('usage_rate', 0),
        'algorithm': algorithm,
        'rectangles': [
            {
                'id': r['id'],
                'x': r['x'],
                'y': r['y'],
                'width': r['orig_width'],
                'height': r['orig_height'],
                'rotation': 0,
                'label': r['label'],
                'order_sn': r['order_sn'],
                'customer_phone': str(r['customer_phone']),
            }
            for r in placed
        ],
    }

    import uuid
    img_filename = f"batch_{uuid.uuid4().hex[:12]}.png"
    img_rel_path, _img_url = generate_plate_image(plate, output_filename=img_filename, use_plate_file=use_plate_file)

    batch = PlateBatch.objects.create(
        merchant=merchant,
        product_name=product_name,
        material=material,
        thickness=thickness,
        plate_spec_name=spec['name'],
        plate_width=spec['width'],
        plate_height=spec['height'],
        layout_data=json.dumps(layout_data, ensure_ascii=False),
        usage_rate=plate.get('usage_rate', 0),
        status='auto_generated',
    )

    if img_rel_path:
        abs_path = os.path.join(settings.MEDIA_ROOT, img_rel_path)
        with open(abs_path, 'rb') as f:
            batch.layout_image.save(img_filename, ContentFile(f.read()), save=True)

    from utils.plate_pdf import generate_plate_production_pdf
    pdf_filename = f"batch_{uuid.uuid4().hex[:12]}_production.pdf"
    pdf_rel_path, _pdf_url = generate_plate_production_pdf(batch, output_filename=pdf_filename)
    if pdf_rel_path:
        pdf_abs_path = os.path.join(settings.MEDIA_ROOT, pdf_rel_path)
        with open(pdf_abs_path, 'rb') as f:
            batch.production_pdf.save(pdf_filename, ContentFile(f.read()), save=True)

    affected_orders = set()
    for r in placed:
        item = r['original_item']
        PlateBatchItem.objects.create(
            plate_batch=batch,
            order=item.order,
            order_item=item,
            x=r['x'],
            y=r['y'],
            width=r['orig_width'],
            height=r['orig_height'],
            rotation=0,
        )
        item.plate_batch = batch
        item.save(update_fields=['plate_batch'])
        affected_orders.add(item.order)

    for order in affected_orders:
        order.plate_status = 'auto_generated'
        order.save(update_fields=['plate_status'])

    return batch


def auto_generate_plate_batches(merchant, algorithm='maxrects', dry_run=False):
    """
    为商户自动跨订单拼版
    
    参数:
        merchant: Merchant 实例
        algorithm: 拼版算法
        dry_run: True 时不保存数据库，只返回结果
    
    返回:
        [{
            'batch': PlateBatch 实例（或 dict）,
            'items': [PlateBatchItem, ...],
            'image_url': str,
        }, ...]
    """
    groups = get_items_for_plate_batching(merchant)
    if not groups:
        return []

    results = []

    for (product_name, material, thickness), item_list in groups.items():
        if not item_list:
            continue

        # 确定间距（同组同材质同厚度）
        spacing = get_spacing_mm(thickness, thickness, material, material)

        rects = build_rects_from_items(item_list, spacing_mm=spacing)
        if not rects:
            continue

        plates = pack_rects_into_plates(rects, algorithm=algorithm)
        if not plates:
            continue

        for plate_idx, plate in enumerate(plates):
            spec = plate['spec']
            placed = plate['placed']
            unplaced = plate.get('unplaced', [])

            if not placed:
                continue

            if dry_run:
                layout_data = {
                    'plate_width': spec['width'],
                    'plate_height': spec['height'],
                    'plate_spec_name': spec['name'],
                    'placed_count': len(placed),
                    'usage_rate': plate.get('usage_rate', 0),
                    'algorithm': algorithm,
                    'rectangles': [
                        {
                            'id': r['id'],
                            'x': r['x'],
                            'y': r['y'],
                            'width': r['orig_width'],
                            'height': r['orig_height'],
                            'rotation': 0,
                            'label': r['label'],
                            'order_sn': r['order_sn'],
                            'customer_phone': str(r['customer_phone']),
                        }
                        for r in placed
                    ],
                }
                import uuid
                img_filename = f"batch_{uuid.uuid4().hex[:12]}.png"
                img_rel_path, img_url = generate_plate_image(plate, output_filename=img_filename)
                results.append({
                    'batch': {
                        'product_name': product_name,
                        'material': material,
                        'thickness': thickness,
                        'plate_spec_name': spec['name'],
                        'plate_width': spec['width'],
                        'plate_height': spec['height'],
                        'usage_rate': plate.get('usage_rate', 0),
                        'status': 'auto_generated',
                        'layout_data': layout_data,
                    },
                    'items': placed,
                    'image_url': img_url,
                    'image_path': img_rel_path,
                })
                continue

            batch = persist_plate_batch(
                merchant, product_name, material, thickness, plate,
                algorithm=algorithm, use_plate_file=False,
            )
            batch_items = list(batch.items.all()) if batch else []

            results.append({
                'batch': batch,
                'items': batch_items,
                'image_url': batch.layout_image.url if batch and batch.layout_image else '',
            })

    return results


def get_scaled_layout_for_display(batch, canvas_width=1100, canvas_height=720):
    """
    将 PlateBatch 的布局数据转换为前端画布可用的缩放后坐标
    
    返回:
        {
            'plate_width': float,
            'plate_height': float,
            'scaled_plate_width': float,
            'scaled_plate_height': float,
            'scale': float,
            'rectangles': [{id, x, y, width, height, label, order_sn, customer_phone}, ...]
        }
    """
    pw = float(batch.plate_width)
    ph = float(batch.plate_height)

    scale_w = canvas_width / pw
    scale_h = canvas_height / ph
    scale = min(scale_w, scale_h)

    scaled_pw = round(pw * scale, 1)
    scaled_ph = round(ph * scale, 1)

    rects = []
    layout_data = {}
    if batch.layout_data:
        try:
            layout_data = json.loads(batch.layout_data)
        except Exception:
            pass

    for rect in layout_data.get('rectangles', []):
        rects.append({
            'id': rect.get('id', ''),
            'x': round(float(rect.get('x', 0)) * scale, 1),
            'y': round(float(rect.get('y', 0)) * scale, 1),
            'width': round(float(rect.get('width', 0)) * scale, 1),
            'height': round(float(rect.get('height', 0)) * scale, 1),
            'rotation': int(rect.get('rotation', 0)),
            'label': rect.get('label', ''),
            'order_sn': rect.get('order_sn', ''),
            'customer_phone': rect.get('customer_phone', ''),
        })

    return {
        'plate_width': pw,
        'plate_height': ph,
        'scaled_plate_width': scaled_pw,
        'scaled_plate_height': scaled_ph,
        'scale': scale,
        'rectangles': rects,
    }
