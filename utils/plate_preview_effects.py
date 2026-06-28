"""
拼版效果图 — 版类视觉效果处理器

根据产品类型（浮雕/平烫金/腐蚀/菲林等）对PDF预览图应用不同的视觉效果，
让设计师在拼版效果图中直接看到每种版类的实际制版效果。

核心设计原则：
- 所有效果以白底为基础（模拟纸张/板材），确保拼版图整体干净
- 通过颜色、阴影、光泽来区分版类，而非改变整体背景色
- 效果必须一眼可辨：金色=烫金/平雕烫金，立体阴影=浮雕/击凸，内阴影=压纹
"""

import os
import logging
import fitz
import numpy as np
from scipy import ndimage
from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageDraw, ImageChops
from django.conf import settings

logger = logging.getLogger(__name__)


# ========== 版类 → 视觉效果映射 ==========
PLATE_EFFECT_MAP = {
    # 腐蚀版
    'etching_gold':      'gold_flat',       # 烫金版 → 金色平面光泽
    'emboss':            'emboss_deboss',   # 压纹版 → 凹陷压纹
    'relief_convex':     'relief_strong',   # 激凸版 → 强浮雕凸起
    'relief_concave':    'deboss_strong',   # 激凹版 → 强凹陷
    # 雕刻版
    'carving_flat':      'gold_satin',      # 平雕版 → 金色 satin（烫金/击凸共用）
    'carving_relief':    'relief_gold',     # 浮雕版 → 金色浮雕
    'carving_multi_layer': 'relief_gold_multi',  # 多层次浮雕
    # 树脂版
    'magnesium_concave_resin_convex_exposure': 'normal',
    'magnesium_concave_resin_convex_mold':     'normal',
    # 菲林
    'alignment_film':    'film_transparent',
    'uv_film':           'film_transparent',
}

PRODUCT_TO_PLATE_TYPE = {
    'etching_concave':  'emboss',
    'etching_convex':   'etching_gold',
    'etching_magnesium_concave_resin_convex': 'relief_convex',
    'etching_double_sided_magnesium_bump': 'relief_convex',
    'carving_flat_convex':       'carving_flat',
    'carving_flat_concave':       'carving_flat',
    'carving_relief_bump_gold': 'carving_relief',
    'carving_relief_multi_bump_gold':  'carving_multi_layer',
    'carving_relief_complex':  'carving_multi_layer',
    'resin_mold':  'magnesium_concave_resin_convex_mold',
    'resin_water': 'magnesium_concave_resin_convex_exposure',
    'film_alignment': 'alignment_film',
    'film_uv':        'uv_film',
}


def get_effect_type(product_name, plate_type_key=None):
    if plate_type_key:
        return PLATE_EFFECT_MAP.get(plate_type_key, 'normal')
    from utils.pricing_tiers import resolve_product_code
    product_name = resolve_product_code(product_name)
    pt = PRODUCT_TO_PLATE_TYPE.get(product_name)
    return PLATE_EFFECT_MAP.get(pt, 'normal')


def _ensure_rgb(img):
    if img.mode != 'RGB':
        return img.convert('RGB')
    return img


def _ensure_rgba(img):
    if img.mode != 'RGBA':
        return img.convert('RGBA')
    return img


def _remove_red_box_borders(page, boxes, border_width=3):
    """
    根据识别到的红框/标记框坐标，在 PDF 页面上应用 redaction，
    仅将框的边框线条填为白色，保留框内内容。
    红框仅用于计价，不应出现在效果预览图中。
    """
    for box in boxes:
        if box.get('page', 0) != page.number:
            continue
        x0 = box['x']
        y0 = box['y']
        x1 = x0 + box['width']
        y1 = y0 + box['height']

        # 只去除四周边框，内部内容保留
        # 上边框
        page.add_redact_annot(fitz.Rect(x0, y0, x1, y0 + border_width), fill=(1, 1, 1))
        # 下边框
        page.add_redact_annot(fitz.Rect(x0, y1 - border_width, x1, y1), fill=(1, 1, 1))
        # 左边框（避开上下边框已覆盖的角）
        page.add_redact_annot(fitz.Rect(x0, y0 + border_width, x0 + border_width, y1 - border_width), fill=(1, 1, 1))
        # 右边框
        page.add_redact_annot(fitz.Rect(x1 - border_width, y0 + border_width, x1, y1 - border_width), fill=(1, 1, 1))
    page.apply_redactions()


