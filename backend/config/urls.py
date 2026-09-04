"""
URL configuration for mPayhub project.
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path, include, re_path
from django.views.static import serve as static_serve
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.views import health_view


def api_root(_request):
    """Quiet probe/bot traffic to ``GET /`` (avoids 404 noise in API logs)."""
    return JsonResponse({'service': 'mpayhub-api', 'status': 'ok'})


urlpatterns = [
    path('', api_root),
    path('api/health/', health_view, name='api-health'),
    path('admin/', admin.site.urls),

    # API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # API Endpoints
    path('api/auth/', include('apps.authentication.urls')),
    path('api/users/', include('apps.users.urls')),
    path('api/wallets/', include('apps.wallets.urls')),
    path('api/fund-management/', include('apps.fund_management.urls')),
    path('api/integrations/', include('apps.integrations.urls')),
    path('api/bbps/', include('apps.bbps.urls')),
    path('api/aeps/', include('apps.aeps.urls')),
    path('api/contacts/', include('apps.contacts.urls')),
    path('api/bank-accounts/', include('apps.bank_accounts.urls')),
    path('api/transactions/', include('apps.transactions.urls')),
    path('api/passbook/', include('apps.transactions.urls_passbook')),
    path('api/reports/', include('apps.transactions.urls_reports')),
    path('api/admin/', include('apps.admin_panel.urls')),
    path('api/admin/session-security/', include('apps.session_security.urls')),
    path('api/admin/wallet-adjustments/', include('apps.wallet_adjustments.urls')),
    path('api/system/', include('apps.core.urls')),
]

# django.conf.urls.static.static() is a no-op when DEBUG=False — serve MEDIA explicitly
# so Gunicorn :8002 can deliver QR/receipt files for the split UI (:3002) deploy.
_media_url = (settings.MEDIA_URL or '/media/').lstrip('/')
urlpatterns += [
    re_path(
        rf'^{_media_url}(?P<path>.*)$',
        static_serve,
        {'document_root': settings.MEDIA_ROOT},
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
