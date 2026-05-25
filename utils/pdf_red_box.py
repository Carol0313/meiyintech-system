"""
PDF框识别工具
从客户上传的PDF中提取任意颜色的矩形框（制版内容区域）
支持红色、黑色、蓝色等各种颜色的框，排除白色/透明框
"""

import fitz


def find_colored_rectangles(file_path):
    """
    识别PDF页面中的有效制版框（排除文字笔画、装饰元素、内嵌描边等干扰）
    返回 [{x, y, width, height, area}, ...] 列表，按面积从大到小排序
    
    过滤策略：
    1. 最小尺寸放宽到 15x10pt（约5.3x3.5mm），保留小制版框
    2. 排除页面边框/裁切框（与页面边界重合或面积超过页面90%）
    3. 排除极端细长条（宽高比>20）和路径过于复杂的图形（>20个items）
    4. 排除嵌套在内的大面积内边框（面积>外层60%的内嵌框）
    5. 最多返回5个框
    """
    doc = fitz.open(file_path)
    colored_rects = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height
        
        # 获取页面文字块，用于排除文字区域被误认为框
        text_blocks = page.get_text("blocks")
        text_rects = [fitz.Rect(b[:4]) for b in text_blocks]
        
        # 方法1: 通过绘图路径识别
        drawings = page.get_drawings()
        for d in drawings:
            color = d.get('color')
            fill = d.get('fill')
            # 检测任意有颜色的框（排除白色/透明）
            is_colored_stroke = _is_colored_box(color)
            is_colored_fill = _is_colored_box(fill)

            if is_colored_stroke or is_colored_fill:
                rect = d.get('rect')
                items = d.get('items', [])
                
                if not rect:
                    continue
                
                # 过滤1：基本尺寸（放宽到 15x10pt，约 5.3x3.5mm）
                if rect.width < 15 or rect.height < 10:
                    continue
                
                rect_area = rect.width * rect.height
                
                # 过滤2：面积不能太小（排除零散细线）
                if rect_area < 200:
                    continue
                
                # 过滤3：排除极端细长条（宽高比 > 20）
                if rect.width / rect.height > 20 or rect.height / rect.width > 20:
                    continue
                
                # 过滤4：排除路径过于复杂的图形（文字轮廓/复杂装饰通常 items 很多）
                # 简单矩形框通常 items <= 10；收紧到 15 以过滤短文字轮廓
                if len(items) > 15:
                    continue
                
                # 过滤5：排除页面边框
                if rect_area > page_area * 0.9:
                    continue
                # 排除与页面边界几乎重合的矩形（裁切框/出血框）
                if (abs(rect.x0 - page_rect.x0) < 5 and 
                    abs(rect.y0 - page_rect.y0) < 5 and
                    abs(rect.x1 - page_rect.x1) < 5 and
                    abs(rect.y1 - page_rect.y1) < 5):
                    continue
                
                # 过滤6：排除与文字块高度重叠的区域（客户备注/文字注释）
                is_text_area = False
                for tr in text_rects:
                    intersect = rect & tr
                    if intersect and intersect.get_area() > rect_area * 0.75:
                        is_text_area = True
                        break
                if is_text_area:
                    continue
                
                colored_rects.append({
                    'page': page_num,
                    'x': round(rect.x0, 2),
                    'y': round(rect.y0, 2),
                    'width': round(rect.width, 2),
                    'height': round(rect.height, 2),
                    'area': round(rect.width * rect.height, 2),
                })

        # 方法2: 通过注释(Annotation)识别
        for annot in page.annots():
            if annot.type[0] in (2, 8, 22):  # Square, Highlight, Stamp 等
                color = annot.colors.get('stroke') or annot.colors.get('fill')
                if _is_colored_box(color):
                    rect = annot.rect
                    if rect.width >= 15 and rect.height >= 10:
                        rect_area = rect.width * rect.height
                        if rect_area < 200:
                            continue
                        # 排除极端细长条
                        if rect.width / rect.height > 20 or rect.height / rect.width > 20:
                            continue
                        # 同样排除页面边框
                        if rect_area > page_area * 0.9:
                            continue
                        if (abs(rect.x0 - page_rect.x0) < 5 and 
                            abs(rect.y0 - page_rect.y0) < 5 and
                            abs(rect.x1 - page_rect.x1) < 5 and
                            abs(rect.y1 - page_rect.y1) < 5):
                            continue
                        colored_rects.append({
                            'page': page_num,
                            'x': round(rect.x0, 2),
                            'y': round(rect.y0, 2),
                            'width': round(rect.width, 2),
                            'height': round(rect.height, 2),
                            'area': round(rect.width * rect.height, 2),
                        })

    doc.close()

    # 去重：合并坐标相近的矩形
    colored_rects = _dedup_rects(colored_rects)
    # 按面积从大到小排序
    colored_rects.sort(key=lambda r: r['area'], reverse=True)

    # 过滤嵌套内边框：如果一个框完全包含在另一个框内，且面积 > 外层框的 60%，
    # 则认为是内边框/描边副本，予以排除
    filtered = []
    for i, r in enumerate(colored_rects):
        is_inner_border = False
        for j, outer in enumerate(colored_rects):
            if i == j:
                continue
            # 检查 r 是否几乎完全在 outer 内部
            if (r['x'] >= outer['x'] - 2 and 
                r['y'] >= outer['y'] - 2 and
                r['x'] + r['width'] <= outer['x'] + outer['width'] + 2 and
                r['y'] + r['height'] <= outer['y'] + outer['height'] + 2):
                # 面积接近外层框，认为是内边框/描边副本
                if r['area'] > outer['area'] * 0.6:
                    is_inner_border = True
                    break
        if not is_inner_border:
            filtered.append(r)
    colored_rects = filtered

    # 最多返回5个框
    return colored_rects[:5]


