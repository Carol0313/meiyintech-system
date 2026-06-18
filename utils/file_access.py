"""客户上传文件路径归属校验。"""


def get_customer_file_prefixes(user):
    """返回当前用户可访问的 order_files 路径前缀列表。"""
    prefixes = {f'order_files/{user.id}/'}
    profile = getattr(user, 'get_effective_customer_profile', lambda: None)()
    if profile and getattr(profile, 'is_main_account', False):
        from apps.accounts.models import CustomerProfile
        sub_ids = CustomerProfile.objects.filter(parent=profile).values_list('user_id', flat=True)
        for sid in sub_ids:
            prefixes.add(f'order_files/{sid}/')
    return prefixes


def assert_customer_file_path(user, file_path):
    """
    校验 file_path 属于当前客户（含主账号下的子账号）。
    返回 (ok: bool, error: str)
    """
    if not file_path or not isinstance(file_path, str):
        return False, '缺少文件路径'
    normalized = file_path.strip().replace('\\', '/').lstrip('/')
    if '..' in normalized.split('/'):
        return False, '非法文件路径'
    prefixes = get_customer_file_prefixes(user)
    if any(normalized.startswith(p) for p in prefixes):
        return True, ''
    return False, '无权访问该文件'
