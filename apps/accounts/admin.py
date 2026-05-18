from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Merchant, CustomerProfile, StaffProfile, Role, Address


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['phone', 'username', 'user_type', 'is_approved', 'is_staff', 'created_at']
    list_filter = ['user_type', 'is_approved', 'is_staff']
    search_fields = ['phone', 'username']
    ordering = ['-created_at']
    fieldsets = UserAdmin.fieldsets + (
        ('扩展信息', {'fields': ('user_type', 'phone', 'avatar', 'is_approved')}),
    )


@admin.register(Merchant)
class MerchantAdmin(admin.ModelAdmin):
    list_display = ['name', 'status', 'invite_code', 'contact_phone', 'created_at']
    list_filter = ['status']
    search_fields = ['name', 'invite_code']


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'company_name', 'merchant', 'credit_limit', 'credit_used', 'registration_status']
    list_filter = ['registration_status', 'merchant']
    search_fields = ['user__phone', 'company_name']


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'merchant', 'role', 'is_active']
    list_filter = ['merchant', 'is_active']


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'merchant', 'is_platform_preset']
    list_filter = ['is_platform_preset', 'name']


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'contact_name', 'phone', 'province', 'city', 'is_default']
