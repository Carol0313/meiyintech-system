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
import fitz
from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageDraw, ImageChops
from django.conf import settings


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


def _get_content_mask(img_gray):
    """内容掩码：黑色内容=255，白色背景=0"""
    inv = ImageOps.invert(img_gray)
    mask = inv.point(lambda x: 255 if x > 30 else 0, 'L')
    return mask


def _get_content_mask_soft(img_gray):
    """软边缘内容掩码"""
    inv = ImageOps.invert(img_gray)
    enhancer = ImageEnhance.Contrast(inv)
    inv = enhancer.enhance(2.0)
    return inv


# ========== 核心视觉效果函数 ==========

def effect_normal(img):
    """普通效果：清晰黑白，白底黑字"""
    img = _ensure_rgb(img)
    gray = img.convert('L')
    # 轻微增强对比度让线条更清晰
    enhancer = ImageEnhance.Contrast(gray)
    gray = enhancer.enhance(1.3)
    return gray.convert('RGB')


def effect_gold_flat(img):
    """
    金色平面效果（烫金版）
    白底 + 金色内容，带金属光泽渐变
    """
    img = _ensure_rgba(img)
    gray = img.convert('L')
    mask = _get_content_mask(gray)

    w, h = img.size
    # 亮金色到暗金色的垂直渐变
    gold = Image.new('RGB', (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(gold)
    for y in range(h):
        ratio = y / h if h > 0 else 0
        # 金色 RGB: 亮金 (255, 215, 0) → 暗金 (184, 134, 11)
        r = int(255 - ratio * 71)
        g = int(215 - ratio * 81)
        b = int(0 + ratio * 11)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    bg = Image.new('RGB', (w, h), (255, 255, 255))
    result = Image.composite(gold, bg, mask)
    result = result.filter(ImageFilter.SHARPEN)
    return result


def effect_gold_satin(img):
    """
    金色 satin 效果（平雕版-烫金/击凸）
    比 gold_flat 更柔和，偏香槟金
    """
    img = _ensure_rgba(img)
    gray = img.convert('L')
    mask = _get_content_mask(gray)

    w, h = img.size
    satin = Image.new('RGB', (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(satin)
    for y in range(h):
        ratio = y / h if h > 0 else 0
        # 香槟金 (250, 230, 160) → (200, 170, 80)
        r = int(250 - ratio * 50)
        g = int(230 - ratio * 60)
        b = int(160 - ratio * 80)
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    bg = Image.new('RGB', (w, h), (255, 255, 255))
    result = Image.composite(satin, bg, mask)
    result = result.filter(ImageFilter.SHARPEN)
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


def effect_relief_strong(img):
    """
    强浮雕凸起效果（激凸版）- 3D增强版
    白底 + 内容有立体投影 + 顶部高光 + 边缘立体感 + 斜面效果
    直观体现"凸起"感
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    # 白底
    bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))

    # 内容层（深灰色，模拟凸起部分的顶面）
    mask = _get_content_mask(gray)
    content = Image.new('RGBA', (w, h), (80, 80, 80, 255))
    content.putalpha(mask)

    # 3D斜面效果（边缘高光和阴影）
    bevel_hl, bevel_sh = _bevel_effect(gray, direction='up')

    # 多层阴影增强立体感
    # 主阴影（右下偏移，模拟光源从左上来）
    shadow1 = _drop_shadow(gray, offset=(4, 4), blur=4, shadow_color=100)
    # 次阴影（更远更淡）
    shadow2 = _drop_shadow(gray, offset=(8, 8), blur=8, shadow_color=50)
    # 接触阴影（模拟与底面接触处的暗部）
    shadow3 = _drop_shadow(gray, offset=(2, 2), blur=2, shadow_color=150)

    # 多层高光
    # 主高光（左上偏移）
    highlight1 = _highlight(gray, offset=(-3, -3), blur=3, highlight_color=220)
    # 次高光（更亮更小）
    highlight2 = _highlight(gray, offset=(-1, -1), blur=1, highlight_color=255)
    # 边缘反光（模拟金属/塑料边缘）
    edge_light = _highlight(gray, offset=(0, -2), blur=2, highlight_color=180)

    # 合成：白底 → 远阴影 → 近阴影 → 斜面阴影 → 内容 → 斜面高光 → 主高光 → 次高光 → 边缘光
    result = Image.alpha_composite(bg, shadow2)
    result = Image.alpha_composite(result, shadow1)
    result = Image.alpha_composite(result, shadow3)
    result = Image.alpha_composite(result, bevel_sh)
    result = Image.alpha_composite(result, content)
    result = Image.alpha_composite(result, bevel_hl)
    result = Image.alpha_composite(result, highlight1)
    result = Image.alpha_composite(result, edge_light)
    result = Image.alpha_composite(result, highlight2)

    return result.convert('RGB')


def effect_emboss_deboss(img):
    """
    压纹凹陷效果（压纹版）
    白底 + 内容有内阴影（凹陷感）
    直观体现"压下去"的感觉
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))

    # 内容层（深灰色，模拟凹陷区的底部）
    mask = _get_content_mask(gray)
    content = Image.new('RGBA', (w, h), (60, 60, 60, 255))
    content.putalpha(mask)

    # 内阴影（左上阴影 = 凹陷边缘）
    inner_shadow = _inner_shadow(gray, offset=(-3, -3), blur=3, shadow_color=140)

    # 底部微光（右下微亮 = 凹陷底部反光）
    bottom_glow = _highlight(gray, offset=(2, 2), blur=4, highlight_color=80)

    result = Image.alpha_composite(bg, inner_shadow)
    result = Image.alpha_composite(result, content)
    result = Image.alpha_composite(result, bottom_glow)

    return result.convert('RGB')


def effect_deboss_strong(img):
    """强凹陷效果（激凹版）- 更深的凹陷"""
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))
    mask = _get_content_mask(gray)
    content = Image.new('RGBA', (w, h), (40, 40, 40, 255))
    content.putalpha(mask)

    inner_shadow = _inner_shadow(gray, offset=(-4, -4), blur=4, shadow_color=180)
    bottom_glow = _highlight(gray, offset=(3, 3), blur=5, highlight_color=60)

    result = Image.alpha_composite(bg, inner_shadow)
    result = Image.alpha_composite(result, content)
    result = Image.alpha_composite(result, bottom_glow)

    return result.convert('RGB')


