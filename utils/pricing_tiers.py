"""
雕刻版 + 腐蚀版 双价格体系

腐蚀版：地域档位 -> 厚度 -> 单价(元/cm²)
雕刻版/树脂版/菲林：产品细分 -> 材质 -> 厚度 -> 固定单价(元/cm²)
"""

from decimal import Decimal

# ========== 产品分类 ==========
# 腐蚀版产品列表（按档位定价）
ETCHING_PRODUCTS = [
    'etching_concave',
    'etching_convex',
    'etching_bump_set',
]

# 雕刻版/树脂版/菲林产品列表（固定价）
CARVING_PRODUCTS = [
    'carving_flat_gold',
    'carving_flat_bump',
    'carving_relief_gold_bump',
    'carving_relief_bump_set',
    'resin_mold',
    'resin_water',
    'film_alignment',
    'film_uv',
]

# ========== 腐蚀版档位价格表 ==========
PROVINCE_TIER_MAP = {
    '北京': 1, '上海': 1, '天津': 1, '云南': 1,
    '香港': 1, '澳门': 1, '台湾': 1,
    '西藏': 1, '青海': 1, '新疆': 1, '内蒙古': 1,
    '海南': 2, '山西': 2, '福建': 2,
    '黑龙江': 2, '吉林': 2, '甘肃': 2, '宁夏': 2,
    '贵州': 2, '广西': 2,
    '广东': 3, '河北': 3, '湖北': 3, '江苏': 3,
    '山东': 3, '浙江': 3, '重庆': 3, '湖南': 3,
    '辽宁': 3, '安徽': 3, '河南': 3, '江西': 3,
    '四川': 3, '陕西': 3,
}

TIER_PRICES = {
    1: {
        '1.5': Decimal('0.15'),
        '2.0': Decimal('0.25'),
        '3.0': Decimal('0.35'),
    },
    2: {
        '1.5': Decimal('0.12'),
        '2.0': Decimal('0.20'),
        '3.0': Decimal('0.30'),
    },
    3: {
        '1.5': Decimal('0.10'),
        '2.0': Decimal('0.15'),
        '3.0': Decimal('0.25'),
    },
}

# ========== 雕刻版/树脂版/菲林固定价格表 ==========
# 产品 -> 材质 -> 厚度 -> 单价
CARVING_PRICE_TABLE = {
    'carving_flat_gold': {
        'copper': {
            '2.0': Decimal('0.40'),
            '3.0': Decimal('0.60'),
        },
    },
    'carving_flat_bump': {
        'copper': {
            '2.0': Decimal('0.40'),
            '3.0': Decimal('0.60'),
        },
    },
    'carving_relief_gold_bump': {
        'magnesium': {
            '3.0': Decimal('1.00'),
            '4.0': Decimal('1.30'),
        },
        'copper': {
            '3.0': Decimal('1.50'),
            '6.0': Decimal('2.00'),
        },
    },
    'carving_relief_bump_set': {
        'magnesium': {
            '3.0': Decimal('1.30'),
            '4.0': Decimal('1.70'),
            '6.35': Decimal('2.00'),
        },
        'copper': {
            '3.0': Decimal('2.00'),
            '4.0': Decimal('2.30'),
            '6.0': Decimal('2.60'),
        },
    },
    'resin_mold': {
        'resin': {
            '-': Decimal('0.10'),
        },
    },
    'resin_water': {
        'resin': {
            '-': Decimal('0.10'),
        },
    },
    'film_alignment': {
        'film': {
            '-': Decimal('0.01'),
        },
    },
    'film_uv': {
        'film': {
            '-': Decimal('0.01'),
        },
    },
}

PROVINCE_CHOICES = sorted(PROVINCE_TIER_MAP.keys())


# ========== 查询函数 ==========

def is_etching_product(product_name):
    """判断是否为腐蚀版产品（按档位定价）"""
    return product_name in ETCHING_PRODUCTS


def get_etching_price(tier_level, thickness):
    """腐蚀版：根据档位和厚度获取单价"""
    tier = TIER_PRICES.get(tier_level, TIER_PRICES[3])
    return tier.get(str(thickness), Decimal('0'))


def get_carving_price(product_name, material, thickness):
    """雕刻版/树脂版/菲林：根据产品、材质、厚度获取固定单价"""
    try:
        return CARVING_PRICE_TABLE[product_name][material][str(thickness)]
    except KeyError:
        return Decimal('0')


def get_tier_by_province(province_name):
    """根据省份名称获取价格档位"""
    if not province_name:
        return 3
    clean = province_name.replace('省', '').replace('市', '').strip()
    for prov, tier in PROVINCE_TIER_MAP.items():
        if clean in prov or prov in clean:
            return tier
    return 3


def get_all_specs():
    """生成所有固定价格规格列表，用于初始化 ProductSpec"""
    specs = []
    for product_name, materials in CARVING_PRICE_TABLE.items():
        for material, thicknesses in materials.items():
            for thickness, price in thicknesses.items():
                specs.append((product_name, material, thickness, price))
    # 腐蚀版规格（价格按档位，unit_price存0）
    for product in ETCHING_PRODUCTS:
        for material in ['magnesium', 'copper', 'zinc', 'stainless_steel']:
            for thickness in ['1.5', '2.0', '3.0']:
                specs.append((product, material, thickness, Decimal('0')))
    return specs


def get_product_category(product_name):
    """获取产品大类"""
    if product_name in ETCHING_PRODUCTS:
        return '腐蚀版'
    if product_name.startswith('carving'):
        return '雕刻版'
    if product_name.startswith('resin'):
        return '树脂版'
    if product_name.startswith('film'):
        return '菲林'
    return '其他'
