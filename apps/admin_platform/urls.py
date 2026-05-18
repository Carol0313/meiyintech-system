from django.urls import path
from . import views

urlpatterns = [
    path('', views.admin_dashboard, name='admin_dashboard'),
    path('merchants/', views.admin_merchants, name='admin_merchants'),
    path('merchants/<uuid:merchant_id>/approve/', views.merchant_approve, name='merchant_approve'),
    path('merchants/<uuid:merchant_id>/reject/', views.merchant_reject, name='merchant_reject'),
    path('merchants/<uuid:merchant_id>/freeze/', views.merchant_freeze, name='merchant_freeze'),
    path('merchants/add/', views.merchant_add, name='merchant_add'),
    path('merchants/<uuid:merchant_id>/edit/', views.merchant_edit, name='merchant_edit'),
    path('roles/', views.admin_roles, name='admin_roles'),
    path('roles/<int:role_id>/edit/', views.admin_role_edit, name='admin_role_edit'),
    path('spec-requests/', views.admin_spec_requests, name='admin_spec_requests'),
    path('spec-requests/<int:req_id>/approve/', views.spec_request_approve, name='spec_request_approve'),
    path('spec-requests/<int:req_id>/reject/', views.spec_request_reject, name='spec_request_reject'),
]
