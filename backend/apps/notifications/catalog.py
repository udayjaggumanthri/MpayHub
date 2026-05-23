"""
SMS event catalog — event_key values are code-defined; admin can only enable/configure existing keys.
"""

SMS_EVENT_CATALOG = [
    {
        'event_key': 'auth.otp.password_reset',
        'module': 'auth',
        'label': 'Password reset OTP',
        'description': 'SMS OTP when user requests password reset via phone.',
        'variable_schema': [
            {'name': 'otp', 'required': True, 'description': 'OTP code'},
            {'name': 'expiry_minutes', 'required': True, 'description': 'OTP validity in minutes'},
        ],
        'sample_variables': {'otp': '123456', 'expiry_minutes': '10'},
    },
    {
        'event_key': 'auth.otp.aadhaar_verification',
        'module': 'auth',
        'label': 'Aadhaar verification OTP',
        'description': 'SMS OTP for Aadhaar verification flow.',
        'variable_schema': [
            {'name': 'otp', 'required': True, 'description': 'OTP code'},
            {'name': 'expiry_minutes', 'required': True, 'description': 'OTP validity in minutes'},
        ],
        'sample_variables': {'otp': '123456', 'expiry_minutes': '10'},
    },
    {
        'event_key': 'auth.otp.registration',
        'module': 'auth',
        'label': 'Registration OTP',
        'description': 'Future: phone verification during registration.',
        'variable_schema': [
            {'name': 'otp', 'required': True, 'description': 'OTP code'},
            {'name': 'expiry_minutes', 'required': True, 'description': 'OTP validity in minutes'},
        ],
        'sample_variables': {'otp': '123456', 'expiry_minutes': '10'},
    },
    {
        'event_key': 'auth.otp.mpin_reset',
        'module': 'auth',
        'label': 'MPIN reset OTP',
        'description': 'Future: MPIN reset OTP via SMS.',
        'variable_schema': [
            {'name': 'otp', 'required': True, 'description': 'OTP code'},
            {'name': 'expiry_minutes', 'required': True, 'description': 'OTP validity in minutes'},
        ],
        'sample_variables': {'otp': '123456', 'expiry_minutes': '10'},
    },
    {
        'event_key': 'payin.success',
        'module': 'payin',
        'label': 'Pay-in success',
        'description': 'Load money / Razorpay pay-in credited successfully.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Credited amount'},
            {'name': 'reference', 'required': True, 'description': 'Gateway or txn reference'},
            {'name': 'transaction_id', 'required': True, 'description': 'Load money transaction id'},
        ],
        'sample_variables': {'amount': '1000.00', 'reference': 'GTX123', 'transaction_id': 'LM123'},
    },
    {
        'event_key': 'payin.failed',
        'module': 'payin',
        'label': 'Pay-in failed',
        'description': 'Load money attempt failed.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Attempted amount'},
            {'name': 'reference', 'required': True, 'description': 'Transaction reference'},
            {'name': 'reason', 'required': False, 'description': 'Failure reason'},
        ],
        'sample_variables': {'amount': '1000.00', 'reference': 'LM123', 'reason': 'Payment failed'},
    },
    {
        'event_key': 'payin.pending',
        'module': 'payin',
        'label': 'Pay-in pending',
        'description': 'Optional: order created, payment not yet captured.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Order amount'},
            {'name': 'reference', 'required': True, 'description': 'Order reference'},
        ],
        'sample_variables': {'amount': '1000.00', 'reference': 'LM123'},
    },
    {
        'event_key': 'payout.success',
        'module': 'payout',
        'label': 'Payout success',
        'description': 'Bank payout completed successfully.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Payout amount'},
            {'name': 'reference', 'required': True, 'description': 'Payout reference'},
            {'name': 'transfer_mode', 'required': False, 'description': 'IMPS/NEFT/etc'},
        ],
        'sample_variables': {'amount': '500.00', 'reference': 'PTX123', 'transfer_mode': 'IMPS'},
    },
    {
        'event_key': 'payout.failed',
        'module': 'payout',
        'label': 'Payout failed',
        'description': 'Bank payout failed.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Attempted amount'},
            {'name': 'reference', 'required': True, 'description': 'Payout reference'},
            {'name': 'reason', 'required': False, 'description': 'Failure reason'},
        ],
        'sample_variables': {'amount': '500.00', 'reference': 'PTX123', 'reason': 'Insufficient balance'},
    },
    {
        'event_key': 'payout.pending',
        'module': 'payout',
        'label': 'Payout pending',
        'description': 'Optional: payout initiated, settlement pending.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Payout amount'},
            {'name': 'reference', 'required': True, 'description': 'Payout reference'},
        ],
        'sample_variables': {'amount': '500.00', 'reference': 'PTX123'},
    },
    {
        'event_key': 'bbps.payment.success',
        'module': 'bbps',
        'label': 'BBPS payment success',
        'description': 'Bill payment completed successfully.',
        'variable_schema': [
            {'name': 'biller', 'required': True, 'description': 'Biller name'},
            {'name': 'amount', 'required': True, 'description': 'Paid amount'},
            {'name': 'txn_ref', 'required': False, 'description': 'Transaction reference'},
            {'name': 'service_id', 'required': True, 'description': 'BBPS service id'},
        ],
        'sample_variables': {
            'biller': 'Electricity Co',
            'amount': '250.00',
            'txn_ref': 'TXN123',
            'service_id': 'BP123',
        },
    },
    {
        'event_key': 'bbps.payment.failed',
        'module': 'bbps',
        'label': 'BBPS payment failed',
        'description': 'Bill payment failed.',
        'variable_schema': [
            {'name': 'biller', 'required': True, 'description': 'Biller name'},
            {'name': 'amount', 'required': True, 'description': 'Attempted amount'},
            {'name': 'reason', 'required': False, 'description': 'Failure reason'},
            {'name': 'service_id', 'required': True, 'description': 'BBPS service id'},
        ],
        'sample_variables': {
            'biller': 'Electricity Co',
            'amount': '250.00',
            'reason': 'Declined',
            'service_id': 'BP123',
        },
    },
    {
        'event_key': 'bbps.payment.awaited',
        'module': 'bbps',
        'label': 'BBPS payment awaited',
        'description': 'Payment in AWAITED state; confirmation pending.',
        'variable_schema': [
            {'name': 'biller', 'required': True, 'description': 'Biller name'},
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'txn_ref', 'required': False, 'description': 'Transaction reference'},
            {'name': 'service_id', 'required': True, 'description': 'BBPS service id'},
        ],
        'sample_variables': {
            'biller': 'Electricity Co',
            'amount': '250.00',
            'txn_ref': 'TXN123',
            'service_id': 'BP123',
        },
    },
    {
        'event_key': 'bbps.payment.success_poll',
        'module': 'bbps',
        'label': 'BBPS success (status poll)',
        'description': 'Optional: success detected via status poll (same template as success).',
        'variable_schema': [
            {'name': 'biller', 'required': True, 'description': 'Biller name'},
            {'name': 'amount', 'required': True, 'description': 'Paid amount'},
            {'name': 'txn_ref', 'required': False, 'description': 'Transaction reference'},
            {'name': 'service_id', 'required': True, 'description': 'BBPS service id'},
        ],
        'sample_variables': {
            'biller': 'Electricity Co',
            'amount': '250.00',
            'txn_ref': 'TXN123',
            'service_id': 'BP123',
        },
    },
    {
        'event_key': 'onboarding.welcome',
        'module': 'onboarding',
        'label': 'Welcome SMS',
        'description': 'Future: sent after KYC + MPIN complete.',
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'User display name'},
        ],
        'sample_variables': {'name': 'Retailer'},
    },
    {
        'event_key': 'complaint.registered',
        'module': 'complaints',
        'label': 'Complaint registered',
        'description': 'Future: BBPS complaint registered confirmation.',
        'variable_schema': [
            {'name': 'txn_ref', 'required': True, 'description': 'Related transaction ref'},
            {'name': 'complaint_id', 'required': True, 'description': 'Complaint id'},
        ],
        'sample_variables': {'txn_ref': 'TXN123', 'complaint_id': 'CMP456'},
    },
]

CATALOG_EVENT_KEYS = {e['event_key'] for e in SMS_EVENT_CATALOG}

AUTH_OTP_PURPOSE_TO_EVENT = {
    'password-reset': 'auth.otp.password_reset',
    'aadhaar-verification': 'auth.otp.aadhaar_verification',
    'registration': 'auth.otp.registration',
    'mpin-reset': 'auth.otp.mpin_reset',
}
