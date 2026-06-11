#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
阿里云短信服务工具
用于手机号验证码登录

接入步骤：
1. 阿里云控制台开通短信服务：https://dysms.console.aliyun.com/
2. 申请签名（如：闪电制版）和模板（如：您的验证码是${code}，5分钟内有效。）
3. 获取 AccessKey ID 和 Secret
4. 在 .env 中配置 SMS_ACCESS_KEY_ID / SMS_ACCESS_KEY_SECRET / SMS_SIGN_NAME / SMS_TEMPLATE_CODE
"""
import json
import random
from django.core.cache import cache
from django.conf import settings

try:
    from alibabacloud_dysmsapi20170525.client import Client as DysmsapiClient
    from alibabacloud_dysmsapi20170525 import models as dysmsapi_models
    from alibabacloud_tea_openapi import models as open_api_models
    ALIBABA_SMS_SDK = True
except ImportError:
    ALIBABA_SMS_SDK = False


def _create_client():
    """创建阿里云短信客户端"""
    config = open_api_models.Config(
        access_key_id=settings.SMS_ACCESS_KEY_ID,
        access_key_secret=settings.SMS_ACCESS_KEY_SECRET
    )
    config.endpoint = 'dysmsapi.aliyuncs.com'
    return DysmsapiClient(config)


def send_verify_code(phone: str) -> tuple:
    """
    发送6位数字验证码
    返回: (success: bool, message: str)
    """
    # 检查SDK是否安装
    if not ALIBABA_SMS_SDK:
        return False, '短信SDK未安装，请执行：pip install alibabacloud_dysmsapi20170525'

    # 检查配置
    if not settings.SMS_ACCESS_KEY_ID or not settings.SMS_ACCESS_KEY_SECRET:
        return False, '短信服务未配置，请检查SMS_ACCESS_KEY_ID和SMS_ACCESS_KEY_SECRET'
    if not settings.SMS_SIGN_NAME or not settings.SMS_TEMPLATE_CODE:
        return False, '短信签名或模板未配置'

    # 频率限制：60秒内只能发一次
    limit_key = f'sms_limit:{phone}'
    if cache.get(limit_key):
        return False, '发送过于频繁，请60秒后再试'

    # 生成6位验证码
    code = ''.join([str(random.randint(0, 9)) for _ in range(6)])

    try:
        client = _create_client()
        send_request = dysmsapi_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=settings.SMS_SIGN_NAME,
            template_code=settings.SMS_TEMPLATE_CODE,
            template_param=json.dumps({'code': code})
        )
        response = client.send_sms(send_request)

        if response.body.code == 'OK':
            # 验证码缓存5分钟
            cache.set(f'sms_code:{phone}', code, timeout=300)
            # 发送频率限制60秒
            cache.set(limit_key, True, timeout=60)
            return True, '验证码已发送'
        else:
            return False, response.body.message or '发送失败'

    except Exception as e:
        return False, f'发送异常: {str(e)}'


def verify_sms_code(phone: str, code: str) -> bool:
    """校验验证码，验证成功后清除缓存"""
    cache_key = f'sms_code:{phone}'
    cached = cache.get(cache_key)
    if cached and str(cached) == str(code):
        cache.delete(cache_key)
        return True
    return False