def remove_red_boxes_from_pdf(doc):
    """
    对 PDF 文档的每一页识别红框边框并去除。返回被去除的框列表。
    支持传入已打开的 fitz.Document 对象。
    """
    from utils.pdf_red_box import find_colored_rectangles
    boxes = find_colored_rectangles(doc)
    for page_num in range(len(doc)):
        page = doc[page_num]
        page_boxes = [b for b in boxes if b.get('page', 0) == page_num]
        if page_boxes:
            _remove_red_box_borders(page, page_boxes)
    return boxes


def _get_content_mask(img_gray):
    """内容掩码：黑色内容=255，白色背景=0。轻微模糊后阈值化，
    平滑文字/线条锯齿，减少距离变换和光照模型中的高频噪声。"""
    inv = ImageOps.invert(img_gray)
    inv = inv.filter(ImageFilter.GaussianBlur(radius=0.5))
    mask = inv.point(lambda x: 255 if x > 30 else 0, 'L')
    return mask


def _get_content_mask_soft(img_gray):
    """软边缘内容掩码"""
    inv = ImageOps.invert(img_gray)
    enhancer = ImageEnhance.Contrast(inv)
    inv = enhancer.enhance(2.0)
    return inv


def _emboss_metal(img_gray, direction='up', metal_color=None, strength=1.5, bg_gray=180):
    """
    通用金属浮雕效果生成器 - 基于距离变换 + 固定方向光照模型

    特点：
    - 使用 scipy 距离变换生成圆润的高度图
    - 使用固定方向光照模型（左上光源）产生 demo 风格的统一 3D 效果
    - 避免 PIL EMBOSS 滤镜导致的径向纹理
    - 灰底背景，强对比，强立体感

    direction: 'up' 凸起 / 'down' 凹陷
    metal_color: 金属基础色 (r, g, b)，None=银灰
    strength: 浮雕强度（1.0=轻柔，3.0=强烈）
    bg_gray: 背景灰度值（demo 风格约 180）
    """
    import numpy as np
    from scipy import ndimage

    w, h = img_gray.size

    # 硬内容掩码：黑色内容=255，白色背景=0
    mask = _get_content_mask(img_gray)
    mask_np = np.array(mask)

    # 1. 距离变换：内容内部距离边缘越远越高
    distance = ndimage.distance_transform_edt(mask_np)
    max_distance = distance.max()
    if max_distance > 0:
        # 限制最大高度（不超过最大距离的40%），避免实心内容中心过高产生同心圆
        distance = np.clip(distance, 0, max_distance * 0.4)
        distance = distance / (max_distance * 0.4) * 255

    # 2. 形状调整：让中心更平、边缘更陡，增强立体感
    gamma = 0.5 / max(strength, 0.3)
    distance = np.power(distance / 255.0, gamma) * 255

    # 3. 凹陷时反相高度图
    if direction == 'down':
        distance = 255 - distance

    # 4. 固定方向光照模型（左上光源）
    # 计算高度图梯度
    dx = ndimage.sobel(distance, axis=1).astype(np.float32)
    dy = ndimage.sobel(distance, axis=0).astype(np.float32)

    # 法线归一化
    length = np.sqrt(dx * dx + dy * dy + 1.0)
    length[length == 0] = 1.0
    nx, ny, nz = dx / length, dy / length, 1.0 / length

    # 左上光源方向（demo 风格）
    light = np.array([-1.0, -1.0, 1.5], dtype=np.float32)
    light = light / np.linalg.norm(light)

    # 漫反射 + 环境光（demo 风格：强明暗对比）
    ambient = 0.18
    diffuse = np.clip(nx * light[0] + ny * light[1] + nz * light[2], -1, 1)
    lighting = ambient + (1 - ambient) * diffuse

    # 直接裁剪到 [0,1]，保留自然的高光/阴影对比
    lighting = np.clip(lighting, 0.0, 1.0)

    # 增强对比度（gamma 调整让高光更突出、暗部更深）
    lighting = np.power(lighting, 0.8)
    lighting = (lighting * 255).astype(np.uint8)

    # 5. 色调映射到金属色
    contrast_factor = 2.0 + strength * 0.8
    emboss = Image.fromarray(lighting, 'L')
    if metal_color:
        r_base, g_base, b_base = metal_color
        r = emboss.point(lambda x: max(0, min(255, int(r_base + (x - 128) * contrast_factor))))
        g = emboss.point(lambda x: max(0, min(255, int(g_base + (x - 128) * contrast_factor))))
        b = emboss.point(lambda x: max(0, min(255, int(b_base + (x - 128) * contrast_factor))))
        result = Image.merge('RGB', (r, g, b))
    else:
        # 银灰色映射：以 bg_gray 为中性灰
        r = emboss.point(lambda x: int(bg_gray + (x - 128) * contrast_factor))
        g = emboss.point(lambda x: int(bg_gray + (x - 128) * contrast_factor))
        b = emboss.point(lambda x: int(bg_gray + 5 + (x - 128) * (contrast_factor * 0.95)))
        result = Image.merge('RGB', (r, g, b))

    # 6. 添加强烈投影/高光边缘（demo 风格）
    if strength >= 0.5:
        edges = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(radius=2))
        edge_mask = edges.point(lambda x: min(255, int(x * (0.6 + strength * 0.3))))

        # 方向决定高光/阴影位置
        if direction == 'up':
            shadow_color = Image.new('RGB', (w, h), (30, 30, 35))
            highlight_color = Image.new('RGB', (w, h), (255, 255, 250))
        else:
            shadow_color = Image.new('RGB', (w, h), (255, 255, 250))
            highlight_color = Image.new('RGB', (w, h), (30, 30, 35))

        # 高光（左上偏移）
        highlight = ImageChops.offset(highlight_color, -2, -2)
        result = Image.composite(highlight, result, edge_mask)

        # 阴影（右下偏移）
        shadow = ImageChops.offset(shadow_color, 2, 2)
        result = Image.composite(shadow, result, edge_mask)

    # 7. 灰色背景合成（demo 风格：灰底，内容区带浮雕）
    bg = Image.new('RGB', (w, h), (bg_gray, bg_gray, bg_gray))
    result = Image.composite(result, bg, mask)

    return result


