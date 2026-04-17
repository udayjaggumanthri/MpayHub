"""
URL configuration for fund management app.
"""
from django.urls import path

from apps.fund_management import views

app_name = 'fund_management'

urlpatterns = [
    # Pay-in endpoints
    path('pay-in/packages/', views.pay_in_packages_view, name='pay-in-packages'),
    path('pay-in/quote/', views.pay_in_quote_view, name='pay-in-quote'),
    path('pay-in/create-order/', views.pay_in_create_order_view, name='pay-in-create-order'),
    path('pay-in/verify-razorpay/', views.pay_in_verify_razorpay_view, name='pay-in-verify-razorpay'),
    path('pay-in/complete-mock/', views.pay_in_complete_mock_view, name='pay-in-complete-mock'),

    # Package assignment endpoints
    path('packages/user/<int:user_id>/', views.user_packages_view, name='user-packages'),
    path('packages/assignable/', views.assignable_packages_view, name='assignable-packages'),
    path('packages/assign/', views.assign_package_view, name='assign-package'),
    path('packages/unassign/', views.remove_package_assignment_view, name='unassign-package'),
    path('packages/set-default/', views.set_default_package_view, name='set-default-package'),
    path('packages/clear-default/', views.clear_default_package_view, name='clear-default-package'),

    # Payout endpoints
    path('payout/quote/', views.payout_quote_view, name='payout-quote'),
    path('payout/', views.payout_view, name='payout'),
    path('payout/list/', views.payout_list_view, name='payout-list'),

    # Legacy / misc
    path('load-money/', views.load_money_view, name='load-money'),
    path('load-money/list/', views.load_money_list_view, name='load-money-list'),
    path('gateways/', views.get_gateways_view, name='gateways'),
]
