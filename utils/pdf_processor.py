"""
PDF处理工具
包含：面积计算、预览图生成、PDF转纯黑
"""

import os
import io
import fitz
from PIL import Image
from django.conf import settings
from django.core.files.storage import default_storage


def calculate_pdf_area(file_path):
    """
    计算PDF第一页的面积（cm²）
    :param file_path: 文件绝对路径或相对于MEDIA_ROOT的路径
    :return: float 面积(cm²)，失败返回0
    """
    try:
        if not os.path.isabs(file_path):
            file_path = os.path.join(settings.MEDIA_ROOT, file_path)
        if not os.path.exists(file_path):
            return 0
        doc = fitz.open(file_path)
        page = doc[0]
        rect = page.rect
        # 1 point = 1/72 inch = 25.4/72 mm
        width_mm = rect.width * 25.4 / 72
        height_mm = rect.height * 25.4 / 72
        area_cm2 = (width_mm * height_mm) / 100.0
        doc.close()
        return round(area_cm2, 2)
    except Exception as e:
        return 0


def convert_pdf_to_black(input_path, output_path=None, threshold=240):
    """
    将PDF所有内容转为纯黑色（保留页面尺寸，内容二值化为纯黑/白）
    用于制版预览，确保拼版效果清晰可见
    
    :param input_path: 输入PDF路径
    :param output_path: 输出PDF路径，None则覆盖原文件
    :param threshold: 灰度阈值，低于此值转为黑色（0-255）
    :return: 输出路径
    """
    if not os.path.isabs(input_path):
        input_path = os.path.join(settings.MEDIA_ROOT, input_path)
    
    if output_path is None:
        output_path = input_path
    elif not os.path.isabs(output_path):
        output_path = os.path.join(settings.MEDIA_ROOT, output_path)
    
    doc = fitz.open(input_path)
    new_doc = fitz.open()
    
    # 安全限制1：最多处理前 10 页，防止多页大文件拖垮服务器
    max_pages = 10
    page_count = min(len(doc), max_pages)
    
    # 安全限制2：单页最大渲染像素限制（约 16MP，平衡质量与内存）
    MAX_PIXELS = 4000 * 4000  # 1600万像素
    
    for page_idx in range(page_count):
        page = doc[page_idx]
        
        # 根据页面尺寸动态计算安全 DPI，避免内存爆炸
        rect = page.rect
        page_w_in = rect.width / 72.0
        page_h_in = rect.height / 72.0
        estimated_pixels = (page_w_in * 300) * (page_h_in * 300)
        
        if estimated_pixels > MAX_PIXELS:
            # 动态降低 DPI，确保不超过安全像素上限
            safe_dpi = max(72, int(300 * (MAX_PIXELS / estimated_pixels) ** 0.5))
        else:
            safe_dpi = 300
        
        pix = page.get_pixmap(colorspace=fitz.CS_GRAY, dpi=safe_dpi)
        img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
        
        # 二值化：所有非纯白内容转为纯黑，纯白保持白色
        # 使用阈值：低于threshold的转为黑色(0)，高于的转为白色(255)
        img_bw = img.point(lambda x: 0 if x < threshold else 255, '1')
        img_rgb = img_bw.convert("RGB")
        
        # 保存为PNG字节流
        img_bytes = io.BytesIO()
        img_rgb.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        # 在新PDF中创建同尺寸页面并插入处理后的图片
        new_page = new_doc.new_page(width=rect.width, height=rect.height)
        new_page.insert_image(rect, stream=img_bytes.read())
    
    new_doc.save(output_path)
    new_doc.close()
    doc.close()
    return output_path


def generate_pdf_preview(pdf_path, output_filename, dpi=150, black_only=False):
    """
    生成PDF第一页的预览图
    :param pdf_path: PDF文件路径
    :param output_filename: 输出文件名（相对于MEDIA_ROOT）
    :param dpi: 分辨率
    :param black_only: 是否转为纯黑预览（用于制版显示）
    :return: 输出文件URL 或 None
    """
    try:
        if not os.path.isabs(pdf_path):
            pdf_path = os.path.join(settings.MEDIA_ROOT, pdf_path)
        output_path = os.path.join(settings.MEDIA_ROOT, output_filename)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        doc = fitz.open(pdf_path)
        page = doc[0]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        
        if black_only:
            try:
                # 统一使用 fitz.CS_GRAY 整数枚举，避免 Colorspace 对象兼容问题
                pix = page.get_pixmap(matrix=mat, colorspace=fitz.CS_GRAY)
                img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
                img_bw = img.point(lambda x: 0 if x < 240 else 255, 'L')
                img_rgb = img_bw.convert("RGB")
                img_rgb.save(output_path)
            except Exception as e:
                # 灰度渲染失败时回退到普通 RGB 渲染
                print(f"[generate_pdf_preview] 灰度渲染失败，回退到RGB: {e}")
                pix = page.get_pixmap(matrix=mat)
                pix.save(output_path)
        else:
            pix = page.get_pixmap(matrix=mat)
            pix.save(output_path)
        doc.close()
        return settings.MEDIA_URL + output_filename
    except Exception as e:
        print(f"[generate_pdf_preview] 生成预览图失败: {e}")
        return None
