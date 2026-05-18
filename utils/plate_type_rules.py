"""
版类处理规则配置
根据产品名称+材质+厚度，确定对应的版类处理规则
"""

from decimal import Decimal

# ========== 版类定义 ==========
PLATE_TYPES = {
    'etching_gold': {
        'name': '烫金版',
        'file_suffix': '阴片',
        'min_line_width': Decimal('0.12'),
        'color_requirement': '单色100K',
        'screenshot_standard': '画板白底尺寸',
        'needs_inner_corner_line': True,
        'needs_thickening_large_area': True,
        'expansion_rules': {},
    },
    'emboss': {
        'name': '压纹版',
        'file_suffix': '阳片',
        'min_line_width': Decimal('0.12'),
        'color_requirement': '单色100K',
        'screenshot_standard': '裁切框轮廓化后的尺寸',
        'needs_cutting_frame': True,
        'cutting_frame_margin': 10,  # mm
        'with_film': False,
    },
    'relief_convex': {
        'name': '激凸版',
        'file_suffix': '阴片',
        'min_line_width': Decimal('0.12'),
        'color_requirement': '单色100K',
        'screenshot_standard': '画板白底尺寸',
        'needs_inner_corner_line': True,
        'expansion_rules': {
            '1.5': {'convex': Decimal('-0.2'), 'concave': Decimal('0')},
            '2.0': {'convex': Decimal('-0.3'), 'concave': Decimal('0')},
            '3.0': {'convex': Decimal('-0.5'), 'concave': Decimal('0')},
            'default': {'convex': Decimal('-0.5'), 'concave': Decimal('0')},
        },
    },
    'relief_concave': {
        'name': '激凹版',
        'file_suffix': '阴片',
        'min_line_width': Decimal('0.12'),
        'color_requirement': '单色100K',
        'screenshot_standard': '画板白底尺寸',
        'needs_flip': True,
        'expansion_rules': {
            '1.5': {'convex': Decimal('-0.2'), 'concave': Decimal('0')},
            '2.0': {'convex': Decimal('-0.3'), 'concave': Decimal('0')},
            '3.0': {'convex': Decimal('-0.5'), 'concave': Decimal('0')},
            'default': {'convex': Decimal('-0.5'), 'concave': Decimal('0')},
        },
    },
    'magnesium_concave_resin_convex_exposure': {
        'name': '镁凹树凸-晒版',
        'file_suffix': '阴片',
        'min_line_width': Decimal('0.12'),
        'color_requirement': '单色100K',
        'screenshot_standard': '画板白底尺寸',
        'expansion_rules': {
            'default': {'convex': Decimal('-0.2'), 'concave': Decimal('0')},
        },
    },
    'magnesium_concave_resin_convex_mold': {
        'name': '镁凹树凸-倒模',
        'file_suffix': '阳片',
        'min_line_width': Decimal('0.12'),
        'color_requirement': '单色100K',
        'screenshot_standard': '黑色图案内容净尺寸',
        'only_concave': True,
        'no_inversion': True,
        'no_expansion': True,
    },
    'alignment_film': {
        'name': '对位菲林',
        'file_suffix': '阳片',
        'color_requirement': '刀版线和主要内容单色100K',
        'screenshot_standard': '角线尺寸',
        'needs_corner_marks': True,
    },
    'uv_film': {
        'name': 'UV菲林',
        'file_suffix': '阳片',
        'min_line_width': Decimal('0.12'),
        'color_requirement': '单色100K',
        'screenshot_standard': '角线尺寸',
        'needs_corner_marks': True,
        'remove_die_lines': True,
    },
    'carving_flat': {
        'name': '平雕版',
        'min_line_width': Decimal('0.12'),
        'gap_min': Decimal('0.10'),
        'border_margin': 10,  # mm
        'needs_vectorization': True,
        'export_ai_version': '3.0',
    },
    'carving_relief': {
        'name': '浮雕版',
        'min_line_width': Decimal('0.30'),
        'gap_min': Decimal('0.10'),
        'border_margin': 10,
        'needs_vectorization': True,
        'needs_color_separation': True,
        'export_ai_version': '3.0',
    },
    'carving_multi_layer': {
        'name': '多层次浮雕版',
        'min_line_width': Decimal('0.30'),
        'gap_min': Decimal('0.10'),
        'border_margin': 10,
        'needs_vectorization': True,
        'needs_color_separation': True,
        'export_ai_version': '3.0',
    },
}


