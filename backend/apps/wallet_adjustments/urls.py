from django.urls import path

from apps.wallet_adjustments import views

urlpatterns = [
    path('', views.adjustments_collection_view, name='wallet-adjustments-collection'),
    path('export.xlsx', views.export_adjustments_view, name='wallet-adjustments-export'),
    path('user-lookup/', views.user_lookup_view, name='wallet-adjustments-user-lookup'),
]
