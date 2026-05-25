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
    'etching_bump_set': 'relief_convex',
    'carving_flat_gold':       'carving_flat',
    'carving_flat_bump':       'carving_flat',
    'carving_relief_gold_bump': 'carving_relief',
    'carving_relief_bump_set':  'carving_multi_layer',
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
    shadow = Image.new('RGBA', img_gray.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    # 将mask转为阴影色
    shadow_mask = mask.point(lambda x: int(x * shadow_color / 255) if x > 0 else 0)
    shadow_r = Image.new('L', img_gray.size, 0)
    shadow_g = Image.new('L', img_gray.size, 0)
    shadow_b = Image.new('L', img_gray.size, 0)
    shadow_a = shadow_mask
    shadow = Image.merge('RGBA', (shadow_r, shadow_g, shadow_b, shadow_a))
    # 模糊
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=blur))
    # 偏移
    shadow = ImageChops.offset(shadow, offset[0], offset[1])
    return shadow


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
    强浮雕凸起效果（激凸版）
    白底 + 内容有立体投影 + 顶部高光
    直观体现"凸起"感
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    # 白底
    bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))

    # 内容层（黑字）
    mask = _get_content_mask(gray)
    content = Image.new('RGBA', (w, h), (0, 0, 0, 255))
    content.putalpha(mask)

    # 阴影（右下偏移，模拟光源从左上来）
    shadow = _drop_shadow(gray, offset=(4, 4), blur=4, shadow_color=100)

    # 高光（左上偏移）
    highlight = _highlight(gray, offset=(-3, -3), blur=3, highlight_color=160)

    # 合成：白底 → 阴影 → 内容 → 高光
    result = Image.alpha_composite(bg, shadow)
    result = Image.alpha_composite(result, content)
    result = Image.alpha_composite(result, highlight)

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
    金色浮雕效果（浮雕版）
    白底 + 金色内容 + 立体投影 + 高光
    """
    img = _ensure_rgb(img)
    gray = img.convert('L')
    w, h = img.size

    bg = Image.new('RGBA', (w, h), (255, 255, 255, 255))

    # 金色内容层
    mask = _get_content_mask(gray)
    gold_content = Image.new('RGB', (w, h), (218, 165, 32))  # 金色 #DAA520
    gold_content_rgba = gold_content.convert('RGBA')
    gold_content_rgba.putalpha(mask)

    # 阴影
    shadow = _drop_shadow(gray, offset=(4, 4), blur=4, shadow_color=90)
    # 高光
    highlight = _highlight(gray, offset=(-3, -3), blur=3, highlight_color=140)

    result = Image.alpha_composite(bg, shadow)
    result = Image.alpha_composite(result, gold_content_rgba)
    result = Image.alpha_composite(result, highlight)

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
