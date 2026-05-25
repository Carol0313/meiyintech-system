from django.urls import path
from . import views

urlpatterns = [
    path('', views.merchant_dashboard, name='merchant_dashboard'),
    path('settings/', views.merchant_settings, name='merchant_settings'),
    # 会员管理
    path('members/', views.member_list, name='member_list'),
    path('members/<int:profile_id>/pricing/', views.member_pricing, name='member_pricing'),
    path('members/<int:profile_id>/approve/', views.member_approve, name='member_approve'),
    path('members/<int:profile_id>/reject/', views.member_reject, name='member_reject'),
    path('members/<int:profile_id>/adjust-credit/', views.member_adjust_credit, name='member_adjust_credit'),
    # 工厂管理
    path('factories/', views.factory_list, name='factory_list'),
    path('factories/add/', views.factory_add, name='factory_add'),
    path('factories/<uuid:pk>/edit/', views.factory_edit, name='factory_edit'),
    path('factories/<uuid:pk>/', views.factory_detail, name='factory_detail'),
    path('factories/<uuid:pk>/export-inventory/', views.export_inventory, name='export_inventory'),
    # 商品规格
    path('specs/', views.spec_list, name='spec_list'),
    path('specs/toggle/', views.spec_toggle, name='spec_toggle'),
    path('specs/custom-request/', views.spec_custom_request, name='spec_custom_request'),
    # 订单管理
    path('orders/', views.merchant_orders, name='merchant_orders'),
    path('orders/batch-process/', views.batch_process_orders, name='batch_process_orders'),
    path('orders/<uuid:order_id>/', views.merchant_order_detail, name='merchant_order_detail'),
    path('orders/<uuid:order_id>/upload-photo/', views.upload_production_photo, name='upload_production_photo'),
    path('orders/<uuid:order_id>/remake/', views.remake_order_create, name='remake_order_create'),
    # 拼版工具（新版：跨订单拼版批次）
    path('plate-batches/', views.plate_batch_list, name='plate_batch_list'),
    path('plate-batches/generate/', views.plate_batch_generate, name='plate_batch_generate'),
    path('plate-batches/<uuid:batch_id>/', views.plate_batch_detail, name='plate_batch_detail'),
    path('plate-batches/<uuid:batch_id>/confirm/', views.plate_batch_confirm, name='plate_batch_confirm'),
    path('plate-batches/<uuid:batch_id>/reject/', views.plate_batch_reject, name='plate_batch_reject'),
    path('plate-batches/<uuid:batch_id>/update-layout/', views.plate_batch_update_layout, name='plate_batch_update_layout'),
    # 拼版工具（旧版兼容）
    path('plate-layout/', views.plate_layout_orders, name='plate_layout_orders'),
    path('plate-layout/<uuid:order_id>/work/', views.plate_layout_work, name='plate_layout_work'),
    path('production-board/', views.factory_production_board, name='factory_production_board'),
    # 岗位与子账号
    path('roles/', views.role_list, name='role_list'),
    path('roles/<int:role_id>/edit/', views.role_edit, name='role_edit'),
    path('subaccounts/', views.subaccount_list, name='subaccount_list'),
    path('subaccounts/add/', views.subaccount_add, name='subaccount_add'),
    path('subaccounts/<int:staff_id>/edit/', views.subaccount_edit, name='subaccount_edit'),
    # 对账单管理
    path('statements/', views.statement_list, name='statement_list'),
    path('statements/generate/', views.statement_generate, name='statement_generate'),
    path('statements/<uuid:statement_id>/', views.statement_detail, name='statement_detail'),
    path('statements/<uuid:statement_id>/mark-paid/', views.statement_mark_paid, name='statement_mark_paid'),
    path('statements/<uuid:statement_id>/settle/', views.statement_settle, name='statement_settle'),
    path('statements/<uuid:statement_id>/export/', views.statement_export, name='statement_export'),
]
