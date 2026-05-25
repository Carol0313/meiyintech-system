from django.urls import path
from . import views

urlpatterns = [
    path('', views.customer_dashboard, name='customer_dashboard'),
    path('place-order/', views.place_order, name='place_order'),
    path('place-order/quick/', views.quick_order, name='quick_order'),
    path('place-order/quick/upload/', views.quick_order_upload, name='quick_order_upload'),
    path('place-order/batch-upload/', views.batch_upload_files, name='batch_upload_files'),
    path('place-order/step1/', views.order_step1, name='order_step1'),
    path('place-order/step2/<uuid:draft_id>/', views.order_step2, name='order_step2'),
    path('place-order/step3/<uuid:draft_id>/', views.order_step3, name='order_step3'),
    path('place-order/step4/<uuid:draft_id>/', views.order_step4, name='order_step4'),
    path('place-order/step5/<uuid:draft_id>/', views.order_step5, name='order_step5'),
    path('place-order/step6/<uuid:draft_id>/', views.order_step6, name='order_step6'),
    path('place-order/step7/<uuid:draft_id>/', views.order_step7, name='order_step7'),
    path('place-order/remove/<uuid:draft_id>/', views.remove_draft, name='remove_draft'),
    path('place-order/submit/', views.submit_orders, name='submit_orders'),
    path('orders/', views.my_orders, name='my_orders'),
    path('orders/<uuid:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<uuid:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    path('orders/<uuid:order_id>/confirm-receipt/', views.confirm_receipt, name='confirm_receipt'),
    path('profile/', views.profile_view, name='profile'),
    path('subaccounts/', views.subaccount_list, name='customer_subaccount_list'),
    path('subaccounts/add/', views.subaccount_add, name='customer_subaccount_add'),
    path('subaccounts/<int:user_id>/edit/', views.subaccount_edit, name='customer_subaccount_edit'),
    # 对账单
    path('statements/', views.customer_statements, name='customer_statements'),
    path('statements/<uuid:statement_id>/', views.customer_statement_detail, name='customer_statement_detail'),
    path('statements/<uuid:statement_id>/confirm/', views.customer_statement_confirm, name='customer_statement_confirm'),
    path('statements/<uuid:statement_id>/export/', views.customer_statement_export, name='customer_statement_export'),
]
