"""
顺丰标快运费预估模块
根据客户地址和发货工厂，计算预估运费
"""

from decimal import Decimal, ROUND_HALF_UP

# ==================== 工厂配置 ====================
FACTORIES = {
    'guangzhou': {
        'name': '广州工厂',
        'province': '广东',
        'city': '广州',
        'coverage_provinces': ['广东', '广西', '福建', '江西', '湖南', '海南'],
    },
    'nantong': {
        'name': '南通工厂',
        'province': '江苏',
        'city': '南通',
        'coverage_provinces': ['江苏', '浙江', '上海', '安徽', '山东'],
    },
}

# ==================== 顺丰标快运费表（2025参考价） ====================
# 格式：{区域代码: {'首重': Decimal, '续重': Decimal, '描述': str}}
SF_EXPRESS_RATE = {
    # 省内/经济圈
    'guangdong_local': {'首重': Decimal('13'), '续重': Decimal('2'), '描述': '广东省内'},
    'jiangsu_local': {'首重': Decimal('13'), '续重': Decimal('2'), '描述': '江苏省内'},
    'zhejiang_local': {'首重': Decimal('13'), '续重': Decimal('2'), '描述': '浙江省内'},
    'shanghai_local': {'首重': Decimal('13'), '续重': Decimal('2'), '描述': '上海同城'},
    
    # 经济圈互寄（江浙沪皖）
    'js_zhejiang': {'首重': Decimal('14'), '续重': Decimal('2'), '描述': '江浙沪互寄'},
    'js_shanghai': {'首重': Decimal('14'), '续重': Decimal('2'), '描述': '江浙沪互寄'},
    'js_anhui': {'首重': Decimal('14'), '续重': Decimal('2'), '描述': '江浙沪皖互寄'},
    'zhejiang_shanghai': {'首重': Decimal('14'), '续重': Decimal('2'), '描述': '江浙沪互寄'},
    'zhejiang_anhui': {'首重': Decimal('14'), '续重': Decimal('2'), '描述': '江浙沪皖互寄'},
    'shanghai_anhui': {'首重': Decimal('14'), '续重': Decimal('2'), '描述': '江浙沪皖互寄'},
    
    # 邻近省份（从广州/南通出发）
    'guangzhou_near': {'首重': Decimal('18'), '续重': Decimal('5'), '描述': '广州-邻近省份'},
    'nantong_near': {'首重': Decimal('18'), '续重': Decimal('5'), '描述': '南通-邻近省份'},
    
    # 中等距离
    'medium': {'首重': Decimal('20'), '续重': Decimal('8'), '描述': '中等距离'},
    
    # 远距离
    'long': {'首重': Decimal('22'), '续重': Decimal('10'), '描述': '远距离'},
    
    # 偏远地区
    'remote': {'首重': Decimal('26'), '续重': Decimal('18'), '描述': '偏远地区（新疆/西藏/青海）'},
}

# 省份到区域分类的映射（从广州出发）
GUANGZHOU_DEST_MAP = {
    '广东': 'guangdong_local',
    '广西': 'guangzhou_near',
    '福建': 'guangzhou_near',
    '江西': 'guangzhou_near',
    '湖南': 'guangzhou_near',
    '海南': 'guangzhou_near',
    '浙江': 'medium',
    '江苏': 'medium',
    '上海': 'medium',
    '安徽': 'medium',
    '湖北': 'medium',
    '河南': 'medium',
    '贵州': 'medium',
    '云南': 'long',
    '四川': 'long',
    '重庆': 'long',
    '陕西': 'long',
    '甘肃': 'long',
    '山西': 'long',
    '河北': 'medium',
    '山东': 'medium',
    '北京': 'long',
    '天津': 'long',
    '辽宁': 'long',
    '吉林': 'long',
    '黑龙江': 'long',
    '内蒙古': 'long',
    '宁夏': 'long',
    '新疆': 'remote',
    '西藏': 'remote',
    '青海': 'remote',
    '台湾': 'remote',
    '香港': 'long',
    '澳门': 'long',
}

