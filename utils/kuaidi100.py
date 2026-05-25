#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
快递100 物流查询工具
文档：https://api.kuaidi100.com/document/5f0ff4a12977d50d94e10512.html

接入步骤：
1. 注册快递100企业账号：https://www.kuaidi100.com/openapi/apply.shtml
2. 获取授权Key和Customer ID
3. 在 settings.py 中配置 KUAIDI100_KEY 和 KUAIDI100_CUSTOMER
4. 可选：配置 KUAIDI100_CACHE_SECONDS（物流数据缓存时间，默认300秒）
"""
import hashlib
import json
import time
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
import requests


def _generate_sign(param_json_str: str, key: str, customer: str) -> str:
    """生成快递100签名：MD5(param+json+key+customer) 转大写"""
    raw = param_json_str + key + customer
    return hashlib.md5(raw.encode('utf-8')).hexdigest().upper()


def query_tracking(tracking_number: str, company_code: str = None, phone_tail: str = None):
    """
    查询快递物流轨迹
    
    Args:
        tracking_number: 快递单号
        company_code: 快递公司编码（如 yuantong, sf, jd 等），不传则自动识别
        phone_tail: 收件人或寄件人手机号后4位（部分快递需要）
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'data': {  # 成功时返回快递100原始数据结构
                'company': '快递公司名称',
                'com': '快递公司编码',
                'nu': '快递单号',
                'state': '3',  # 0-运输中 1-揽收 2-疑难 3-签收 4-退签 5-派件 6-退回
                'ischeck': '1',  # 0-未签收 1-已签收
                'data': [
                    {'time': '2024-01-01 10:00:00', 'context': '快件已签收', 'location': ''},
                    ...
                ]
            }
        }
    """
    key = getattr(settings, 'KUAIDI100_KEY', '')
    customer = getattr(settings, 'KUAIDI100_CUSTOMER', '')
    
    if not key or not customer:
        return {
            'success': False,
            'message': '快递100未配置，请在settings.py中设置KUAIDI100_KEY和KUAIDI100_CUSTOMER',
            'data': None
        }
    
    # 缓存key
    cache_key = f'kuaidi100:{tracking_number}'
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    param_dict = {"num": tracking_number}
    if company_code:
        param_dict["com"] = company_code
    if phone_tail:
        param_dict["phone"] = phone_tail
    
    param_json_str = json.dumps(param_dict, ensure_ascii=False, separators=(',', ':'))
    sign = _generate_sign(param_json_str, key, customer)
    
    payload = {
        "customer": customer,
        "sign": sign,
        "param": param_json_str,
    }
    
    try:
        resp = requests.post(
            "https://poll.kuaidi100.com/poll/query.do",
            data=payload,
            timeout=10,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        resp.raise_for_status()
        result = resp.json()
        
        # 快递100返回格式：{status, message, data}
        if result.get('status') == '200':
            response_data = {
                'success': True,
                'message': '查询成功',
                'data': result.get('data')
            }
        else:
            response_data = {
                'success': False,
                'message': result.get('message', '查询失败'),
                'data': result.get('data')
            }
    except requests.RequestException as e:
        response_data = {
            'success': False,
            'message': f'网络请求失败: {str(e)}',
            'data': None
        }
    except Exception as e:
        response_data = {
            'success': False,
            'message': f'查询异常: {str(e)}',
            'data': None
        }
    
    # 缓存结果（默认5分钟）
    cache_seconds = getattr(settings, 'KUAIDI100_CACHE_SECONDS', 300)
    cache.set(cache_key, response_data, cache_seconds)
    
    return response_data


def get_company_code(company_name: str) -> str:
    """
    根据快递公司名称获取编码（常用映射）
    完整列表参见：https://api.kuaidi100.com/document/5f0ff4a29777d50d94e1026a.html
    """
    mapping = {
        '顺丰': 'shunfeng',
        '顺丰速运': 'shunfeng',
        '圆通': 'yuantong',
        '圆通速递': 'yuantong',
        '中通': 'zhongtong',
        '中通快递': 'zhongtong',
        '申通': 'shentong',
        '申通快递': 'shentong',
        '韵达': 'yunda',
        '韵达快递': 'yunda',
        'EMS': 'ems',
        '邮政': 'ems',
        '京东': 'jd',
        '京东物流': 'jd',
        '德邦': 'debangkuaidi',
        '德邦快递': 'debangkuaidi',
        '极兔': 'jtexpress',
        '极兔速递': 'jtexpress',
        '菜鸟': 'cainiao',
        '丹鸟': 'cainiao',
        '百世': 'huitongkuaidi',
        '百世快递': 'huitongkuaidi',
        '天天': 'tiantian',
        '优速': 'youshuwuliu',
        '宅急送': 'zhaijisong',
        '跨越': 'kuayue',
        '跨越速运': 'kuayue',
        '速尔': 'suer',
        '安能': 'annengwuliu',
        '安能物流': 'annengwuliu',
    }
    return mapping.get(company_name, '')


def format_tracking_data(raw_data: dict) -> dict:
    """
    将快递100原始数据格式化为模板友好的结构
    """
    if not raw_data:
        return None
    
    state_map = {
        '0': '运输中',
        '1': '揽件中',
        '2': '疑难件',
        '3': '已签收',
        '4': '退签',
        '5': '派件中',
        '6': '退回中',
    }
    
    tracks = []
    for item in raw_data.get('data', []):
        tracks.append({
            'time': item.get('time', ''),
            'context': item.get('context', ''),
            'location': item.get('location', ''),
        })
    
    return {
        'company': raw_data.get('company', ''),
        'com': raw_data.get('com', ''),
        'tracking_number': raw_data.get('nu', ''),
        'state': raw_data.get('state', ''),
        'state_label': state_map.get(raw_data.get('state', ''), '未知'),
        'is_signed': raw_data.get('ischeck') == '1',
        'tracks': tracks,
    }
