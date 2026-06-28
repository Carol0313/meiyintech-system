"""
PDF处理工具
包含：面积计算、预览图生成、PDF转纯黑
"""

import os
import io
import logging
import tempfile
import fitz
from PIL import Image
from django.conf import settings
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)


def _get_pdf_local_path(file_path):
    """
    获取 PDF 的本地路径。如果文件在本地不存在，尝试从存储后端（如 OSS）下载到临时文件。
    :param file_path: 文件路径（绝对路径或相对于 MEDIA_ROOT 的路径）
    :return: 本地文件路径，失败返回 None
    """
    if os.path.isabs(file_path):
        if os.path.exists(file_path):
            return file_path
    else:
        local_path = os.path.join(settings.MEDIA_ROOT, file_path)
        if os.path.exists(local_path):
            return local_path
        # 尝试从存储后端（OSS）读取到临时文件
        try:
            f = default_storage.open(file_path, 'rb')
            suffix = os.path.splitext(file_path)[1] or '.pdf'
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                for chunk in f.chunks():
                    tmp.write(chunk)
                return tmp.name
        except Exception:
            logger.exception('从存储后端读取文件失败: %s', file_path)
    return None


def calculate_pdf_area(file_path):
    """
    计算PDF第一页的面积（cm²）
    :param file_path: 文件绝对路径或相对于MEDIA_ROOT的路径
    :return: float 面积(cm²)，失败返回0
    """
    try:
        local_path = _get_pdf_local_path(file_path)
        if not local_path:
            return 0
        doc = fitz.open(local_path)
        page = doc[0]
        rect = page.rect
        # 1 point = 1/72 inch = 25.4/72 mm
        width_mm = rect.width * 25.4 / 72
        height_mm = rect.height * 25.4 / 72
        area_cm2 = (width_mm * height_mm) / 100.0
        doc.close()
        # 清理临时文件
        if local_path != file_path and not local_path.startswith(str(settings.MEDIA_ROOT)):
            try:
                os.unlink(local_path)
            except Exception:
                logger.warning('清理临时PDF文件失败: %s', local_path, exc_info=True)
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


def generate_pdf_preview(pdf_path, output_filename, dpi=150, black_only=False, return_size=False):
    """
    生成PDF第一页的预览图，并保存到Django默认存储后端（本地或OSS）
    :param pdf_path: PDF文件路径
    :param output_filename: 输出文件名（相对于MEDIA_ROOT）
    :param dpi: 分辨率
    :param black_only: 是否转为纯黑预览（用于制版显示）
    :param return_size: 是否同时返回图片尺寸 (width, height)
    :return: 输出文件URL，或 (URL, width, height) 元组，失败返回 None
    """
    try:
        local_pdf_path = _get_pdf_local_path(pdf_path)
        if not local_pdf_path:
            logger.warning("[generate_pdf_preview] PDF 文件不存在: %s", pdf_path)
            return None
        
        # 1. 生成预览图到临时文件
        import tempfile
        suffix = os.path.splitext(output_filename)[1] or '.png'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = tmp.name
        
        doc = fitz.open(local_pdf_path)
        page = doc[0]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        
        if black_only:
            try:
                # 【修复】使用 Colorspace 对象而非整数
                cs = fitz.Colorspace(fitz.CS_GRAY)
                pix = page.get_pixmap(matrix=mat, colorspace=cs)
                img = Image.frombytes("L", [pix.width, pix.height], pix.samples)
                img_bw = img.point(lambda x: 0 if x < 240 else 255, 'L')
                img_rgb = img_bw.convert("RGB")
                img_rgb.save(tmp_path)
            except Exception as e:
                logger.warning("[generate_pdf_preview] 灰度渲染失败，回退到RGB: %s", e)
                pix = page.get_pixmap(matrix=mat)
                pix.save(tmp_path)
        else:
            pix = page.get_pixmap(matrix=mat)
            pix.save(tmp_path)
        doc.close()
        
        # 2. 读取预览图尺寸
        from PIL import Image
        with Image.open(tmp_path) as im:
            img_width, img_height = im.size
        
        # 3. 上传到Django默认存储后端（本地或OSS）
        from django.core.files.base import File
        if not default_storage.exists(output_filename):
            with open(tmp_path, 'rb') as f:
                default_storage.save(output_filename, File(f))
        
        # 4. 清理临时文件
        try:
            os.unlink(tmp_path)
        except:
            pass
        if local_pdf_path != pdf_path and not local_pdf_path.startswith(str(settings.MEDIA_ROOT)):
            try:
                os.unlink(local_pdf_path)
            except:
                pass
        
        # 5. 返回存储后端的URL
        url = default_storage.url(output_filename)
        if return_size:
            return url, img_width, img_height
        return url
        
    except Exception as e:
        logger.exception("[generate_pdf_preview] 生成预览图失败: %s", e)
        return None