def effect_relief_gold(img):
    """
    金色浮雕效果（浮雕版）- 3D增强版
    白底 + 金色内容 + 立体投影 + 高光 + 金属光泽 + 斜面效果
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))

    # 金色内容层（带渐变）
    mask = _get_content_mask(gray)
    
    # 创建金色渐变（从左上到右下，模拟光照）
    gold_gradient = Image.new('RGB', (w, h), (0, 0, 0))
    draw = ImageDraw.Draw(gold_gradient)
    for y in range(h):
        for x in range(0, w, 10):  # 步进10像素加速
            ratio_x = x / w if w > 0 else 0
            ratio_y = y / h if h > 0 else 0
            ratio = (ratio_x + ratio_y) / 2
            # 亮金 (255, 223, 80) → 暗金 (184, 134, 11)
            r = int(255 - ratio * 71)
            g = int(223 - ratio * 89)
            b = int(80 - ratio * 69)
            draw.rectangle([x, y, x+10, y+1], fill=(r, g, b))
    
    # 应用mask到金色渐变
    gold_rgba = gold_gradient.convert('RGBA')
    gold_rgba.putalpha(mask)

    # 3D斜面效果
    bevel_hl, bevel_sh = _bevel_effect(gray, direction='up')

    # 多层阴影增强立体感
    shadow1 = _drop_shadow(gray, offset=(4, 4), blur=4, shadow_color=100)
    shadow2 = _drop_shadow(gray, offset=(8, 8), blur=8, shadow_color=50)
    shadow3 = _drop_shadow(gray, offset=(2, 2), blur=2, shadow_color=120)
    
    # 多层高光
    highlight1 = _highlight(gray, offset=(-3, -3), blur=3, highlight_color=200)
    highlight2 = _highlight(gray, offset=(-1, -1), blur=1, highlight_color=255)
    
    # 边缘光（模拟金属边缘反射）
    edge_light = _highlight(gray, offset=(0, -2), blur=2, highlight_color=150)
    
    # 金属反光条（模拟金属表面反射）
    reflection = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    refl_draw = ImageDraw.Draw(reflection)
    for i in range(0, h, 20):
        alpha = int(30 * (1 - abs(i - h/2) / (h/2)))
        refl_draw.line([(0, i), (w, i+2)], fill=(255, 255, 255, alpha))
    reflection_mask = mask.copy()
    reflection.putalpha(reflection_mask)

    # 合成：白底 → 远阴影 → 近阴影 → 接触阴影 → 斜面阴影 → 金色内容 → 斜面高光 → 边缘光 → 主高光 → 次高光 → 反光
    result = Image.alpha_composite(bg, shadow2)
    result = Image.alpha_composite(result, shadow1)
    result = Image.alpha_composite(result, shadow3)
    result = Image.alpha_composite(result, bevel_sh)
    result = Image.alpha_composite(result, gold_rgba)
    result = Image.alpha_composite(result, bevel_hl)
    result = Image.alpha_composite(result, edge_light)
    result = Image.alpha_composite(result, highlight1)
    result = Image.alpha_composite(result, reflection)
    result = Image.alpha_composite(result, highlight2)

    return result.convert('RGB')


def effect_relief_gold_multi(img):
    """
    多层金色浮雕效果（多层次浮雕版）
    更强的立体感 + 更亮的金色
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))

    mask = _get_content_mask(gray)
    # 更亮的金色
    gold_content = Image.new('RGB', (w, h), (255, 215, 0))  # 亮金 #FFD700
    gold_content_rgba = gold_content.convert('RGBA')
    gold_content_rgba.putalpha(mask)

    # 双层阴影
    shadow1 = _drop_shadow(gray, offset=(3, 3), blur=3, shadow_color=70)
    shadow2 = _drop_shadow(gray, offset=(6, 6), blur=6, shadow_color=40)
    highlight = _highlight(gray, offset=(-3, -3), blur=2, highlight_color=180)

    result = Image.alpha_composite(bg, shadow2)
    result = Image.alpha_composite(result, shadow1)
    result = Image.alpha_composite(result, gold_content_rgba)
    result = Image.alpha_composite(result, highlight)

    return result.convert('RGB')


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


