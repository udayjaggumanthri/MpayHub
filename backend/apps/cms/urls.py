from django.urls import path

from apps.cms import views

urlpatterns = [
    path('me/status/', views.me_status, name='cms-me-status'),
    path('launch/', views.launch, name='cms-launch'),
    path('wallet/', views.wallet_get, name='cms-wallet'),
    path('wallet/fund/', views.wallet_fund, name='cms-wallet-fund'),
    path('transactions/', views.transactions_list, name='cms-transactions'),
    path('reports/summary/', views.reports_summary, name='cms-reports-summary'),
    path('reports/export.csv', views.reports_export_csv, name='cms-reports-export'),
    path('admin/provider-config/', views.admin_provider_config, name='cms-admin-provider'),
    path('admin/entitlements/enable/', views.admin_entitlement_enable, name='cms-admin-entitle'),
    path('admin/entitlements/disable/', views.admin_entitlement_disable, name='cms-admin-entitle-off'),
    path('admin/entitlements/user/<int:user_id>/', views.admin_entitlements_for_user, name='cms-admin-entitle-user'),
    path('admin/agents/', views.admin_agents, name='cms-admin-agents'),
    path('admin/agents/<int:agent_id>/reset-pin/', views.admin_agent_reset_pin, name='cms-admin-agent-reset-pin'),
    path('admin/audit-logs/', views.admin_audit_logs, name='cms-admin-audit-logs'),
    path('webhooks/fingpay/wallet-check/', views.webhook_wallet_check, name='cms-webhook-wallet-check'),
    path('webhooks/fingpay/wallet-debit/', views.webhook_wallet_debit, name='cms-webhook-wallet-debit'),
    path('webhooks/fingpay/txn-result/', views.webhook_txn_result, name='cms-webhook-txn-result'),
]
