"""
URL configuration for mPayhub project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # API Endpoints
    path('api/auth/', include('apps.authentication.urls')),
    path('api/users/', include('apps.users.urls')),
    path('api/wallets/', include('apps.wallets.urls')),
    path('api/fund-management/', include('apps.fund_management.urls')),
    path('api/bbps/', include('apps.bbps.urls')),
    path('api/contacts/', include('apps.contacts.urls')),
    path('api/bank-accounts/', include('apps.bank_accounts.urls')),
    path('api/transactions/', include('apps.transactions.urls')),
    path('api/passbook/', include('apps.transactions.urls_passbook')),
    path('api/reports/', include('apps.transactions.urls_reports')),
    path('api/admin/', include('apps.admin_panel.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