# ========== 核心视觉效果函数 ==========

def effect_normal(img):
    """普通效果：清晰黑白，白底黑字"""
    img = _ensure_rgb(img)
    gray = img.convert('L')
    # 轻微增强对比度让线条更清晰
    enhancer = ImageEnhance.Contrast(gray)
    gray = enhancer.enhance(1.3)
    return gray.convert('RGB')


def effect_gold_flat(img, direction='up', strength=1.5):
    """
    金色平面效果（烫金版）- 基于EMBOSS的真实金属烫金
    金色底色 + 金属浮雕高光 + 颗粒质感，灰底背景
    """
    img = _ensure_rgba(img)
    gray = img.convert('L')
    w, h = img.size

    mask = _get_content_mask(gray)

    # 使用金属浮雕生成器，金色基础色
    metal = _emboss_metal(gray, direction=direction, metal_color=(230, 190, 40), strength=strength)

    # 添加额外的高光层（模拟镜面反射）
    emboss = gray.filter(ImageFilter.EMBOSS)
    hl_mask = emboss.point(lambda x: 255 if x > 150 else 0).filter(ImageFilter.GaussianBlur(radius=2))
    highlight = Image.new('RGB', (w, h), (255, 250, 200))
    metal = Image.composite(highlight, metal, hl_mask)

    # 灰底合成（demo 风格）
    bg_gray = 180
    bg = Image.new('RGB', (w, h), (bg_gray, bg_gray, bg_gray))
    result = Image.composite(metal, bg, mask)

    return result