# 保留旧函数名作为别名，兼容现有调用
find_red_rectangles = find_colored_rectangles


def _is_colored_box(color):
    """判断颜色是否为有颜色的框（排除白色/近白色/透明/无色）"""
    if not color:
        return False
    if len(color) >= 3:
        r, g, b = color[0], color[1], color[2]
        # 排除白色和近白色（所有通道都接近1）
        if r > 0.95 and g > 0.95 and b > 0.95:
            return False
        # 排除透明/无色
        if r == 0 and g == 0 and b == 0 and len(color) == 4 and color[3] == 0:
            return False
        # 其他所有颜色（红、黑、蓝、绿、黄等）都认为是有效框
        return True
    elif len(color) == 4:
        # CMYK
        c, m, y, k = color[0], color[1], color[2], color[3]
        # 排除白色（C=M=Y=0, K=0）
        if c == 0 and m == 0 and y == 0 and k == 0:
            return False
        return True
    elif len(color) == 1:
        # 灰度，排除白色
        return color[0] < 0.95
    return False


# 保留旧函数名作为别名
_is_red = _is_colored_box


def _dedup_rects(rects, tolerance=2.0):
    """去重：坐标相差不超过tolerance的矩形视为同一个"""
    if not rects:
        return rects
    unique = []
    for r in rects:
        is_dup = False
        for u in unique:
            if (abs(r['x'] - u['x']) < tolerance and
                abs(r['y'] - u['y']) < tolerance and
                abs(r['width'] - u['width']) < tolerance and
                abs(r['height'] - u['height']) < tolerance):
                is_dup = True
                break
        if not is_dup:
            unique.append(r)
    return unique