def apply_plate_effect(img, effect_type):
    func = EFFECT_FUNCTIONS.get(effect_type, effect_normal)
    try:
        return func(img)
    except Exception as e:
        print(f"[plate_preview_effects] 效果处理失败 ({effect_type}): {e}")
        return effect_normal(img)


def generate_effect_preview(pdf_path, output_path, product_name, plate_type_key=None, dpi=150):
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
        page = doc[0]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()

        effect_type = get_effect_type(product_name, plate_type_key)
        result = apply_plate_effect(img, effect_type)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        result.save(output_path, "PNG")

        return output_path
    except Exception as e:
        print(f"[generate_effect_preview] 生成失败: {e}")
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
    
    根据效果类型生成不同的高度图：
    - relief/凸起: 内容区域高，背景低
    - deboss/凹陷: 内容区域低，背景高
    - gold_flat: 轻微凸起（烫金厚度）
    
    返回: PIL Image (L模式，灰度图)
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    
    # 反转：黑色内容=255（高），白色背景=0（低）
    inv = ImageOps.invert(gray)
    
    # 增强对比度，让内容边缘更明显
    enhancer = ImageEnhance.Contrast(inv)
    inv = enhancer.enhance(2.5)
    
    # 二值化内容区域（更严格的阈值）
    mask = inv.point(lambda x: 255 if x > 20 else 0, 'L')
    
    # 根据效果类型调整高度
    if effect_type in ('emboss_deboss', 'deboss_strong'):
        # 凹陷效果：内容区域低
        height = Image.new('L', img.size, 220)  # 背景较高
        # 内容区域降低
        content_low = mask.point(lambda x: int(x * 0.8))  # 内容区域降低80%
        height = ImageChops.subtract(height, content_low)
    elif effect_type in ('gold_flat', 'gold_satin'):
        # 烫金：轻微凸起
        height = mask.point(lambda x: int(x * 0.4))  # 最大40%高度
    else:
        # 浮雕/激凸：明显凸起（增强版）
        height = mask.point(lambda x: int(x * 0.95))  # 最大95%高度
    
    # 轻微平滑边缘（保持细节）
    height = height.filter(ImageFilter.GaussianBlur(radius=1))
    
    # 再次增强对比度
    enhancer = ImageEnhance.Contrast(height)
    height = enhancer.enhance(1.5)
    
    # 应用强度
    if intensity != 1.0:
        height = height.point(lambda x: int(x * intensity))
    
    return height


