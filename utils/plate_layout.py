"""
智能拼版算法
支持多板材规格、拼版间距规则、红框尺寸识别
"""

import math
from decimal import Decimal
from .plate_type_rules import PLATE_SPECS, get_spacing_mm


def calculate_plate_layout(rectangles, plate_width=610, plate_height=914, spacing_mm=10):
    """
    矩形打包算法（Shelf算法增强版）
    
    参数:
        rectangles: [{id, width, height, label, thickness, material}, ...]
        plate_width: 板材宽度(mm)
        plate_height: 板材高度(mm)
        spacing_mm: 拼版间距(mm)，会根据产品厚度/材质自动计算
    
    返回:
        {
            'plate_width': int,
            'plate_height': int,
            'placed_count': int,
            'usage_rate': float,
            'rectangles': [{id, x, y, width, height, label}, ...]
        }
    """
    if not rectangles:
        return None
    
    # 复制并排序（按面积从大到小）
    rects = []
    for r in rectangles:
        w = float(r['width'])
        h = float(r['height'])
        # 确保width >= height（标准化方向）
        if w < h:
            w, h = h, w
        rects.append({
            'id': r['id'],
            'width': w,
            'height': h,
            'label': r.get('label', ''),
            'thickness': str(r.get('thickness', '')),
            'material': r.get('material', ''),
            'original': r,
        })
    
    rects.sort(key=lambda r: r['width'] * r['height'], reverse=True)
    
    # Shelf打包
    shelves = []
    placed = []
    
    for rect in rects:
        # 计算该矩形需要的间距（与已放置矩形的间距取最大值）
        # 简化：使用传入的spacing_mm作为基础，如果rect有thickness/material则自动计算
        actual_spacing = spacing_mm
        if rect['thickness'] and rect['material']:
            # 与同shelf中最后一个矩形比较
            if shelves:
                last_shelf = shelves[-1]
                if last_shelf['items']:
                    last_item = last_shelf['items'][-1]
                    actual_spacing = get_spacing_mm(
                        rect['thickness'], last_item['thickness'],
                        rect['material'], last_item['material']
                    )
        
        rect_w = rect['width'] + actual_spacing
        rect_h = rect['height'] + actual_spacing
        
        placed_flag = False
        
        # 尝试放入现有shelf
        for shelf in shelves:
            if (shelf['remaining_width'] >= rect_w and
                shelf['height'] >= rect_h):
                shelf['items'].append(rect)
                placed.append({
                    'id': rect['id'],
                    'x': round(plate_width - shelf['remaining_width'], 2),
                    'y': round(shelf['y'], 2),
                    'width': round(rect['width'], 2),
                    'height': round(rect['height'], 2),
                    'label': rect['label'],
                })
                shelf['remaining_width'] -= rect_w
                shelf['height'] = max(shelf['height'], rect_h)
                placed_flag = True
                break
        
        # 创建新shelf
        if not placed_flag:
            # 计算新shelf的y位置
            y_pos = 0
            if shelves:
                y_pos = shelves[-1]['y'] + shelves[-1]['height']
            
            if y_pos + rect_h <= plate_height:
                new_shelf = {
                    'y': y_pos,
                    'height': rect_h,
                    'remaining_width': plate_width - rect_w,
                    'items': [rect],
                }
                shelves.append(new_shelf)
                placed.append({
                    'id': rect['id'],
                    'x': 0,
                    'y': round(y_pos, 2),
                    'width': round(rect['width'], 2),
                    'height': round(rect['height'], 2),
                    'label': rect['label'],
                })
                placed_flag = True
    
    # 计算材料利用率
    total_area = plate_width * plate_height
    used_area = sum(r['width'] * r['height'] for r in placed)
    usage_rate = round((used_area / total_area) * 100, 2) if total_area > 0 else 0
    
    return {
        'plate_width': plate_width,
        'plate_height': plate_height,
        'placed_count': len(placed),
        'usage_rate': usage_rate,
        'rectangles': placed,
        'shelves': len(shelves),
    }


