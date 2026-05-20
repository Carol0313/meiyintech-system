from django.urls import path
from . import views

urlpatterns = [
    path('', views.customer_dashboard, name='customer_dashboard'),
    path('place-order/', views.place_order, name='place_order'),
    path('place-order/quick/', views.quick_order, name='quick_order'),
    path('place-order/quick/upload/', views.quick_order_upload, name='quick_order_upload'),
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
    path('profile/', views.profile_view, name='profile'),
]
