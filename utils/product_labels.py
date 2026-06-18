"""产品类型中文名：当前选项 + 旧版 product_name 编码兼容。"""

# 旧版编码 → 中文名（与 OrderItem.PRODUCT_NAME_CHOICES 命名风格一致）
LEGACY_PRODUCT_NAME_LABELS = {
    'etching_bump_set': '腐蚀版-击凸/凹版（配套）',
    'carving_flat_gold': '雕刻版-平雕（烫金版）',
    'carving_flat_bump': '雕刻版-平雕（击凸版）',
    'carving_relief_gold_bump': '雕刻版-浮雕（烫金击凸一体）',
    'carving_relief_bump_set': '雕刻版-浮雕（击凸/凹版）',
    'pingdiao': '雕刻版-平雕',
}


def get_product_display_name(code):
    """返回产品中文名；未知编码原样返回。"""
    if not code:
        return ''
    from apps.orders.models import OrderItem

    label = dict(OrderItem.PRODUCT_NAME_CHOICES).get(code)
    if label:
        return label
    return LEGACY_PRODUCT_NAME_LABELS.get(code, code)
