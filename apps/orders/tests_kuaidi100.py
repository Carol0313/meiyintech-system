"""
快递100工具测试
覆盖：签名生成、回调解析、签名验证、数据格式化
"""
import json
import hashlib
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.cache import cache
from utils.kuaidi100 import (
    _generate_sign, parse_callback_data, verify_callback_sign,
    format_tracking_data
)


class GenerateSignTest(TestCase):
    """签名生成测试"""

    def test_sign_generation(self):
        """签名生成逻辑正确"""
        param = '{"num":"123456"}'
        key = 'test_key'
        customer = 'test_customer'
        
        expected = hashlib.md5(
            (param + key + customer).encode('utf-8')
        ).hexdigest().upper()
        
        result = _generate_sign(param, key, customer)
        self.assertEqual(result, expected)
        self.assertEqual(len(result), 32)  # MD5长度

    def test_sign_consistency(self):
        """相同输入产生相同签名"""
        param = '{"num":"123456"}'
        key = 'test_key'
        customer = 'test_customer'
        
        sign1 = _generate_sign(param, key, customer)
        sign2 = _generate_sign(param, key, customer)
        self.assertEqual(sign1, sign2)

    def test_sign_different_inputs(self):
        """不同输入产生不同签名"""
        sign1 = _generate_sign('{"a":1}', 'k1', 'c1')
        sign2 = _generate_sign('{"a":2}', 'k1', 'c1')
        self.assertNotEqual(sign1, sign2)


@override_settings(
    KUAIDI100_KEY='test_key',
    KUAIDI100_CUSTOMER='test_customer'
)
class VerifyCallbackSignTest(TestCase):
    """回调签名验证测试"""

    def test_valid_sign(self):
        """正确的签名通过验证"""
        param = '{"num":"123456"}'
        expected_sign = _generate_sign(param, 'test_key', 'test_customer')
        self.assertTrue(verify_callback_sign(param, expected_sign))

    def test_invalid_sign(self):
        """错误的签名不通过"""
        param = '{"num":"123456"}'
        self.assertFalse(verify_callback_sign(param, 'wrong_sign'))

    def test_empty_sign(self):
        """空签名不通过"""
        self.assertFalse(verify_callback_sign('{"num":"123"}', ''))


class ParseCallbackDataTest(TestCase):
    """回调数据解析测试"""

    def test_valid_json(self):
        """正常JSON解析"""
        data = {
            'com': 'shunfeng',
            'nu': 'SF123456',
            'state': '3',
            'data': [
                {'time': '2024-01-01 10:00', 'context': '已签收'}
            ]
        }
        body = json.dumps(data).encode('utf-8')
        result = parse_callback_data(body)
        self.assertEqual(result['com'], 'shunfeng')
        self.assertEqual(result['nu'], 'SF123456')

    def test_invalid_json(self):
        """无效JSON返回空字典"""
        result = parse_callback_data(b'not json')
        self.assertEqual(result, {})

    def test_empty_body(self):
        """空body返回空字典"""
        result = parse_callback_data(b'')
        self.assertEqual(result, {})


class FormatTrackingDataTest(TestCase):
    """物流数据格式化测试"""

    def test_full_data(self):
        """完整数据格式化"""
        raw = {
            'company': '顺丰速运',
            'com': 'shunfeng',
            'nu': 'SF123456',
            'state': '3',
            'ischeck': '1',
            'data': [
                {'time': '2024-01-01 10:00', 'context': '已签收', 'location': '北京'},
                {'time': '2024-01-01 08:00', 'context': '派送中', 'location': '北京'},
            ]
        }
        result = format_tracking_data(raw)
        self.assertEqual(result['company'], '顺丰速运')
        self.assertEqual(result['tracking_number'], 'SF123456')
        self.assertEqual(result['state'], '3')
        self.assertEqual(result['state_label'], '已签收')
        self.assertTrue(result['is_signed'])
        self.assertEqual(len(result['tracks']), 2)
        self.assertEqual(result['tracks'][0]['context'], '已签收')

    def test_empty_data(self):
        """空数据返回None"""
        self.assertIsNone(format_tracking_data(None))
        self.assertIsNone(format_tracking_data({}))

    def test_state_mapping(self):
        """状态码映射正确"""
        state_tests = [
            ('0', '运输中', False),
            ('1', '揽件中', False),
            ('2', '疑难件', False),
            ('3', '已签收', True),
            ('4', '退签', False),
            ('5', '派件中', False),
            ('6', '退回中', False),
            ('99', '未知', False),  # 未知状态
        ]
        for state_code, expected_label, expected_signed in state_tests:
            raw = {'state': state_code, 'ischeck': '1' if expected_signed else '0', 'data': []}
            result = format_tracking_data(raw)
            self.assertEqual(result['state_label'], expected_label, f'状态码 {state_code} 应该显示 {expected_label}')
            self.assertEqual(result['is_signed'], expected_signed)