def effect_gold_satin(img, direction='up', strength=1.5):
    """
    金色 satin 效果（平雕版-烫金/击凸）- 香槟金金属浮雕
    比 gold_flat 更柔和，偏香槟金，灰底背景
    """
    img = _ensure_rgba(img)
    gray = img.convert('L')
    w, h = img.size

    mask = _get_content_mask(gray)

    # 香槟金金属浮雕
    metal = _emboss_metal(gray, direction=direction, metal_color=(220, 200, 120), strength=strength)

    # 灰底合成（demo 风格）
    bg_gray = 180
    bg = Image.new('RGB', (w, h), (bg_gray, bg_gray, bg_gray))
    result = Image.composite(metal, bg, mask)

    return result


def _drop_shadow(img_gray, offset=(3, 3), blur=3, shadow_color=80):
    """
    为内容生成投影阴影（用于浮雕凸起效果）
    返回阴影层（RGBA）
    """
    mask = _get_content_mask(img_gray)
    # 阴影层
    shadow_mask = mask.point(lambda x: int(x * shadow_color / 255) if x > 0 else 0)
    shadow_r = Image.new('L', img_gray.size, 0)
    shadow_g = Image.new('L', img_gray.size, 0)
    shadow_b = Image.new('L', img_gray.size, 0)
    shadow = Image.merge('RGBA', (shadow_r, shadow_g, shadow_b, shadow_mask))
    # 模糊
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur))
    # 偏移
    shadow = ImageChops.offset(shadow, offset[0], offset[1])
    return shadow


def _bevel_effect(img_gray, direction='up'):
    """
    生成斜面/倒角效果，模拟3D厚度
    direction: 'up' = 凸起, 'down' = 凹陷
    """
    mask = _get_content_mask(img_gray)
    w, h = img_gray.size
    
    # 创建斜面效果
    bevel = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    
    # 使用边缘检测创建斜面
    edges = mask.filter(ImageFilter.FIND_EDGES)
    edges = edges.filter(ImageFilter.GaussianBlur(radius=1))
    
    if direction == 'up':
        # 凸起：左上亮，右下暗
        highlight = edges.point(lambda x: int(x * 0.8) if x > 30 else 0)
        shadow = edges.point(lambda x: int(x * 0.6) if x > 30 else 0)
        
        # 高光层（左上）
        hl = Image.merge('RGBA', (
            Image.new('L', (w, h), 255),
            Image.new('L', (w, h), 255),
            Image.new('L', (w, h), 255),
            highlight
        ))
        hl = ImageChops.offset(hl, -1, -1)
        
        # 阴影层（右下）
        sh = Image.merge('RGBA', (
            Image.new('L', (w, h), 0),
            Image.new('L', (w, h), 0),
            Image.new('L', (w, h), 0),
            shadow
        ))
        sh = ImageChops.offset(sh, 1, 1)
        
        return hl, sh
    else:
        # 凹陷：左上暗，右下亮
        shadow = edges.point(lambda x: int(x * 0.8) if x > 30 else 0)
        highlight = edges.point(lambda x: int(x * 0.6) if x > 30 else 0)
        
        # 阴影层（左上）
        sh = Image.merge('RGBA', (
            Image.new('L', (w, h), 0),
            Image.new('L', (w, h), 0),
            Image.new('L', (w, h), 0),
            shadow
        ))
        sh = ImageChops.offset(sh, -1, -1)
        
        # 高光层（右下）
        hl = Image.merge('RGBA', (
            Image.new('L', (w, h), 255),
            Image.new('L', (w, h), 255),
            Image.new('L', (w, h), 255),
            highlight
        ))
        hl = ImageChops.offset(hl, 1, 1)
        
        return hl, sh