# 省份到区域分类的映射（从南通出发）
NANTONG_DEST_MAP = {
    '江苏': 'jiangsu_local',
    '浙江': 'js_zhejiang',
    '上海': 'js_shanghai',
    '安徽': 'js_anhui',
    '山东': 'nantong_near',
    '河北': 'medium',
    '河南': 'medium',
    '北京': 'medium',
    '天津': 'medium',
    '山西': 'medium',
    '陕西': 'long',
    '辽宁': 'long',
    '吉林': 'long',
    '黑龙江': 'long',
    '湖北': 'medium',
    '湖南': 'medium',
    '江西': 'medium',
    '福建': 'medium',
    '广东': 'long',
    '广西': 'long',
    '海南': 'long',
    '四川': 'long',
    '重庆': 'long',
    '贵州': 'long',
    '云南': 'long',
    '甘肃': 'long',
    '内蒙古': 'long',
    '宁夏': 'long',
    '新疆': 'remote',
    '西藏': 'remote',
    '青海': 'remote',
    '台湾': 'remote',
    '香港': 'long',
    '澳门': 'long',
}


def _normalize_province(province: str) -> str:
    """清洗省份名称，去除'市'、'省'后缀，统一格式"""
    if not province:
        return ''
    province = province.strip()
    # 去除'市'后缀：上海市 -> 上海，北京市 -> 北京
    if province.endswith('市'):
        province = province[:-1]
    # 去除'省'后缀：广东省 -> 广东
    if province.endswith('省'):
        province = province[:-1]
    # 处理自治区：广西壮族自治区 -> 广西，内蒙古自治区 -> 内蒙古（内蒙古本身不带后缀）
    # 处理特别行政区：香港特别行政区 -> 香港
    if province.endswith('特别行政区'):
        province = province[:-5]
    if province.endswith('自治区'):
        # 新疆维吾尔自治区 -> 新疆，西藏自治区 -> 西藏，宁夏回族自治区 -> 宁夏，广西壮族自治区 -> 广西，内蒙古自治区 -> 内蒙古
        if '新疆' in province:
            province = '新疆'
        elif '西藏' in province:
            province = '西藏'
        elif '宁夏' in province:
            province = '宁夏'
        elif '广西' in province:
            province = '广西'
        elif '内蒙古' in province:
            province = '内蒙古'
    return province


def select_factory(customer_province: str) -> str:
    """
    根据客户省份选择最近的发货工厂
    
    Args:
        customer_province: 客户所在省份
        
    Returns:
        工厂代码: 'guangzhou' 或 'nantong'
    """
    # 清洗省份名称
    customer_province = _normalize_province(customer_province)
    
    # 如果客户在广东省，一定从广州发
    if customer_province == '广东':
        return 'guangzhou'
    
    # 如果在江苏省，一定从南通发
    if customer_province == '江苏':
        return 'nantong'
    
    # 如果在广州工厂覆盖范围，从广州发
    if customer_province in FACTORIES['guangzhou']['coverage_provinces']:
        return 'guangzhou'
    
    # 如果在南通工厂覆盖范围，从南通发
    if customer_province in FACTORIES['nantong']['coverage_provinces']:
        return 'nantong'
    
    # 其他省份：比较运费，选更便宜的
    gz_rate = GUANGZHOU_DEST_MAP.get(customer_province, 'long')
    nt_rate = NANTONG_DEST_MAP.get(customer_province, 'long')
    
    gz_fee = SF_EXPRESS_RATE.get(gz_rate, SF_EXPRESS_RATE['long'])
    nt_fee = SF_EXPRESS_RATE.get(nt_rate, SF_EXPRESS_RATE['long'])
    
    # 选首重更便宜的
    if gz_fee['首重'] <= nt_fee['首重']:
        return 'guangzhou'
    return 'nantong'


