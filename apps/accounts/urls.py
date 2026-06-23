from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.user_login, name='login'),
    path('login-phone/', views.phone_code_login, name='phone_code_login'),
    path('api/send-verify-code/', views.api_send_verify_code, name='send_verify_code'),
    path('logout/', views.user_logout, name='logout'),
    path('register/customer/', views.customer_register, name='customer_register'),
    path('register/merchant/', views.merchant_register, name='merchant_register'),
    path('forget-password/', views.forget_password, name='forget_password'),
    path('profile/', views.profile, name='profile'),
    path('addresses/', views.my_addresses, name='my_addresses'),
    path('addresses/add/', views.address_add, name='address_add'),
    path('addresses/<int:pk>/edit/', views.address_edit, name='address_edit'),
    path('addresses/<int:pk>/delete/', views.address_delete, name='address_delete'),
]
