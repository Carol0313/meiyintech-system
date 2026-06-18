"""商户员工 RBAC 权限校验。"""

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from apps.accounts.models import Role

# 角色未单独配置 permissions 时的默认权限（按岗位名称）
ROLE_DEFAULT_PERMISSIONS = {
    'admin': set(Role.VALID_PERMISSIONS),
    'customer_service': {
        'order_view', 'order_audit', 'order_ship', 'member_manage',
    },
    'designer': {
        'order_view', 'design_layout', 'order_production',
    },
    'finance': {
        'order_view', 'finance_manage', 'member_manage',
    },
    'production': {
        'order_view', 'order_production', 'order_ship', 'factory_manage',
    },
}


def staff_has_permission(user, *permission_codes):
    """merchant_admin 始终有权限；员工按 Role 校验。"""
    if not permission_codes:
        return True
    if user.user_type == 'merchant_admin':
        return True
    if user.user_type != 'merchant_staff':
        return False
    profile = getattr(user, 'staff_profile', None)
    if not profile or not profile.is_active or not profile.role:
        return False
    role = profile.role
    perms = role.permissions or {}
    if isinstance(perms, dict) and any(perms.values()):
        return any(role.has_permission(code) for code in permission_codes)
    defaults = ROLE_DEFAULT_PERMISSIONS.get(role.name, set())
    return any(code in defaults for code in permission_codes)


def staff_permission(*permission_codes):
    """装饰器：要求商户员工具备指定权限之一（管理员始终放行）。"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if staff_has_permission(request.user, *permission_codes):
                return view_func(request, *args, **kwargs)
            messages.error(request, '您没有访问此功能的权限')
            return redirect('merchant_dashboard')
        return wrapper
    return decorator