# ========== 拼版间距规则 ==========
# key: (thickness, material) 或 thickness 字符串 → spacing_mm
SPACING_RULES = {
    # 同厚度同材质
    '1.5': 10,
    '2.0': 10,
    '3.0': 15,
    '4.0': 15,
    '6.0': 15,
    '6.35': 15,
    # 不同厚度之间
    'different_thickness': 20,
    # 不同材质之间
    'different_material': 20,
    # 烫金版/激凸版内角线之间（距离图案不足10mm时）
    'inner_corner_close': 5,
    # 烫金版/激凸版内角线之间（距离图案10mm时）
    'inner_corner_far': 0,
    # 压纹版裁切框之间（距离图案不足10mm时）
    'emboss_frame_close': 5,
    # 压纹版裁切框之间（距离图案10mm时）
    'emboss_frame_far': 0,
}


# ========== 板材规格 ==========
PLATE_SPECS = [
    {'name': '610×914mm', 'width': 610, 'height': 914},
    {'name': '762×1016mm', 'width': 762, 'height': 1016},
    {'name': '600×1000mm', 'width': 600, 'height': 1000},
]


def get_plate_type_by_product(product_name, material, thickness):
    """
    根据产品名称+材质+厚度，确定版类
    返回版类key 或 None
    """
    # 腐蚀版
    if product_name == 'etching_concave':
        return 'emboss'  # 蚀刻凹版 → 压纹版（阳片，裁切框）
    if product_name == 'etching_convex':
        return 'etching_gold'  # 蚀刻凸版 → 烫金版（阴片）
    if product_name == 'etching_bump_set':
        return 'relief_convex'  # 击凸/凹配套 → 激凸版（主版）
    # 平雕版
    if product_name in ('carving_flat_gold', 'carving_flat_bump'):
        return 'carving_flat'
    # 浮雕版
    if product_name == 'carving_relief_gold_bump':
        return 'carving_relief'
    # 多层次浮雕版
    if product_name == 'carving_relief_bump_set':
        return 'carving_multi_layer'
    # 树脂版
    if product_name == 'resin_mold':
        return 'magnesium_concave_resin_convex_mold'
    if product_name == 'resin_water':
        return 'magnesium_concave_resin_convex_exposure'
    # 菲林
    if product_name == 'film_alignment':
        return 'alignment_film'
    if product_name == 'film_uv':
        return 'uv_film'
    return None


def get_spacing_mm(thickness_a, thickness_b, material_a, material_b):
    """
    计算两个产品之间的拼版间距(mm)
    """
    # 不同材质
    if material_a != material_b:
        return SPACING_RULES['different_material']
    # 不同厚度
    if str(thickness_a) != str(thickness_b):
        return SPACING_RULES['different_thickness']
    # 同厚度同材质
    key = str(thickness_a)
    return SPACING_RULES.get(key, 15)


def get_expansion_mm(plate_type_key, thickness):
    """
    获取扩缩值(mm)
    返回 {'convex': Decimal, 'concave': Decimal} 或 None
    """
    plate_type = PLATE_TYPES.get(plate_type_key)
    if not plate_type:
        return None
    rules = plate_type.get('expansion_rules', {})
    key = str(thickness)
    if key in rules:
        return rules[key]
    return rules.get('default')


def get_min_line_width(plate_type_key):
    """获取最细线条要求(mm)"""
    plate_type = PLATE_TYPES.get(plate_type_key)
    if plate_type:
        return plate_type.get('min_line_width', Decimal('0.12'))
    return Decimal('0.12')
