from django.contrib import admin
from .models import ProductSpec, CustomSpecRequest


@admin.register(ProductSpec)
class ProductSpecAdmin(admin.ModelAdmin):
    list_display = ['product_name', 'material', 'thickness', 'unit_price', 'is_platform_preset', 'is_active']
    list_filter = ['product_name', 'material', 'is_platform_preset', 'is_active']


@admin.register(CustomSpecRequest)
class CustomSpecRequestAdmin(admin.ModelAdmin):
    list_display = ['merchant', 'material', 'process_type', 'thickness', 'status', 'created_at']
    list_filter = ['status']
