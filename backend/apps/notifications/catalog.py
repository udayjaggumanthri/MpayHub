"""
SMS event catalog — event_key values are code-defined; admin can only enable/configure existing keys.

Domain code passes semantic variable names (otp, amount, name, …).
Admin maps them to MSG91 Flow recipient keys via SmsNotificationTemplate.variable_map.
Those keys must match the template body exactly (##amount## → amount, ##var1## → var1).
"""

SMS_EVENT_CATALOG = [
    {
        'event_key': 'auth.otp.verification',
        'module': 'auth',
        'label': 'OTP — Verification',
        'description': (
            'Single MSG91 template for all verification OTPs (password reset, MPIN reset). '
            'Template shape: Dear {#var#}, Your OTP … is {#var#}. Valid for 10 minutes. '
            'Aadhaar uses DigiLocker — no SMS OTP.'
        ),
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'Customer name (Dear …)'},
            {'name': 'otp', 'required': True, 'description': 'OTP / verification code'},
        ],
        'sample_variables': {'name': 'Customer', 'otp': '123456'},
        # Suggested MSG91 Flow mapping for Admin UI auto-fill after fetch
        'default_variable_map': {'name': 'var1', 'otp': 'var2'},
    },
    {
        'event_key': 'payin.success',
        'module': 'payin',
        'label': 'Pay-in Successful',
        'description': (
            'Hi, Your MPAYHUB Wallet has been credited with Rs. {#var#} via Txn ID: {#var#}.'
        ),
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Credited amount (Rs.)'},
            {'name': 'transaction_id', 'required': True, 'description': 'Txn ID'},
        ],
        # MSG91 Flow body uses ##amount## / ##transaction_id## — keys must match names
        'sample_variables': {'amount': '1000.00', 'transaction_id': 'LM123'},
        'default_variable_map': {'amount': 'amount', 'transaction_id': 'transaction_id'},
    },
    {
        'event_key': 'payin.failed',
        'module': 'payin',
        'label': 'Pay-in Failed',
        'description': (
            'Wallet top-up of Rs. {#var#} has failed. Txn ID: {#var#}.'
        ),
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Attempted amount (Rs.)'},
            {'name': 'transaction_id', 'required': True, 'description': 'Txn ID'},
        ],
        'sample_variables': {'amount': '1000.00', 'transaction_id': 'LM123'},
        'default_variable_map': {'amount': 'amount', 'transaction_id': 'transaction_id'},
    },
    {
        'event_key': 'payin.pending',
        'module': 'payin',
        'label': 'Pay-in Pending',
        'description': (
            'Wallet top-up of Rs. {#var#} is pending. Txn ID: {#var#}.'
        ),
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Order amount (Rs.)'},
            {'name': 'transaction_id', 'required': True, 'description': 'Txn ID'},
        ],
        'sample_variables': {'amount': '1000.00', 'transaction_id': 'LM123'},
        'default_variable_map': {'amount': 'amount', 'transaction_id': 'transaction_id'},
    },
    {
        'event_key': 'payout.success',
        'module': 'payout',
        'label': 'Payout Successful',
        'description': (
            'Payout of Rs. {#var#} to A/c {#var#} SUCCESSFULLY. UTR: {#var#}.'
        ),
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Payout amount (Rs.)'},
            {'name': 'account', 'required': True, 'description': 'Masked account number'},
            {'name': 'utr', 'required': True, 'description': 'UTR / bank reference'},
        ],
        'sample_variables': {'amount': '500.00', 'account': 'XXXX1234', 'utr': 'UTR123456'},
        'default_variable_map': {'amount': 'amount', 'account': 'account', 'utr': 'utr'},
    },
    {
        'event_key': 'payout.failed',
        'module': 'payout',
        'label': 'Payout Failed',
        'description': (
            'Payout of Rs. {#var#} to Account {#var#} failed. Txn ID: {#var#}. Amount restored.'
        ),
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Attempted amount (Rs.)'},
            {'name': 'account', 'required': True, 'description': 'Masked account number'},
            {'name': 'transaction_id', 'required': True, 'description': 'Txn ID'},
        ],
        'sample_variables': {
            'amount': '500.00',
            'account': 'XXXX1234',
            'transaction_id': 'PTX123',
        },
        'default_variable_map': {
            'amount': 'amount',
            'account': 'account',
            'transaction_id': 'transaction_id',
        },
    },
    {
        'event_key': 'payout.pending',
        'module': 'payout',
        'label': 'Payout Pending',
        'description': 'Payout initiated; settlement pending (no dedicated MSG91 template yet).',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Payout amount'},
            {'name': 'transaction_id', 'required': True, 'description': 'Txn ID'},
        ],
        'sample_variables': {'amount': '500.00', 'transaction_id': 'PTX123'},
        'default_variable_map': {'amount': 'amount', 'transaction_id': 'transaction_id'},
    },
    {
        'event_key': 'bbps.payment.success',
        'module': 'bbps',
        'label': 'Bill Pay Successful',
        'description': (
            'Bill payment of Rs. {#var#} for {#var#} (Consumer ID: {#var#}) SUCCESSFUL. '
            'Receipt No: {#var#}.'
        ),
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Paid amount (Rs.)'},
            {'name': 'biller', 'required': True, 'description': 'Biller / service name'},
            {'name': 'consumer_id', 'required': True, 'description': 'Consumer ID'},
            {'name': 'receipt_no', 'required': True, 'description': 'Receipt / txn reference'},
        ],
        'sample_variables': {
            'amount': '250.00',
            'biller': 'Electricity Co',
            'consumer_id': '9876543210',
            'receipt_no': 'RCP123',
        },
        'default_variable_map': {
            'amount': 'amount',
            'biller': 'biller',
            'consumer_id': 'consumer_id',
            'receipt_no': 'receipt_no',
        },
    },
    {
        'event_key': 'bbps.payment.failed',
        'module': 'bbps',
        'label': 'Bill Pay Fail',
        'description': 'Bill payment failed (configure MSG91 template when available).',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Attempted amount'},
            {'name': 'biller', 'required': True, 'description': 'Biller name'},
            {'name': 'consumer_id', 'required': False, 'description': 'Consumer ID'},
            {'name': 'reason', 'required': False, 'description': 'Failure reason'},
        ],
        'sample_variables': {
            'amount': '250.00',
            'biller': 'Electricity Co',
            'consumer_id': '9876543210',
            'reason': 'Declined',
        },
        'default_variable_map': {
            'amount': 'amount',
            'biller': 'biller',
            'consumer_id': 'consumer_id',
            'reason': 'reason',
        },
    },
    {
        'event_key': 'bbps.payment.awaited',
        'module': 'bbps',
        'label': 'Bill Pay Pending',
        'description': 'Payment awaited / confirmation pending (configure MSG91 template when available).',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'biller', 'required': True, 'description': 'Biller name'},
            {'name': 'consumer_id', 'required': False, 'description': 'Consumer ID'},
            {'name': 'txn_ref', 'required': False, 'description': 'Transaction reference'},
        ],
        'sample_variables': {
            'amount': '250.00',
            'biller': 'Electricity Co',
            'consumer_id': '9876543210',
            'txn_ref': 'TXN123',
        },
        'default_variable_map': {
            'amount': 'amount',
            'biller': 'biller',
            'consumer_id': 'consumer_id',
            'txn_ref': 'txn_ref',
        },
    },
    {
        'event_key': 'bbps.payment.success_poll',
        'module': 'bbps',
        'label': 'Bill Pay Successful (status poll)',
        'description': 'Same variables as Bill Pay Successful; reuse that MSG91 template_id.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Paid amount (Rs.)'},
            {'name': 'biller', 'required': True, 'description': 'Biller / service name'},
            {'name': 'consumer_id', 'required': True, 'description': 'Consumer ID'},
            {'name': 'receipt_no', 'required': True, 'description': 'Receipt / txn reference'},
        ],
        'sample_variables': {
            'amount': '250.00',
            'biller': 'Electricity Co',
            'consumer_id': '9876543210',
            'receipt_no': 'RCP123',
        },
        'default_variable_map': {
            'amount': 'amount',
            'biller': 'biller',
            'consumer_id': 'consumer_id',
            'receipt_no': 'receipt_no',
        },
    },
    {
        'event_key': 'onboarding.welcome',
        'module': 'onboarding',
        'label': 'User Registration',
        'description': 'Welcome SMS after hierarchy user account is created.',
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'User display name'},
            {'name': 'user_id', 'required': True, 'description': 'Public user id'},
        ],
        'sample_variables': {'name': 'Retailer', 'user_id': 'RTL001'},
        # Often ##var1## / ##var2## — override via Fetch if MSG91 uses named vars
        'default_variable_map': {'name': 'var1', 'user_id': 'var2'},
    },
    {
        'event_key': 'complaint.registered',
        'module': 'complaints',
        'label': 'Complaint Registration',
        'description': (
            'Complaint registered. Transaction ID: {#var#}. Complaint ID: {#var#}.'
        ),
        'variable_schema': [
            {'name': 'txn_ref', 'required': True, 'description': 'Transaction ID'},
            {'name': 'complaint_id', 'required': True, 'description': 'Complaint ID'},
        ],
        'sample_variables': {'txn_ref': 'TXN123', 'complaint_id': 'CMP456'},
        # Soft default until Fetch; live MSG91 may use ##var1##/##var2## or named keys
        'default_variable_map': {'txn_ref': 'var1', 'complaint_id': 'var2'},
    },
]

CATALOG_EVENT_KEYS = {e['event_key'] for e in SMS_EVENT_CATALOG}

# Obsolete OTP event keys (replaced by single auth.otp.verification). Soft-deleted on seed.
OBSOLETE_SMS_EVENT_KEYS = frozenset({
    'auth.otp.password_reset',
    'auth.otp.mpin_reset',
    'auth.otp.aadhaar_verification',
    'auth.otp.registration',
})

# All SMS verification OTPs (password / MPIN) share one MSG91 Flow template.
AUTH_OTP_PURPOSE_TO_EVENT = {
    'password-reset': 'auth.otp.verification',
    'mpin-reset': 'auth.otp.verification',
}
