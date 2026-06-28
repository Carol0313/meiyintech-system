"""
拼版生产PDF生成器（矢量精确嵌入客户原始文件）

核心原则：
- 绝不对客户文件进行位图化渲染
- 使用 PyMuPDF show_pdf_page 将客户原始文件以矢量 Form XObject 形式嵌入
- 按红框数据精确裁剪，只提取实际需要生产的区域
- 支持 90° 旋转，旋转后图案不变形、不模糊
- 线条粗细、文字精度完全保留
"""

import os
import json
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile

import fitz  # PyMuPDF


# 单位转换常量
MM_TO_PT = 72 / 25.4  # 1 mm = 2.83464567 pt
PT_TO_MM = 25.4 / 72


def _add_crop_marks(page, pw_mm, ph_mm, mark_len_mm=5):
    """在PDF页面四角添加裁切标记"""
    mark_len = mark_len_mm * MM_TO_PT
    # 左上
    page.draw_line((0, 0), (mark_len, 0), color=(0, 0, 0), width=0.5)
    page.draw_line((0, 0), (0, mark_len), color=(0, 0, 0), width=0.5)
    # 右上
    page.draw_line((pw_mm * MM_TO_PT, 0), ((pw_mm - mark_len_mm) * MM_TO_PT, 0), color=(0, 0, 0), width=0.5)
    page.draw_line((pw_mm * MM_TO_PT, 0), (pw_mm * MM_TO_PT, mark_len), color=(0, 0, 0), width=0.5)
    # 左下
    page.draw_line((0, ph_mm * MM_TO_PT), (mark_len, ph_mm * MM_TO_PT), color=(0, 0, 0), width=0.5)
    page.draw_line((0, ph_mm * MM_TO_PT), (0, (ph_mm - mark_len_mm) * MM_TO_PT), color=(0, 0, 0), width=0.5)
    # 右下
    page.draw_line((pw_mm * MM_TO_PT, ph_mm * MM_TO_PT),
                   ((pw_mm - mark_len_mm) * MM_TO_PT, ph_mm * MM_TO_PT), color=(0, 0, 0), width=0.5)
    page.draw_line((pw_mm * MM_TO_PT, ph_mm * MM_TO_PT),
                   (pw_mm * MM_TO_PT, (ph_mm - mark_len_mm) * MM_TO_PT), color=(0, 0, 0), width=0.5)


def _get_red_box_clip_rect(order_item, box_index=0):
    """
    从 OrderItem 的 red_box_data 中提取指定索引的红框裁剪区域（单位：points）
    优先使用后端返回的 pt_* 字段；不存在时根据 mm 字段换算；最后回退 x/y/width/height。
    返回 fitz.Rect 或 None
    """
    if not order_item.red_box_data:
        return None
    try:
        boxes = json.loads(order_item.red_box_data)
        if not isinstance(boxes, list) or len(boxes) == 0:
            return None
        # 循环使用红框（quantity 可能大于红框数量）
        box = boxes[box_index % len(boxes)]

        # 优先使用后端识别出的原始 PDF 点坐标
        x = float(box.get('pt_x', 0) or 0)
        y = float(box.get('pt_y', 0) or 0)
        w = float(box.get('pt_width', 0) or 0)
        h = float(box.get('pt_height', 0) or 0)
        if w > 0 and h > 0:
            return fitz.Rect(x, y, x + w, y + h)

        # 其次根据 mm 字段换算（1 pt = 25.4/72 mm）
        mm_to_pt = 72.0 / 25.4
        length_mm = float(box.get('length_mm', 0) or 0)
        width_mm = float(box.get('width_mm', 0) or 0)
        if length_mm > 0 and width_mm > 0:
            return fitz.Rect(0, 0, length_mm * mm_to_pt, width_mm * mm_to_pt)

        # 兼容旧数据：直接读取 x/y/width/height（假设为 pt）
        x = float(box.get('x', 0))
        y = float(box.get('y', 0))
        w = float(box.get('width', 0))
        h = float(box.get('height', 0))
        if w <= 0 or h <= 0:
            return None
        return fitz.Rect(x, y, x + w, y + h)
    except Exception:
        return None


def _embed_customer_file_vector(page, rect_rect, file_path, rotation=0, clip_rect=None):
    """
    将客户原始文件以矢量方式嵌入到生产PDF的指定矩形中
    
    参数:
        page: fitz.Page 目标页面
        rect_rect: fitz.Rect 目标矩形（已转换为PDF坐标）
        file_path: 客户文件绝对路径
        rotation: 旋转角度（0/90/180/270）
        clip_rect: fitz.Rect 源文件中的裁剪区域（points）
    
    返回:
        True/False 是否成功
    """
    try:
        src_doc = fitz.open(file_path)
        if len(src_doc) == 0:
            src_doc.close()
            return False

        kwargs = {
            'overlay': True,
            'keep_proportion': True,
        }
        if clip_rect is not None:
            kwargs['clip'] = clip_rect
        if rotation:
            kwargs['rotate'] = rotation

        page.show_pdf_page(rect_rect, src_doc, 0, **kwargs)
        src_doc.close()
        return True
    except Exception:
        return False


