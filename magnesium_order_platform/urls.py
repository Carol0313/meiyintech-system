"""
根URL配置
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('customer/', include('apps.customer_platform.urls')),
    path('merchant/', include('apps.merchant_platform.urls')),
    path('platform/', include('apps.admin_platform.urls')),
    # 快递100回调
    path('webhook/kuaidi100/', include('apps.merchant_platform.urls_kuaidi100')),
    path('', include('apps.accounts.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
