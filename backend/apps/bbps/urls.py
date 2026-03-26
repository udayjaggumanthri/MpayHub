"""
URL configuration for BBPS app.
"""
from django.urls import path
from apps.bbps import views

app_name = 'bbps'

urlpatterns = [
    path('categories/', views.get_categories_view, name='categories'),
    path('billers/<str:category>/', views.get_billers_view, name='billers'),
    path('fetch-bill/', views.fetch_bill_view, name='fetch-bill'),
    path('pay/', views.pay_bill_view, name='pay'),
    path('payments/', views.bill_payments_list_view, name='payments'),
    path('payments/<int:payment_id>/', views.bill_payment_detail_view, name='payment-detail'),
]
