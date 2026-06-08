"""
PDF框识别工具
从客户上传的PDF中提取任意颜色的矩形框（制版内容区域）
支持红色、黑色、蓝色等各种颜色的框，排除白色/透明框

2025-06-02 修复记录：
1. 放宽文字区域过滤阈值（75%→90%），避免误删含文字的有效红框
2. 放宽绘图路径 items 限制（15→25），避免漏识别复杂路径组成的矩形
3. 扩大数量文字搜索范围（框四周各80pt），提高数量识别率
4. 修复 CMYK/灰度白色判断的浮点数精度问题
5. 增加红色框优先权重，优先识别红色标记框
6. 增加日志输出，便于排查识别问题

2025-06-04 修复记录：
1. 【关键修复】排除纯填充（fill-only）的小图形，避免转曲文字/装饰被误认为框
   - 真正的制版框是空心描边（stroke有颜色，fill=None）
   - 文字转曲后是实心填充（stroke=None，fill有颜色）
2. 【增强】数量语义理解：支持"烫板 3块"等带制版上下文的数量识别（默认每个框）

2025-06-06 性能优化：
1. 【延迟文字提取】先对drawings做基础过滤，过滤后再提取文字块，避免无效计算
2. 【减少嵌套循环】文字区域过滤改用提前break和批量检测
3. 【避免重复打开文件】smart_extract_boxes复用find_colored_rectangles已解析的文档
4. 【提前退出】只处理前3页，每页最多处理200个drawings，防止超大文件卡死
5. 【减少重复计算】缓存rect_area，避免多次乘法
"""

import fitz
import logging
import time

logger = logging.getLogger(__name__)

# 性能参数
MAX_PAGES = 3           # 最多处理3页
MAX_DRAWINGS_PER_PAGE = 200  # 每页最多处理200个绘图元素
MAX_CANDIDATES = 50     # 最多保留50个候选框进入文字过滤阶段


