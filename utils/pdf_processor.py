"""
PDF处理工具
包含：面积计算、预览图生成
"""

import os
import fitz
from django.conf import settings


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


def generate_pdf_preview(pdf_path, output_filename, dpi=150):
    """
    生成PDF第一页的预览图
    :param pdf_path: PDF文件路径
    :param output_filename: 输出文件名（相对于MEDIA_ROOT）
    :param dpi: 分辨率
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
        pix = page.get_pixmap(matrix=mat)
        pix.save(output_path)
        doc.close()
        return settings.MEDIA_URL + output_filename
    except Exception as e:
        return None