def _emboss_3d(img_gray, depth=3):
    """
    生成3D浮雕效果（使用PIL的EMBOSS滤镜增强）
    """
    # 使用EMBOSS滤镜
    embossed = img_gray.filter(ImageFilter.EMBOSS)
    # 增强对比度
    enhancer = ImageEnhance.Contrast(embossed)
    embossed = enhancer.enhance(1.5)
    return embossed


def _inner_shadow(img_gray, offset=(-2, -2), blur=2, shadow_color=120):
    """
    为内容生成内阴影（用于压纹凹陷效果）
    """
    mask = _get_content_mask(img_gray)
    # 内阴影：内容区内部有阴影
    shadow = Image.new('RGBA', img_gray.size, (0, 0, 0, 0))
    shadow_mask = mask.point(lambda x: int(x * shadow_color / 255) if x > 0 else 0)
    shadow_r = Image.new('L', img_gray.size, 0)
    shadow_g = Image.new('L', img_gray.size, 0)
    shadow_b = Image.new('L', img_gray.size, 0)
    shadow = Image.merge('RGBA', (shadow_r, shadow_g, shadow_b, shadow_mask))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur))
    shadow = ImageChops.offset(shadow, offset[0], offset[1])
    return shadow


def _highlight(img_gray, offset=(-2, -2), blur=2, highlight_color=200):
    """
    为内容生成高光（用于浮雕凸起效果）
    """
    mask = _get_content_mask(img_gray)
    highlight = Image.new('RGBA', img_gray.size, (0, 0, 0, 0))
    highlight_mask = mask.point(lambda x: int(x * highlight_color / 255) if x > 0 else 0)
    h_r = Image.new('L', img_gray.size, 255)
    h_g = Image.new('L', img_gray.size, 255)
    h_b = Image.new('L', img_gray.size, 255)
    highlight = Image.merge('RGBA', (h_r, h_g, h_b, highlight_mask))
    highlight = highlight.filter(ImageFilter.GaussianBlur(radius=blur))
    highlight = ImageChops.offset(highlight, offset[0], offset[1])
    return highlight


def effect_relief_strong(img, direction='up', strength=1.5):
    """
    强浮雕凸起效果（激凸版）- 基于EMBOSS的专业级银灰金属浮雕
    模拟真实金属凸起：EMBOSS滤镜 + 银灰色调 + 高光增强，灰底背景
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    mask = _get_content_mask(gray)

    # 银灰金属浮雕（凸起）
    metal = _emboss_metal(gray, direction=direction, metal_color=None, strength=strength)

    # 添加边缘高光增强立体感
    edges = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(radius=1))
    edge_hl = Image.new('RGB', (w, h), (255, 255, 255))
    metal = Image.composite(edge_hl, metal, edges.point(lambda x: int(x * 0.25)))

    # 灰底合成（demo 风格）
    bg_gray = 180
    bg = Image.new('RGB', (w, h), (bg_gray, bg_gray, bg_gray))
    result = Image.composite(metal, bg, mask)

    return result


def effect_emboss_deboss(img, direction='down', strength=1.5):
    """
    压纹凹陷效果（压纹版）- 基于EMBOSS的专业级凹陷
    模拟真实压痕：EMBOSS滤镜 + 银灰色调 + 凹陷方向，灰底背景
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    mask = _get_content_mask(gray)

    # 银灰金属浮雕（凹陷）
    metal = _emboss_metal(gray, direction=direction, metal_color=None, strength=strength)

    # 灰底合成（demo 风格）
    bg_gray = 180
    bg = Image.new('RGB', (w, h), (bg_gray, bg_gray, bg_gray))
    result = Image.composite(metal, bg, mask)

    return result


