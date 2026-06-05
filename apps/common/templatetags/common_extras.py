import json
from django import template

register = template.Library()


@register.filter
def load_json(value):
    """将 JSON 字符串解析为 Python 对象"""
    if not value:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return None
