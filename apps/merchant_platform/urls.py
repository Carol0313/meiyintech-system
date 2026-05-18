from django.urls import path
from . import views

urlpatterns = [
    path('', views.merchant_dashboard, name='merchant_dashboard'),
    path('settings/', views.merchant_settings, name='merchant_settings'),
    # 会员管理
    path('members/', views.member_list, name='member_list'),
    path('members/<int:profile_id>/approve/', views.member_approve, name='member_approve'),
    path('members/<int:profile_id>/reject/', views.member_reject, name='member_reject'),
    path('members/<int:profile_id>/adjust-credit/', views.member_adjust_credit, name='member_adjust_credit'),
    # 工厂管理
    path('factories/', views.factory_list, name='factory_list'),
    path('factories/add/', views.factory_add, name='factory_add'),
    path('factories/<uuid:pk>/edit/', views.factory_edit, name='factory_edit'),
    # 商品规格
    path('specs/', views.spec_list, name='spec_list'),
    path('specs/toggle/', views.spec_toggle, name='spec_toggle'),
    path('specs/custom-request/', views.spec_custom_request, name='spec_custom_request'),
    # 订单管理
    path('orders/', views.merchant_orders, name='merchant_orders'),
    path('orders/<uuid:order_id>/', views.merchant_order_detail, name='merchant_order_detail'),
    path('orders/<uuid:order_id>/upload-photo/', views.upload_production_photo, name='upload_production_photo'),
    path('orders/<uuid:order_id>/remake/', views.remake_order_create, name='remake_order_create'),
    # 拼版工具
    path('plate-layout/', views.plate_layout_orders, name='plate_layout_orders'),
    path('plate-layout/<uuid:order_id>/work/', views.plate_layout_work, name='plate_layout_work'),
    path('production-board/', views.factory_production_board, name='factory_production_board'),
    # 岗位与子账号
    path('roles/', views.role_list, name='role_list'),
    path('roles/<int:role_id>/edit/', views.role_edit, name='role_edit'),
    path('subaccounts/', views.subaccount_list, name='subaccount_list'),
    path('subaccounts/add/', views.subaccount_add, name='subaccount_add'),
    path('subaccounts/<int:staff_id>/edit/', views.subaccount_edit, name='subaccount_edit'),
]
