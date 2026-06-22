"""
快递100推送回调URL配置
"""
from django.urls import path
from . import views_kuaidi100

urlpatterns = [
    path('', views_kuaidi100.kuaidi100_callback, name='kuaidi100_callback'),
]