def auto_select_plate_spec(rectangles, spacing_mm=10):
    """
    自动选择最合适的板材规格
    尝试所有板材规格，选择利用率最高的
    
    返回: (plate_spec_dict, layout_result)
    """
    best_result = None
    best_spec = None
    best_usage = 0
    
    for spec in PLATE_SPECS:
        result = calculate_plate_layout(
            rectangles,
            plate_width=spec['width'],
            plate_height=spec['height'],
            spacing_mm=spacing_mm
        )
        if result and result['placed_count'] == len(rectangles):
            if result['usage_rate'] > best_usage:
                best_usage = result['usage_rate']
                best_result = result
                best_spec = spec
    
    # 如果所有规格都放不下，选能放最多的
    if not best_result:
        best_count = 0
        for spec in PLATE_SPECS:
            result = calculate_plate_layout(
                rectangles,
                plate_width=spec['width'],
                plate_height=spec['height'],
                spacing_mm=spacing_mm
            )
            if result and result['placed_count'] > best_count:
                best_count = result['placed_count']
                best_result = result
                best_spec = spec
    
    return best_spec, best_result


def build_rectangles_from_order_items(items):
    """
    从OrderItem列表构建拼版矩形数据
    优先使用PDF红框识别的尺寸，如果没有则使用客户填写的尺寸
    """
    rects = []
    for item in items:
        # 优先使用红框识别的尺寸（如果已存储）
        length = float(item.length_mm) if item.length_mm else 0
        width = float(item.width_mm) if item.width_mm else 0
        if length <= 0 or width <= 0:
            continue
        rects.append({
            'id': str(item.id),
            'width': length,
            'height': width,
            'label': f"{item.get_product_name_display()} {item.thickness}mm",
            'thickness': str(item.thickness),
            'material': str(item.material),
        })
    return rects


def calculate_plate_layout_rectpack(rectangles, plate_width=610, plate_height=914, spacing_mm=10, algorithm='maxrects'):
    """
    使用 rectpack 库进行矩形打包（支持多种算法）
    
    algorithm 可选值:
        'maxrects'    - MaxRectsBssf（默认，利用率最高）
        'guillotine'  - GuillotineBssfSas
        'skyline'     - SkylineMwf
        'shelf'       - 回退到原生Shelf算法
    
    返回格式与 calculate_plate_layout 完全一致
    """
    if algorithm == 'shelf' or not rectangles:
        return calculate_plate_layout(rectangles, plate_width, plate_height, spacing_mm)
    
    # 导入 rectpack（内嵌在项目utils中，无需pip安装）
    from utils.rectpack import newPacker, PackingMode
    from utils.rectpack.maxrects import MaxRectsBssf
    from utils.rectpack.guillotine import GuillotineBssfSas
    from utils.rectpack.skyline import SkylineMwf
    
    # 选择算法类
    algo_map = {
        'maxrects': MaxRectsBssf,
        'guillotine': GuillotineBssfSas,
        'skyline': SkylineMwf,
    }
    pack_algo = algo_map.get(algorithm, MaxRectsBssf)
    
    # 复制并排序（按面积从大到小，rectpack也会排序但保险起见）
    rects = []
    for r in rectangles:
        w = float(r['width']) + spacing_mm
        h = float(r['height']) + spacing_mm
        # 标准化：长边在前
        if w < h:
            w, h = h, w
        rects.append({
            'id': r['id'],
            'width': w,
            'height': h,
            'label': r.get('label', ''),
            'original': r,
        })
    
    rects.sort(key=lambda r: r['width'] * r['height'], reverse=True)
    
    # 创建packer
    packer = newPacker(mode=PackingMode.Offline, pack_algo=pack_algo)
    packer.add_bin(plate_width, plate_height)
    
    for r in rects:
        packer.add_rect(r['width'], r['height'], r['id'])
    
    packer.pack()
    
    # 解析结果
    placed = []
    total_area = plate_width * plate_height
    used_area = 0
    
    for abin in packer:
        for rect in abin:
            # 减去间距得到原始尺寸
            orig_w = rect.width - spacing_mm
            orig_h = rect.height - spacing_mm
            placed.append({
                'id': rect.rid,
                'x': round(rect.x, 2),
                'y': round(rect.y, 2),
                'width': round(orig_w, 2),
                'height': round(orig_h, 2),
                'label': next((r['label'] for r in rects if r['id'] == rect.rid), ''),
            })
            used_area += orig_w * orig_h
        # 只取第一个bin（单板材）
        break
    
    placed_count = len(placed)
    usage_rate = round((used_area / total_area) * 100, 2) if total_area > 0 else 0
    
    return {
        'plate_width': plate_width,
        'plate_height': plate_height,
        'placed_count': placed_count,
        'usage_rate': usage_rate,
        'rectangles': placed,
        'shelves': 0,  # rectpack不区分shelf
        'algorithm': algorithm,
    }