def calculate_delivery_fee(
    customer_province: str,
    customer_city: str = '',
    weight_kg: float = 0.5,  # 制版产品默认约0.5kg
    factory: str = None,  # 可指定工厂，否则自动选择
) -> dict:
    """
    计算顺丰标快预估运费
    
    Args:
        customer_province: 客户省份
        customer_city: 客户城市（可选，用于省内同城判断）
        weight_kg: 包裹重量（kg），默认0.5kg（制版产品通常较轻）
        factory: 指定工厂代码，None则自动选择
        
    Returns:
        {
            'factory': 'guangzhou',
            'factory_name': '广州工厂',
            'rate_code': 'guangdong_local',
            'rate_name': '广东省内',
            '首重': Decimal('13'),
            '续重': Decimal('2'),
            'weight_kg': 0.5,
            'chargeable_weight_kg': 1.0,  # 计费重量（向上取整到1kg）
            '首重费用': Decimal('13'),
            '续重费用': Decimal('0'),
            '预估运费': Decimal('13'),
            'currency': 'CNY',
            'note': '顺丰标快参考价，实际以收派员确认为准',
        }
    """
    # 清洗省份名称
    customer_province = _normalize_province(customer_province)
    
    # 选择工厂
    if factory is None:
        factory = select_factory(customer_province)
    
    factory_info = FACTORIES[factory]
    
    # 获取运费区域代码
    if factory == 'guangzhou':
        rate_code = GUANGZHOU_DEST_MAP.get(customer_province, 'long')
    else:
        rate_code = NANTONG_DEST_MAP.get(customer_province, 'long')
    
    # 获取运费标准
    rate = SF_EXPRESS_RATE.get(rate_code, SF_EXPRESS_RATE['long'])
    
    # 计算计费重量（向上取整到1kg）
    chargeable_weight = max(1.0, float(int(weight_kg) + (1 if weight_kg % 1 > 0 else 0)))
    
    # 计算费用
    首重费用 = rate['首重']
    续重公斤数 = max(0, chargeable_weight - 1.0)
    续重费用 = (Decimal(str(续重公斤数)) * rate['续重']).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    预估运费 = (首重费用 + 续重费用).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    
    return {
        'factory': factory,
        'factory_name': factory_info['name'],
        'rate_code': rate_code,
        'rate_name': rate['描述'],
        '首重': rate['首重'],
        '续重': rate['续重'],
        'weight_kg': weight_kg,
        'chargeable_weight_kg': chargeable_weight,
        '首重费用': 首重费用,
        '续重费用': 续重费用,
        '预估运费': 预估运费,
        'currency': 'CNY',
        'note': '顺丰标快参考价，实际以收派员上门确认为准',
    }


def estimate_order_delivery_fee(order_items: list, customer_province: str) -> dict:
    """
    根据订单明细估算运费
    
    Args:
        order_items: OrderItem列表或规格组数据
        customer_province: 客户省份
        
    Returns:
        运费估算结果（同 calculate_delivery_fee）
    """
    # 估算重量：每个规格组约0.3-0.5kg（版材轻小）
    # 如果有多个规格组，重量累加
    item_count = len(order_items) if order_items else 1
    estimated_weight = min(3.0, item_count * 0.5)  # 封顶3kg
    
    return calculate_delivery_fee(
        customer_province=customer_province,
        weight_kg=estimated_weight,
    )


# ==================== 快捷函数 ====================

def get_delivery_fee_choices() -> list:
    """获取运费区域选项（用于后台配置）"""
    return [
        ('guangdong_local', '广东省内 (首重13元)'),
        ('jiangsu_local', '江苏省内 (首重13元)'),
        ('js_zhejiang', '江浙沪互寄 (首重14元)'),
        ('guangzhou_near', '广州-邻近省份 (首重18元)'),
        ('nantong_near', '南通-邻近省份 (首重18元)'),
        ('medium', '中等距离 (首重20元)'),
        ('long', '远距离 (首重22元)'),
        ('remote', '偏远地区 (首重26元)'),
    ]
