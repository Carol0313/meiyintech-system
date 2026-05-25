"""
全局模板上下文处理器
"""

from apps.accounts.models import Merchant


def global_context(request):
    """为所有模板提供全局上下文变量"""
    ctx = {
        'app_name': '闪电制版下单系统',
        'user_type_display': '',
        'user_merchant': None,
    }
    if request.user.is_authenticated:
        ctx['user_type_display'] = request.user.get_user_type_display()
        if request.user.user_type in ('merchant_admin', 'merchant_staff'):
            profile = getattr(request.user, 'staff_profile', None)
            if profile:
                ctx['user_merchant'] = profile.merchant
        elif request.user.user_type == 'customer':
            profile = getattr(request.user, 'customer_profile', None)
            if profile:
                ctx['user_merchant'] = profile.merchant
                ctx['effective_customer_profile'] = request.user.get_effective_customer_profile()
                ctx['is_customer_main'] = profile.is_main_account
    return ctx