def auto_select_plate_spec_rectpack(rectangles, spacing_mm=10, algorithm='maxrects'):
    """
    使用 rectpack 自动选择最优板材规格
    返回: (plate_spec_dict, layout_result)
    """
    best_result = None
    best_spec = None
    best_usage = 0
    
    for spec in PLATE_SPECS:
        result = calculate_plate_layout_rectpack(
            rectangles,
            plate_width=spec['width'],
            plate_height=spec['height'],
            spacing_mm=spacing_mm,
            algorithm=algorithm
        )
        if result and result['placed_count'] == len(rectangles):
            if result['usage_rate'] > best_usage:
                best_usage = result['usage_rate']
                best_result = result
                best_spec = spec
    
    # 如果所有规格都放不下，选能放最多的
    if not best_result:
        best_count = 0
        for spec in PLATE_SPECS:
            result = calculate_plate_layout_rectpack(
                rectangles,
                plate_width=spec['width'],
                plate_height=spec['height'],
                spacing_mm=spacing_mm,
                algorithm=algorithm
            )
            if result and result['placed_count'] > best_count:
                best_count = result['placed_count']
                best_result = result
                best_spec = spec
    
    return best_spec, best_result


def auto_generate_plate_layout_for_order(order, algorithm='maxrects'):
    """
    为订单自动调用拼版算法生成拼版建议（整合PDF红框识别+版类规则）
    可在客户下单或商家审核时调用
    """
    import json, os
    from django.conf import settings
    from utils.pdf_red_box import find_red_rectangles, extract_red_box_area_mm
    from utils.plate_type_rules import get_plate_type_by_product, get_spacing_mm
    from apps.orders.models import PlateLayout

    items = order.items.all()
    if not items:
        return

    # Step 1: PDF红框识别 + 版类识别
    rects = []
    for item in items:
        # 版类识别
        plate_type_key = get_plate_type_by_product(item.product_name, item.material, item.thickness)
        if plate_type_key:
            item.plate_type = plate_type_key
            item.save(update_fields=['plate_type'])

        # PDF红框识别
        red_box = None
        if item.file:
            try:
                file_path = os.path.join(settings.MEDIA_ROOT, item.file.name)
                if os.path.exists(file_path):
                    red_rects = find_red_rectangles(file_path)
                    if red_rects:
                        item.red_box_data = json.dumps(red_rects)
                        item.save(update_fields=['red_box_data'])
                        # 使用红框尺寸替代客户填写的尺寸
                        red_box = red_rects[0]
            except Exception:
                pass

        # 确定拼版矩形尺寸（优先红框，但做合理性校验）
        user_length = float(item.length_mm) if item.length_mm else 0
        user_width = float(item.width_mm) if item.width_mm else 0
        MAX_PLATE_DIM = 1100  # mm，超过任何板材规格视为异常

        length = user_length
        width = user_width

        if red_box:
            # 【修复】统一使用 mm 字段，避免 pt/mm 混用导致尺寸异常
            rb_w = float(red_box.get('length_mm', 0) or red_box.get('width', 0))
            rb_h = float(red_box.get('width_mm', 0) or red_box.get('height', 0))
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
                print(f"[拼版] 红框尺寸异常 {rb_w:.1f}×{rb_h:.1f}，"
                      f"回退到用户填写尺寸 {user_length:.1f}×{user_width:.1f} "
                      f"(订单 {order.sn})")

        if length <= 0 or width <= 0:
            continue

        rects.append({
            'id': str(item.id),
            'width': length,
            'height': width,
            'label': f"{item.get_product_name_display()} {item.thickness}mm",
            'thickness': str(item.thickness),
            'material': str(item.material),
        })

    if not rects:
        return

    # Step 2: 自动选择最优板材规格并拼版
    best_spec, suggestion = auto_select_plate_spec_rectpack(rects, algorithm=algorithm)
    if suggestion:
        layout, created = PlateLayout.objects.get_or_create(order=order)
        layout.layout_data = json.dumps(suggestion, ensure_ascii=False)
        plate_info = best_spec['name'] if best_spec else '自动选择'
        algo_name = {'maxrects':'MaxRects','guillotine':'Guillotine','skyline':'Skyline','shelf':'Shelf'}.get(algorithm, algorithm)
        layout.designer_note = f'系统自动拼版（算法:{algo_name}，板材:{plate_info}，利用率:{suggestion["usage_rate"]}%），请设计师确认或微调'
        layout.save()
