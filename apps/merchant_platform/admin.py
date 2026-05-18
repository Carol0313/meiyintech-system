from django.contrib import admin
from .models import Factory


@admin.register(Factory)
class FactoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'merchant', 'contact_person', 'contact_phone', 'is_active']
    list_filter = ['merchant', 'is_active']