def generate_normal_map(img, effect_type='relief', strength=3.0):
    """
    生成法线贴图（Normal Map）用于 Three.js 3D 渲染
    
    法线贴图可以让平面产生凹凸感，配合光照实现逼真3D效果
    增强版：使用Sobel算子计算更精确的法线，增强浮雕立体感
    """
    displacement = generate_displacement_map(img, effect_type, intensity=1.0)
    
    # 将灰度高度图转换为法线贴图
    w, h = displacement.size
    disp_data = displacement.load()
    
    normal = Image.new('RGB', (w, h))
    normal_data = normal.load()
    
    for y in range(h):
        for x in range(w):
            # Sobel算子采样周围像素计算梯度（更精确）
            # 水平方向
            left2 = disp_data[max(0, x-2), y]
            left1 = disp_data[max(0, x-1), y]
            right1 = disp_data[min(w-1, x+1), y]
            right2 = disp_data[min(w-1, x+2), y]
            
            # 垂直方向
            up2 = disp_data[x, max(0, y-2)]
            up1 = disp_data[x, max(0, y-1)]
            down1 = disp_data[x, min(h-1, y+1)]
            down2 = disp_data[x, min(h-1, y+2)]
            
            # Sobel梯度计算
            dx = (-right2 + left2 - 2*right1 + 2*left1) * strength / 255.0
            dy = (-down2 + up2 - 2*down1 + 2*up1) * strength / 255.0
            dz = 1.0
            
            # 归一化
            length = (dx*dx + dy*dy + dz*dz) ** 0.5
            if length > 0:
                dx, dy, dz = dx/length, dy/length, dz/length
            
            # 转换到RGB [0, 255]
            r = int((dx * 0.5 + 0.5) * 255)
            g = int((dy * 0.5 + 0.5) * 255)
            b = int(dz * 255)
            
            normal_data[x, y] = (r, g, b)
    
    return normal


def generate_3d_preview_maps(pdf_path, output_dir, product_name, plate_type_key=None, dpi=72):
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
        page = doc[0]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        doc.close()
        
        # 限制尺寸
        max_size = 1200
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        
        # 获取效果类型
        effect_type = plate_type_key or get_effect_type(product_name)
        
        # 生成彩色效果图
        color_img = apply_plate_effect(img, effect_type)
        
        # 生成高度图和法线贴图
        displacement = generate_displacement_map(img, effect_type)
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
    except Exception as e:
        print(f"[generate_3d_preview_maps] 生成失败: {e}")
        import traceback
        traceback.print_exc()
        return None