def find_colored_rectangles(file_path_or_doc):
    """
    识别PDF页面中的有效制版框（排除文字笔画、装饰元素、内嵌描边等干扰）
    返回 [{x, y, width, height, area}, ...] 列表，按面积从大到小排序
    
    支持传入文件路径(str)或已打开的fitz.Document对象，避免重复打开文件
    
    过滤策略：
    1. 最小尺寸放宽到 15x10pt（约5.3x3.5mm），保留小制版框
    2. 排除页面边框/裁切框（与页面边界重合或面积超过页面90%）
    3. 排除极端细长条（宽高比>20）和路径过于复杂的图形（>25个items）
    4. 排除嵌套在内的大面积内边框（面积>外层60%的内嵌框）
    5. 排除与文字块高度重叠的区域（阈值从75%放宽到90%，避免误删含文字的有效框）
    6. 【新增】排除纯填充（fill-only）的小图形（<28pt/10mm），避免文字/装饰被误认为框
    7. 最多返回5个框
    """
    start_time = time.time()
    
    # 支持传入已打开的文档对象或文件路径
    if isinstance(file_path_or_doc, str):
        doc = fitz.open(file_path_or_doc)
        should_close = True
    else:
        doc = file_path_or_doc
        should_close = False
    
    colored_rects = []
    pages_to_process = min(len(doc), MAX_PAGES)

    for page_num in range(pages_to_process):
        page = doc[page_num]
        page_rect = page.rect
        page_area = page_rect.width * page_rect.height
        
        # 【优化】延迟提取文字块：先过滤drawings，有候选框后再提取文字
        text_rects = None
        
        # 方法1: 通过绘图路径识别
        drawings = page.get_drawings()
        
        # 【优化】限制每页处理的drawings数量，防止超大文件卡死
        if len(drawings) > MAX_DRAWINGS_PER_PAGE:
            logger.info(f"[红框识别] 第{page_num+1}页绘图元素过多({len(drawings)}个)，只处理前{MAX_DRAWINGS_PER_PAGE}个")
            drawings = drawings[:MAX_DRAWINGS_PER_PAGE]
        
        for d in drawings:
            color = d.get('color')
            fill = d.get('fill')
            # 检测任意有颜色的框（排除白色/透明）
            is_colored_stroke = _is_colored_box(color)
            is_colored_fill = _is_colored_box(fill)
            # 红色框给予更高优先级（标记为红色专用框）
            is_red_stroke = _is_red_box(color)
            is_red_fill = _is_red_box(fill)

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
                # 简单矩形框通常 items <= 10；收紧到 25 以过滤短文字轮廓
                if len(items) > 25:
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
                
                # 【新增】过滤6：排除纯填充的小图形（文字转曲/装饰元素）
                # 真正的制版框是空心描边（stroke有颜色，fill=None）
                # 文字转曲后是实心填充（stroke=None，fill有颜色）
                has_stroke = _is_colored_box(color)
                has_fill = _is_colored_box(fill)
                if not has_stroke and has_fill:
                    # 纯填充图形，如果尺寸较小（<28pt ≈ 10mm），更可能是文字/装饰
                    if rect.width < 28 or rect.height < 28:
                        continue
                
                colored_rects.append({
                    'page': page_num,
                    'x': round(rect.x0, 2),
                    'y': round(rect.y0, 2),
                    'width': round(rect.width, 2),
                    'height': round(rect.height, 2),
                    'area': round(rect_area, 2),
                    'is_red': is_red_stroke or is_red_fill,
                })

        # 【优化】如果候选框太多，先裁剪到合理数量再提取文字做过滤
        if len(colored_rects) > MAX_CANDIDATES:
            # 按红色优先、面积从大到小排序，保留前MAX_CANDIDATES个
            colored_rects.sort(key=lambda r: (not r.get('is_red', False), -r['area']))
            colored_rects = colored_rects[:MAX_CANDIDATES]
        
        # 【优化】有候选框且需要文字过滤时，才提取文字块
        if colored_rects:
            text_blocks = page.get_text("blocks")
            text_rects = [fitz.Rect(b[:4]) for b in text_blocks]
            
            # 过滤7：排除与文字块高度重叠的区域（客户备注/文字注释）
            # 【修复】阈值从 75% 放宽到 90%，避免误删含文字的有效制版框
            # 同时增加面积判断：大于 3000pt²（约10cm×10cm）的框即使含文字也保留
            filtered_rects = []
            for r in colored_rects:
                if r['page'] != page_num:
                    filtered_rects.append(r)
                    continue
                    
                if r['area'] >= 3000:  # 大于3000pt²的框直接保留
                    filtered_rects.append(r)
                    continue
                
                # 【优化】批量检测文字重叠，提前break
                is_text_area = False
                r_fitz = fitz.Rect(r['x'], r['y'], r['x'] + r['width'], r['y'] + r['height'])
                for tr in text_rects:
                    intersect = r_fitz & tr
                    if intersect and intersect.get_area() > r['area'] * 0.90:
                        is_text_area = True
                        break
                if not is_text_area:
                    filtered_rects.append(r)
            
            colored_rects = filtered_rects

        # 方法2: 通过注释(Annotation)识别
        for annot in page.annots():
            if annot.type[0] in (2, 8, 22):  # Square, Highlight, Stamp 等
                color = annot.colors.get('stroke') or annot.colors.get('fill')
                is_colored = _is_colored_box(color)
                is_red = _is_red_box(color)
                if is_colored:
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
                            'area': round(rect_area, 2),
                            'is_red': is_red,
                        })

    if should_close:
        doc.close()

    # 去重：合并坐标相近的矩形
    colored_rects = _dedup_rects(colored_rects)
    
    # 【修复】优先按红色框排序，然后按面积排序
    # 红色框通常是客户明确标记的制版区域，应优先
    colored_rects.sort(key=lambda r: (not r.get('is_red', False), -r['area']))

    # 过滤嵌套内边框：如果一个框完全包含在另一个框内，且面积 > 外层框的 60%，
    # 则认为是内边框/描边副本，予以排除
    # 【优化】只对前20个框做嵌套检查
    filtered = []
    check_count = min(len(colored_rects), 20)
    for i in range(check_count):
        r = colored_rects[i]
        is_inner_border = False
        for j in range(check_count):
            if i == j:
                continue
            outer = colored_rects[j]
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
    # 保留未检查的框
    if len(colored_rects) > check_count:
        filtered.extend(colored_rects[check_count:])
    colored_rects = filtered

    # 【修复】优先识别红色框，但没有红色框时保留其他颜色的框
    # 避免客户使用黑色/蓝色等非红色标记框时完全无法识别
    red_rects = [r for r in colored_rects if r.get('is_red', False)]
    if red_rects:
        colored_rects = red_rects
        logger.info(f"[红框识别] 检测到红色标记框，过滤其他颜色，保留 {len(red_rects)} 个红色框")
    else:
        # 没有红色框时，保留所有有颜色的框（不再直接清空）
        logger.info(f"[红框识别] 未检测到红色标记框，保留 {len(colored_rects)} 个其他颜色框")
        # colored_rects 保持原样，不清空
    
    # 最多返回5个框
    result = colored_rects[:5]
    
    elapsed = time.time() - start_time
    if result:
        logger.info(f"[红框识别] 识别到 {len(result)} 个框，耗时 {elapsed:.2f}s: {result}")
    else:
        logger.info(f"[红框识别] 未识别到有效框，耗时 {elapsed:.2f}s")
    
    return result


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
        # 【修复】排除白色（C=M=Y≈0, K≈0），使用容差避免浮点精度问题
        if abs(c) < 0.01 and abs(m) < 0.01 and abs(y) < 0.01 and abs(k) < 0.01:
            return False
        return True
    elif len(color) == 1:
        # 灰度，排除白色
        return color[0] < 0.95
    return False


