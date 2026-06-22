"""
快递100推送回调处理视图
文档：https://api.kuaidi100.com/document/5f0ff4a29777d50d94e1026a.html
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from apps.orders.models import Order
from utils.kuaidi100 import parse_callback_data, verify_callback_sign, format_tracking_data

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def kuaidi100_callback(request):
    """
    快递100物流推送回调接口
    当订阅的物流单号状态变更时，快递100会主动推送数据到此接口
    
    请求格式：
    {
        "status": "polling",  // 推送状态
        "billstatus": "",     // 签收状态
        "message": "",        // 消息
        "autoCheck": "0",     // 是否自动识别
        "comOld": "",         // 原快递公司
        "comNew": "",         // 新快递公司
        "nu": "123456",       // 快递单号
        "ischeck": "0",       // 是否签收
        "condition": "F00",   // 状态码
        "data": [             // 物流轨迹
            {"time": "2024-01-01 10:00:00", "context": "快件已签收", "location": ""}
        ]
    }
    """
    try:
        # 解析请求体
        body = request.body
        
        # 尝试解析JSON
        try:
            data = json.loads(body.decode('utf-8'))
        except json.JSONDecodeError:
            # 可能是form-data格式
            param = request.POST.get('param', '')
            sign = request.POST.get('sign', '')
            if param:
                data = json.loads(param)
            else:
                logger.warning("快递100回调无法解析数据")
                return JsonResponse({'result': 'false', 'returnCode': '500', 'message': '无法解析数据'})
        
        # 获取快递单号
        tracking_number = data.get('nu', '')
        if not tracking_number:
            logger.warning("快递100回调缺少单号")
            return JsonResponse({'result': 'false', 'returnCode': '500', 'message': '缺少单号'})
        
        # 查找对应订单
        orders = Order.objects.filter(tracking_number=tracking_number)
        if not orders.exists():
            logger.warning("快递100回调未找到订单: %s", tracking_number)
            return JsonResponse({'result': 'false', 'returnCode': '500', 'message': '未找到订单'})
        
        # 格式化数据
        tracking_data = format_tracking_data(data)
        
        # 更新所有匹配订单的缓存
        for order in orders:
            order.update_tracking_cache(tracking_data)
            logger.info("更新订单物流缓存: order=%s state=%s", order.id, tracking_data.get('state'))
            
            # 如果已签收，自动确认收货（可选）
            if tracking_data.get('is_signed') and order.status == 'shipped':
                # 可以在这里自动确认收货，或者发送通知
                logger.info("订单已签收: order=%s", order.id)
        
        # 返回成功响应（快递100要求特定格式）
        return JsonResponse({
            'result': 'true',
            'returnCode': '200',
            'message': '成功'
        })
        
    except Exception as e:
        logger.exception("快递100回调处理异常")
        return JsonResponse({
            'result': 'false',
            'returnCode': '500',
            'message': f'处理异常: {str(e)}'
        })
