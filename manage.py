#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
import socket

# 修复 Windows 中文计算机名导致的 socket.getfqdn() 编码错误
_orig_getfqdn = socket.getfqdn

def _patched_getfqdn(name=''):
    try:
        return _orig_getfqdn(name)
    except UnicodeDecodeError:
        return name or 'localhost'

socket.getfqdn = _patched_getfqdn


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'magnesium_order_platform.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
