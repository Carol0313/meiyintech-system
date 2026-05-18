"""
商户平台模型
包含：工厂信息
"""

import uuid
from django.db import models


class Factory(models.Model):
    """工厂信息"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(
        'accounts.Merchant', on_delete=models.CASCADE, related_name='factories',
        verbose_name='所属商家'
    )
    name = models.CharField('工厂名称', max_length=200)
    address = models.TextField('工厂地址', blank=True)
    contact_person = models.CharField('联系人', max_length=50, blank=True)
    contact_phone = models.CharField('联系电话', max_length=20, blank=True)
    is_active = models.BooleanField('是否启用', default=True)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        verbose_name = '工厂'
        verbose_name_plural = '工厂'

    def __str__(self):
        return f"{self.name} ({self.merchant.name})"