def effect_deboss_strong(img, direction='down', strength=1.5):
    """
    强凹陷效果（激凹版）- 基于EMBOSS的深凹陷
    更强的凹陷感和立体感，灰底背景
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    mask = _get_content_mask(gray)

    # 银灰金属浮雕（强凹陷）
    metal = _emboss_metal(gray, direction=direction, metal_color=None, strength=strength)

    # 灰底合成（demo 风格）
    bg_gray = 180
    bg = Image.new('RGB', (w, h), (bg_gray, bg_gray, bg_gray))
    result = Image.composite(metal, bg, mask)

    return result


def effect_relief_gold(img, direction='up', strength=1.5):
    """
    金色浮雕效果（浮雕版）- 基于EMBOSS的专业级金色浮雕
    模拟真实金属浮雕：EMBOSE滤镜 + 金色调 + 高光增强，灰底背景
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    mask = _get_content_mask(gray)

    # 金色金属浮雕（凸起）
    metal = _emboss_metal(gray, direction=direction, metal_color=(255, 215, 0), strength=strength)

    # 添加边缘高光增强立体感
    edges = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(radius=1))
    edge_hl = Image.new('RGB', (w, h), (255, 250, 220))
    metal = Image.composite(edge_hl, metal, edges.point(lambda x: int(x * 0.2)))

    # 灰底合成（demo 风格）
    bg_gray = 180
    bg = Image.new('RGB', (w, h), (bg_gray, bg_gray, bg_gray))
    result = Image.composite(metal, bg, mask)

    return result