def generate_plate_production_pdf(batch, output_filename=None, use_plate_file=False):
    """
    为 PlateBatch 生成生产用PDF文件
    
    核心要求：
    - 客户文件以矢量方式嵌入，绝不做位图化
    - 按红框精确裁剪，只取实际生产区域
    - 支持旋转，线条粗细和文字精度完全保留
    
    参数:
        batch: PlateBatch 实例
        output_filename: 输出文件名（不含路径）
        use_plate_file: 是否优先使用制版文件（plate_file）而非客户源文件（file）
    
    返回:
        (rel_path, url) 或 (None, None)
    """
    layout_data = {}
    if batch.layout_data:
        try:
            layout_data = json.loads(batch.layout_data)
        except Exception:
            pass

    rectangles = layout_data.get('rectangles', [])
    if not rectangles:
        return None, None

    pw = float(batch.plate_width)
    ph = float(batch.plate_height)

    # 创建新PDF，页面尺寸 = 板材尺寸（mm）
    doc = fitz.open()
    page = doc.new_page(width=pw * MM_TO_PT, height=ph * MM_TO_PT)

    # 预加载所有 OrderItem（含 red_box_data）
    order_item_map = {}
    for bi in batch.items.select_related('order_item').all():
        order_item_map[str(bi.order_item_id)] = bi.order_item

    # 绘制每个矩形的内容
    for rect in rectangles:
        rx = float(rect.get('x', 0))
        ry = float(rect.get('y', 0))
        rw = float(rect.get('width', 0))
        rh = float(rect.get('height', 0))
        rid = rect.get('id', '')
        order_sn = rect.get('order_sn', '')
        rotation = int(rect.get('rotation', 0))

        # 解析 order_item_id 和 box_index
        if '_' in rid:
            order_item_id, box_idx_str = rid.rsplit('_', 1)
            try:
                box_index = int(box_idx_str)
            except ValueError:
                box_index = 0
        else:
            order_item_id = rid
            box_index = 0

        # 找到对应的 OrderItem
        item = order_item_map.get(order_item_id)

        # 若旋转90/270度，实际占位宽高互换
        embed_rw, embed_rh = rw, rh
        if rotation in (90, 270):
            embed_rw, embed_rh = rh, rw

        # 坐标转换：拼版坐标系原点在左上角，y向下
        # PDF坐标系原点在左下角，y向上
        x1 = rx * MM_TO_PT
        y1 = (ph - ry - embed_rh) * MM_TO_PT
        x2 = (rx + embed_rw) * MM_TO_PT
        y2 = (ph - ry) * MM_TO_PT
        rect_rect = fitz.Rect(x1, y1, x2, y2)

        embedded = False
        # 选择文件源：优先使用制版文件
        file_field = item.plate_file if use_plate_file and item and item.plate_file else (item.file if item else None)
        if file_field:
            file_path = os.path.join(settings.MEDIA_ROOT, file_field.name)
            if os.path.exists(file_path):
                # 获取红框裁剪区域
                clip_rect = _get_red_box_clip_rect(item, box_index)
                # 矢量嵌入
                embedded = _embed_customer_file_vector(
                    page, rect_rect, file_path,
                    rotation=rotation, clip_rect=clip_rect
                )

        if not embedded:
            # 矢量嵌入失败，绘制边框+文字（绝不使用位图回退）
            page.draw_rect(rect_rect, color=(0, 0, 0), width=0.5)
            page.insert_text((x1 + 2, y2 - 4), order_sn, fontsize=8, color=(0, 0, 0))

    # 添加裁切标记
    _add_crop_marks(page, pw, ph)

    # 添加标题信息（页面顶部）
    title = (
        f"批次:{batch.id.hex[:8].upper()} | "
        f"板材:{batch.plate_spec_name}({pw:.0f}x{ph:.0f}mm) | "
        f"利用率:{batch.usage_rate or 0:.1f}% | "
        f"件数:{len(rectangles)} | "
        f"时间:{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    page.insert_text((10 * MM_TO_PT, (ph - 5) * MM_TO_PT), title, fontsize=10, color=(0, 0, 0))

    # 保存PDF
    if output_filename is None:
        output_filename = f"plate_{batch.id.hex[:12]}_production.pdf"

    rel_path = f"plate_layouts/{output_filename}"
    abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)

    doc.save(abs_path, deflate=True, garbage=4)
    doc.close()

    url = f"{settings.MEDIA_URL}{rel_path}"
    return rel_path, url
