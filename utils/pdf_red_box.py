"""
PDF红框识别工具
从客户上传的PDF中提取红色矩形框（制版内容区域）
"""

import fitz


def find_red_rectangles(file_path):
    """
    识别PDF页面中的红色矩形框
    返回 [{x, y, width, height, area}, ...] 列表，按面积从大到小排序
    """
    doc = fitz.open(file_path)
    red_rects = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # 方法1: 通过绘图路径识别
        drawings = page.get_drawings()
        for d in drawings:
            color = d.get('color')
            fill = d.get('fill')
            # stroke颜色为红色 (R高, G低, B低)
            is_red_stroke = _is_red(color)
            is_red_fill = _is_red(fill)

            if is_red_stroke or is_red_fill:
                rect = d.get('rect')
                if rect and rect.width > 5 and rect.height > 5:
                    red_rects.append({
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
                if _is_red(color):
                    rect = annot.rect
                    if rect.width > 5 and rect.height > 5:
                        red_rects.append({
                            'page': page_num,
                            'x': round(rect.x0, 2),
                            'y': round(rect.y0, 2),
                            'width': round(rect.width, 2),
                            'height': round(rect.height, 2),
                            'area': round(rect.width * rect.height, 2),
                        })

    doc.close()

    # 去重：合并坐标相近的矩形
    red_rects = _dedup_rects(red_rects)
    # 按面积从大到小排序
    red_rects.sort(key=lambda r: r['area'], reverse=True)
    return red_rects


def _is_red(color):
    """判断颜色是否为红色 (支持RGB/CMYK/Gray)"""
    if not color:
        return False
    if len(color) >= 3:
        r, g, b = color[0], color[1], color[2]
        # RGB中红色分量显著高于绿蓝，或CMYK中M高Y高C低K低
        if r > 0.7 and g < 0.4 and b < 0.4:
            return True
    elif len(color) == 1:
        # 灰度
        return False
    return False


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