def effect_relief_gold_multi(img, direction='up', strength=1.5):
    """
    多层金色浮雕效果（多层次浮雕版）- 基于EMBOSE的增强金色浮雕
    更强的浮雕感和金色金属光泽，灰底背景
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    mask = _get_content_mask(gray)

    # 强金色金属浮雕（凸起，更高强度）
    metal = _emboss_metal(gray, direction=direction, metal_color=(255, 215, 0), strength=strength)

    # 添加强边缘高光
    edges = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(radius=1))
    edge_hl = Image.new('RGB', (w, h), (255, 250, 220))
    metal = Image.composite(edge_hl, metal, edges.point(lambda x: int(x * 0.25)))

    # 灰底合成（demo 风格）
    bg_gray = 180
    bg = Image.new('RGB', (w, h), (bg_gray, bg_gray, bg_gray))
    result = Image.composite(metal, bg, mask)

    return result


def effect_film_transparent(img):
    """菲林半透明效果 - 白底 + 半透明淡蓝灰 + 黑字"""
    img = _ensure_rgba(img)
    gray = img.convert('L')
    mask = _get_content_mask(gray)

    # 半透明菲林底色（淡蓝灰，80%不透明度）
    film = Image.new('RGBA', img.size, (210, 218, 235, 200))
    # 黑色内容
    content = Image.new('RGBA', img.size, (10, 10, 15, 255))
    content.putalpha(mask)

    bg = Image.new('RGBA', img.size, (255, 255, 255, 255))
    result = Image.alpha_composite(bg, film)
    result = Image.alpha_composite(result, content)

    return result.convert('RGB')


# ========== 效果分发器 ==========
EFFECT_FUNCTIONS = {
    'normal':            effect_normal,
    'gold_flat':         effect_gold_flat,
    'gold_satin':        effect_gold_satin,
    'emboss_deboss':     effect_emboss_deboss,
    'relief_strong':     effect_relief_strong,
    'deboss_strong':     effect_deboss_strong,
    'relief_gold':       effect_relief_gold,
    'relief_gold_multi': effect_relief_gold_multi,
    'film_transparent':  effect_film_transparent,
}


def apply_plate_effect(img, effect_type, emboss_direction='up', emboss_strength=1.5):
    func = EFFECT_FUNCTIONS.get(effect_type, effect_normal)
    try:
        if effect_type in ('gold_flat', 'gold_satin', 'relief_strong', 'emboss_deboss',
                           'deboss_strong', 'relief_gold', 'relief_gold_multi'):
            return func(img, direction=emboss_direction, strength=emboss_strength)
        return func(img)
    except Exception as e:
        logger.exception('版类效果处理失败: %s', effect_type)
        return effect_normal(img)


def generate_effect_preview(pdf_path, output_path, product_name, plate_type_key=None,
                            dpi=150, emboss_direction='up', emboss_strength=1.5):
    """从PDF文件生成带版类视觉效果的预览图"""
    try:
        if not os.path.isabs(pdf_path):
            pdf_path = os.path.join(settings.MEDIA_ROOT, pdf_path)
        if not os.path.isabs(output_path):
            output_path = os.path.join(settings.MEDIA_ROOT, output_path)

        if not os.path.exists(pdf_path):
            return None

        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return None

        # 去除红框标记线：红框仅用于计价，不应出现在效果预览图中
        remove_red_boxes_from_pdf(doc)

        page = doc[0]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()

        effect_type = get_effect_type(product_name, plate_type_key)
        result = apply_plate_effect(img, effect_type,
                                    emboss_direction=emboss_direction,
                                    emboss_strength=emboss_strength)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        result.save(output_path, "PNG")

        return output_path
    except Exception as e:
        logger.exception('生成版类效果图失败')
        return None


def get_effect_name(product_name, plate_type_key=None):
    effect_type = get_effect_type(product_name, plate_type_key)
    names = {
        'normal': '普通',
        'gold_flat': '烫金光泽',
        'gold_satin': '金色平雕',
        'emboss_deboss': '压纹凹陷',
        'relief_strong': '激凸浮雕',
        'deboss_strong': '激凹凹陷',
        'relief_gold': '金色浮雕',
        'relief_gold_multi': '多层金色浮雕',
        'film_transparent': '菲林半透明',
    }
    return names.get(effect_type, '普通')


# ========== 3D 渲染辅助函数 ==========

def generate_displacement_map(img, effect_type='relief', intensity=1.0):
    """
    生成高度图（Displacement Map）用于 Three.js 3D 渲染
    
    专业浮雕高度图：模拟圆润的浮雕边缘过渡
    - 内容中心最高
    - 边缘逐渐降低（圆润过渡）
    - 背景最低
    
    返回: PIL Image (L模式，灰度图)
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    
    # 反转：黑色内容=255（高），白色背景=0（低）
    inv = ImageOps.invert(gray)
    
    # 增强对比度
    enhancer = ImageEnhance.Contrast(inv)
    inv = enhancer.enhance(3.0)
    
    # 获取内容掩码
    mask = inv.point(lambda x: 255 if x > 15 else 0, 'L')
    
    # 计算距离变换：内容内部距离边缘的距离
    # 距离边缘越远 = 越高（中心最高）
    mask_np = np.array(mask)
    
    # 距离变换：每个像素到最近背景像素的距离
    distance = ndimage.distance_transform_edt(mask_np)
    
    # 归一化到0-255
    if distance.max() > 0:
        distance = (distance / distance.max()) * 255
    
    # 应用圆滑曲线（让顶部更平，边缘更陡）
    distance = np.power(distance / 255.0, 0.7) * 255
    
    height = Image.fromarray(distance.astype(np.uint8), 'L')
    
    # 根据效果类型调整
    if effect_type in ('emboss_deboss', 'deboss_strong'):
        # 凹陷：反转高度
        height = ImageOps.invert(height)
    elif effect_type in ('gold_flat', 'gold_satin'):
        # 烫金：降低高度
        height = height.point(lambda x: int(x * 0.3))
    else:
        # 浮雕：保持高度，轻微增强
        height = height.point(lambda x: int(x * 0.9))
    
    # 轻微平滑（保持圆润边缘）
    height = height.filter(ImageFilter.GaussianBlur(radius=2))
    
    # 应用强度
    if intensity != 1.0:
        height = height.point(lambda x: int(x * intensity))
    
    return height


