"""
运费计算模块测试
覆盖：省份清洗、工厂选择、运费计算
"""
from django.test import TestCase
from decimal import Decimal
from utils.delivery_fee import (
    _normalize_province, select_factory, calculate_delivery_fee,
    FACTORIES, SF_EXPRESS_RATE, GUANGZHOU_DEST_MAP, NANTONG_DEST_MAP
)


class NormalizeProvinceTest(TestCase):
    """省份名称清洗测试"""

    def test_remove_shi_suffix(self):
        """去除'市'后缀"""
        self.assertEqual(_normalize_province('上海市'), '上海')
        self.assertEqual(_normalize_province('北京市'), '北京')
        self.assertEqual(_normalize_province('广州市'), '广州')

    def test_remove_sheng_suffix(self):
        """去除'省'后缀"""
        self.assertEqual(_normalize_province('广东省'), '广东')
        self.assertEqual(_normalize_province('江苏省'), '江苏')

    def test_autonomous_region(self):
        """处理自治区"""
        self.assertEqual(_normalize_province('内蒙古自治区'), '内蒙古')
        self.assertEqual(_normalize_province('广西壮族自治区'), '广西')
        self.assertEqual(_normalize_province('西藏自治区'), '西藏')
        self.assertEqual(_normalize_province('宁夏回族自治区'), '宁夏')
        self.assertEqual(_normalize_province('新疆维吾尔自治区'), '新疆')

    def test_special_administrative(self):
        """处理特别行政区"""
        self.assertEqual(_normalize_province('香港特别行政区'), '香港')
        self.assertEqual(_normalize_province('澳门特别行政区'), '澳门')

    def test_already_clean(self):
        """已经是干净的名称"""
        self.assertEqual(_normalize_province('广东'), '广东')
        self.assertEqual(_normalize_province('江苏'), '江苏')
        self.assertEqual(_normalize_province('上海'), '上海')

    def test_empty_and_none(self):
        """空值处理"""
        self.assertEqual(_normalize_province(''), '')
        self.assertEqual(_normalize_province(None), '')

    def test_whitespace(self):
        """去除前后空格"""
        self.assertEqual(_normalize_province(' 上海市 '), '上海')


class SelectFactoryTest(TestCase):
    """工厂选择测试"""

    def test_guangzhou_coverage(self):
        """广州覆盖省份选择广州工厂"""
        for province in ['广东', '广西', '福建', '江西', '湖南', '海南']:
            self.assertEqual(select_factory(province), 'guangzhou', f'{province} 应该选广州')

    def test_nantong_coverage(self):
        """南通覆盖省份选择南通工厂"""
        for province in ['江苏', '浙江', '上海', '安徽', '山东']:
            self.assertEqual(select_factory(province), 'nantong', f'{province} 应该选南通')

    def test_guangdong_jiangsu_direct(self):
        """广东和江苏直接匹配"""
        self.assertEqual(select_factory('广东'), 'guangzhou')
        self.assertEqual(select_factory('江苏'), 'nantong')

    def test_cost_comparison(self):
        """运费比较选择更便宜的工厂"""
        # 云南：广州运费22(long)，南通运费22(long)，选广州（相等时选广州）
        result = select_factory('云南')
        self.assertEqual(result, 'guangzhou')

        # 黑龙江：广州运费22(long)，南通运费22(long)，选广州（相等时选广州）
        self.assertEqual(select_factory('黑龙江'), 'guangzhou')

    def test_with_shi_suffix(self):
        """带'市'后缀也能正确选择"""
        self.assertEqual(select_factory('上海市'), 'nantong')
        self.assertEqual(select_factory('广州市'), 'guangzhou')

    def test_unknown_province(self):
        """未知省份也能返回结果"""
        result = select_factory('未知省份')
        self.assertIn(result, ['guangzhou', 'nantong'])


class CalculateDeliveryFeeTest(TestCase):
    """运费计算测试"""

    def test_guangzhou_to_guangdong(self):
        """广州到广东（省内）"""
        fee = calculate_delivery_fee('广东', 'guangzhou')
        self.assertEqual(fee['首重'], 13)
        self.assertEqual(fee['续重'], 2)

    def test_nantong_to_jiangsu(self):
        """南通到江苏（省内）"""
        fee = calculate_delivery_fee('江苏', 'nantong')
        self.assertEqual(fee['首重'], 13)
        self.assertEqual(fee['续重'], 2)

    def test_guangzhou_to_shanghai(self):
        """广州到上海（经济圈）"""
        fee = calculate_delivery_fee('上海', 'guangzhou')
        self.assertEqual(fee['首重'], 14)
        self.assertEqual(fee['续重'], 2)

    def test_nantong_to_beijing(self):
        """南通到北京（中等距离）"""
        fee = calculate_delivery_fee('北京', factory='nantong')
        self.assertEqual(fee['首重'], 20)
        self.assertEqual(fee['续重'], 8)

    def test_guangzhou_to_xinjiang(self):
        """广州到新疆（偏远）"""
        fee = calculate_delivery_fee('新疆', factory='guangzhou')
        self.assertEqual(fee['首重'], 26)
        self.assertEqual(fee['续重'], 18)

    def test_invalid_factory(self):
        """无效工厂返回默认运费"""
        fee = calculate_delivery_fee('广东', 'invalid_factory')
        self.assertIn('首重', fee)
        self.assertIn('续重', fee)

    def test_fee_structure(self):
        """运费结构完整性"""
        fee = calculate_delivery_fee('广东', factory='guangzhou')
        self.assertIn('首重', fee)
        self.assertIn('续重', fee)
        self.assertIsInstance(fee['首重'], Decimal)
        self.assertIsInstance(fee['续重'], Decimal)
        self.assertGreater(fee['首重'], 0)
        self.assertGreaterEqual(fee['续重'], 0)