def _is_red_box(color):
    """判断是否为明显的红色框（R高，G/B低）"""
    if not color:
        return False
    if len(color) >= 3:
        r, g, b = color[0], color[1], color[2]
        # 红色：R通道明显高于G和B
        if r > 0.5 and r > g + 0.15 and r > b + 0.15:
            return True
    elif len(color) == 4:
        # CMYK红色：M和Y较高，C和K较低
        c, m, y, k = color[0], color[1], color[2], color[3]
        if m > 0.3 and y > 0.3 and c < 0.3 and k < 0.5:
            return True
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
    # 点转mm: 1点 = 1/72英寸 = 25.4/72 mm
    pt_to_mm = 25.4 / 72.0
    length_mm = round(r['width'] * pt_to_mm, 2)
    width_mm = round(r['height'] * pt_to_mm, 2)
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


def extract_global_quantity_semantic(text):
    """
    从全局文字中提取数量语义
    返回: (quantity, mode)
      mode='each'  -> "各3块"，每个框都是3个
      mode='total' -> "共3块"，总共3个（需要分配）
      None         -> 没有找到全局数量语义
    """
    if not text:
        return None, None
    
    # "各3块"、"各 3 块"、"各3个"等
    match = re.search(r'各\s*(\d+)\s*[块个只片张]', text)
    if match:
        return int(match.group(1)), 'each'
    
    # "共3块"、"总共3块"等
    match = re.search(r'共\s*(\d+)\s*[块个只片张]', text)
    if match:
        return int(match.group(1)), 'total'
    
    # 【新增】"3块"（无"各"字前缀，但带制版上下文）
    # 如"2.0烫板 3块 送小彭" → 默认理解为每个框都做3块
    match = re.search(r'(\d+)\s*[块个只片张]', text)
    if match:
        plate_keywords = ['烫板', '烫金版', '腐蚀版', '雕刻版', '版', '板']
        has_plate_context = any(kw in text for kw in plate_keywords)
        if has_plate_context:
            return int(match.group(1)), 'each'
    
    return None, None


def smart_extract_boxes(file_path):
    """
    智能识别PDF中所有框及其对应的数量
    支持全局数量语义理解（如"各3块"）
    对尺寸相同的框去重（认为是同一内容的重复）
    返回: [{'length_mm': ..., 'width_mm': ..., 'quantity': ..., 'nearby_text': ...}, ...]
    """
    start_time = time.time()
    
    # 【优化】只打开一次文件，复用文档对象
    doc = fitz.open(file_path)
    
    rects = find_colored_rectangles(doc)
    if not rects:
        logger.info(f"[红框识别] {file_path} 未识别到框")
        doc.close()
        return []

    pt_to_mm = 25.4 / 72.0
    results = []

    # 【优化】只提取有框的页面的文字，而非所有页面
    pages_with_rects = set(r['page'] for r in rects)
    full_page_text = ""
    for page_num in pages_with_rects:
        if page_num < len(doc):
            full_page_text += doc[page_num].get_text()
    
    global_qty, global_mode = extract_global_quantity_semantic(full_page_text)
    if global_qty:
        logger.info(f"[红框识别] 检测到全局数量语义: {global_mode} {global_qty} 块")

    for r in rects:
        length_mm = round(r['width'] * pt_to_mm, 2)
        width_mm = round(r['height'] * pt_to_mm, 2)

        # 【修复】扩大数量文字搜索范围：框四周各扩展80pt，避免遗漏
        page = doc[r['page']]
        expanded_rect = fitz.Rect(
            r['x'] - 80, r['y'] - 80,
            r['x'] + r['width'] + 80, r['y'] + r['height'] + 80
        )
        # 确保在页面范围内
        expanded_rect = expanded_rect & page.rect
        nearby_text = page.get_textbox(expanded_rect)

        # 【改进】优先使用全局数量语义（如"各3块"）
        if global_qty and global_mode == 'each':
            quantity = global_qty
        else:
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

    elapsed = time.time() - start_time
    logger.info(f"[红框识别] {file_path} 去重后 {len(unique)} 个框，总耗时 {elapsed:.2f}s")
    return unique


def smart_extract_boxes_for_order(file_path):
    """
    为下单流程提取框信息
    【修复】total_area_cm2 也加入 5mm 版边，与前端和订单模型保持一致
    返回: {
        'boxes': [...],           # 所有唯一框列表
        'box_count': N,           # 框数量
        'first_length': ...,      # 第一个框的长
        'first_width': ...,       # 第一个框的宽
        'first_quantity': ...,    # 第一个框识别的数量
        'total_area_cm2': ...,    # 所有框的总面积(cm²)，含5mm版边
    }
    """
    boxes = smart_extract_boxes(file_path)
    if not boxes:
        logger.info(f"[红框识别] {file_path} 无框数据")
        return None

    # 【修复】计算总面积时加入 5mm 版边，与前端和 OrderItem.save() 保持一致
    total_area = sum(
        ((b['length_mm'] + 5.0) * (b['width_mm'] + 5.0) / 100.0) * b['quantity']
        for b in boxes
    )

    result = {
        'boxes': boxes,
        'box_count': len(boxes),
        'first_length': boxes[0]['length_mm'],
        'first_width': boxes[0]['width_mm'],
        'first_quantity': boxes[0]['quantity'],
        'total_area_cm2': round(total_area, 2),
    }
    logger.info(f"[红框识别] {file_path} 订单框信息: {result}")
    return result