def generate_normal_map(img, effect_type='relief', strength=3.0):
    """
    生成法线贴图（Normal Map）用于 Three.js 3D 渲染

    法线贴图可以让平面产生凹凸感，配合光照实现逼真3D效果
    【修复】使用 numpy 向量化实现 Sobel 梯度，替代纯 Python 双层循环，性能提升约 50~100 倍
    """
    displacement = generate_displacement_map(img, effect_type, intensity=1.0)

    # 将灰度高度图转换为 numpy 数组并归一化到 [0, 1]
    disp = np.array(displacement, dtype=np.float32) / 255.0

    # Sobel 核（与原版采样范围一致：左右/上下各 2 像素）
    # 水平梯度
    kernel_x = np.array([[-1, 0, 1],
                         [-2, 0, 2],
                         [-1, 0, 1]], dtype=np.float32)
    # 垂直梯度
    kernel_y = np.array([[-1, -2, -1],
                         [ 0,  0,  0],
                         [ 1,  2,  1]], dtype=np.float32)

    dx = ndimage.convolve(disp, kernel_x) * strength
    dy = ndimage.convolve(disp, kernel_y) * strength
    dz = np.ones_like(disp, dtype=np.float32)

    # 归一化
    length = np.sqrt(dx*dx + dy*dy + dz*dz)
    length[length == 0] = 1.0
    dx, dy, dz = dx / length, dy / length, dz / length

    # 转换到 RGB [0, 255]
    r = ((dx * 0.5 + 0.5) * 255).astype(np.uint8)
    g = ((dy * 0.5 + 0.5) * 255).astype(np.uint8)
    b = (dz * 255).astype(np.uint8)

    rgb = np.stack([r, g, b], axis=-1)
    return Image.fromarray(rgb, 'RGB')


def generate_3d_preview_maps(pdf_path, output_dir, product_name, plate_type_key=None,
                             dpi=72, emboss_direction='up', emboss_strength=1.5):
    """
    生成 Three.js 3D 预览所需的贴图：
    - color_map.png: 彩色纹理（带版类效果）
    - displacement_map.png: 高度图
    - normal_map.png: 法线贴图
    
    返回: {
        'color_url': '...',
        'displacement_url': '...',
        'normal_url': '...',
        'width': w,
        'height': h,
    }
    """
    try:
        if not os.path.isabs(pdf_path):
            pdf_path = os.path.join(settings.MEDIA_ROOT, pdf_path)
        if not os.path.isabs(output_dir):
            output_dir = os.path.join(settings.MEDIA_ROOT, output_dir)
        
        if not os.path.exists(pdf_path):
            return None
        
        os.makedirs(output_dir, exist_ok=True)
        
        # 打开PDF
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            doc.close()
            return None

        # 去除红框标记线：红框仅用于计价，不应出现在 3D 预览贴图中
        remove_red_boxes_from_pdf(doc)

        page = doc[0]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()

        # 限制尺寸（3D贴图过大时法线计算会很慢，保持1200）
        max_size = 1200
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # 获取效果类型
        effect_type = plate_type_key or get_effect_type(product_name)
        
        # 生成彩色效果图
        color_img = apply_plate_effect(img, effect_type,
                                       emboss_direction=emboss_direction,
                                       emboss_strength=emboss_strength)
        
        # 生成高度图和法线贴图
        displacement = generate_displacement_map(img, effect_type,
                                                 intensity=emboss_strength / 1.5)
        normal = generate_normal_map(img, effect_type)
        
        # 保存文件
        base_name = os.urandom(8).hex()
        color_path = os.path.join(output_dir, f"{base_name}_color.png")
        disp_path = os.path.join(output_dir, f"{base_name}_disp.png")
        normal_path = os.path.join(output_dir, f"{base_name}_normal.png")
        
        color_img.save(color_path, "PNG")
        displacement.save(disp_path, "PNG")
        normal.save(normal_path, "PNG")
        
        return {
            'color_url': settings.MEDIA_URL + f"customer_previews/{base_name}_color.png",
            'displacement_url': settings.MEDIA_URL + f"customer_previews/{base_name}_disp.png",
            'normal_url': settings.MEDIA_URL + f"customer_previews/{base_name}_normal.png",
            'width': img.width,
            'height': img.height,
        }
    except Exception:
        logger.exception('生成3D预览贴图失败')
        return None