def extract_red_box_area_mm(file_path, rect_index=0):
    """
    提取指定红框区域的尺寸（mm）
    返回 (length_mm, width_mm) 或 None
    """
    rects = find_red_rectangles(file_path)
    if not rects or rect_index >= len(rects):
        return None
    r = rects[rect_index]
    doc = fitz.open(file_path)
    page = doc[0]
    # 点转mm: 1点 = 1/72英寸 = 25.4/72 mm
    pt_to_mm = 25.4 / 72.0
    length_mm = round(r['width'] * pt_to_mm, 2)
    width_mm = round(r['height'] * pt_to_mm, 2)
    doc.close()
    return length_mm, width_mm


import re


def extract_quantity_from_text(text):
    """从文字中提取数量，如'3块'、'x3'、'数量3'等"""
    if not text:
        return 1
    patterns = [
        r'(\d+)\s*块',      # "3块"
        r'[×xX]\s*(\d+)',   # "x3", "×3"
        r'数量\s*[:：]?\s*(\d+)',  # "数量:3"
        r'(\d+)\s*个',      # "3个"
        r'(\d+)\s*只',      # "3只"
        r'(\d+)\s*片',      # "3片"
        r'(\d+)\s*张',      # "3张"
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))
    return 1


def smart_extract_boxes(file_path):
    """
    智能识别PDF中所有框及其对应的数量
    对尺寸相同的框去重（认为是同一内容的重复）
    返回: [{'length_mm': ..., 'width_mm': ..., 'quantity': ..., 'nearby_text': ...}, ...]
    """
    rects = find_colored_rectangles(file_path)
    if not rects:
        return []

    doc = fitz.open(file_path)
    pt_to_mm = 25.4 / 72.0
    results = []

    for r in rects:
        length_mm = round(r['width'] * pt_to_mm, 2)
        width_mm = round(r['height'] * pt_to_mm, 2)

        # 提取框附近文字（框下方扩展50pt区域）
        page = doc[r['page']]
        expanded_rect = fitz.Rect(
            r['x'] - 5, r['y'] - 5,
            r['x'] + r['width'] + 5, r['y'] + r['height'] + 80
        )
        # 确保在页面范围内
        expanded_rect = expanded_rect & page.rect
        nearby_text = page.get_textbox(expanded_rect)

        quantity = extract_quantity_from_text(nearby_text)

        results.append({
            'length_mm': length_mm,
            'width_mm': width_mm,
            'quantity': quantity,
            'nearby_text': nearby_text.strip().replace('\n', ' ')[:200],
            'x': r['x'],
            'y': r['y'],
        })

    doc.close()

    # 去重：坐标和尺寸都相近（误差±1mm/±2pt）的框视为同一内容，保留第一个
    # 修正：原逻辑只比较尺寸，会误删同一文件中多个相同尺寸的制版框
    unique = []
    for item in results:
        is_dup = False
        for u in unique:
            if (abs(item['length_mm'] - u['length_mm']) <= 1.0 and
                abs(item['width_mm'] - u['width_mm']) <= 1.0 and
                abs(item.get('x', 0) - u.get('x', 0)) <= 2.0 and
                abs(item.get('y', 0) - u.get('y', 0)) <= 2.0):
                is_dup = True
                break
        if not is_dup:
            unique.append(item)

    return unique


def smart_extract_boxes_for_order(file_path):
    """
    为下单流程提取框信息
    返回: {
        'boxes': [...],           # 所有唯一框列表
        'box_count': N,           # 框数量
        'first_length': ...,      # 第一个框的长
        'first_width': ...,       # 第一个框的宽
        'first_quantity': ...,    # 第一个框识别的数量
        'total_area_cm2': ...,    # 所有框的总面积(cm²)
    }
    """
    boxes = smart_extract_boxes(file_path)
    if not boxes:
        return None

    total_area = sum((b['length_mm'] * b['width_mm'] / 100.0) for b in boxes)

    return {
        'boxes': boxes,
        'box_count': len(boxes),
        'first_length': boxes[0]['length_mm'],
        'first_width': boxes[0]['width_mm'],
        'first_quantity': boxes[0]['quantity'],
        'total_area_cm2': round(total_area, 2),
    }
