from django.contrib import admin
from .models import Order, OrderItem, OrderStatusLog, CommunicationLog, PlateLayout, ProductionPhoto


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['sn', 'customer', 'merchant', 'status', 'total_amount', 'urgent', 'created_at']
    list_filter = ['status', 'urgent', 'merchant']
    search_fields = ['sn', 'customer__phone']
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product_name', 'material', 'thickness', 'area', 'subtotal']


@admin.register(OrderStatusLog)
class OrderStatusLogAdmin(admin.ModelAdmin):
    list_display = ['order', 'from_status', 'to_status', 'operator', 'created_at']


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = ['order', 'sender', 'content', 'created_at']


@admin.register(PlateLayout)
class PlateLayoutAdmin(admin.ModelAdmin):
    list_display = ['order', 'designer', 'material_usage_rate', 'created_at']


@admin.register(ProductionPhoto)
class ProductionPhotoAdmin(admin.ModelAdmin):
    list_display = ['order', 'photo_type', 'uploaded_by', 'uploaded_at']
