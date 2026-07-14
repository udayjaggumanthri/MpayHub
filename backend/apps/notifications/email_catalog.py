"""
Email event catalog — event_key values are code-defined; admin can only enable/configure existing keys.
"""

EMAIL_EVENT_CATALOG = [
    {
        'event_key': 'auth.otp.password_reset',
        'module': 'auth',
        'label': 'Password reset OTP (email)',
        'description': 'OTP sent to registered email when user chooses email channel for password reset.',
        'variable_schema': [
            {'name': 'otp', 'required': True, 'description': 'OTP code'},
            {'name': 'expiry_minutes', 'required': True, 'description': 'OTP validity in minutes'},
        ],
        'sample_variables': {'otp': '123456', 'expiry_minutes': '10'},
        'default_subject': 'mPayhub password reset verification code',
        'default_body_html': (
            '<p>Your password reset verification code is: <strong>{{otp}}</strong></p>'
            '<p>This code expires in {{expiry_minutes}} minutes.</p>'
            '<p>If you did not request this, ignore this email.</p>'
        ),
        'default_body_plain': (
            'Your password reset verification code is: {{otp}}\n\n'
            'This code expires in {{expiry_minutes}} minutes.\n\n'
            'If you did not request this, ignore this email.'
        ),
    },
    {
        'event_key': 'auth.otp.mpin_reset',
        'module': 'auth',
        'label': 'MPIN reset OTP (email)',
        'description': 'OTP sent to registered email when user chooses email channel for MPIN reset.',
        'variable_schema': [
            {'name': 'otp', 'required': True, 'description': 'OTP code'},
            {'name': 'expiry_minutes', 'required': True, 'description': 'OTP validity in minutes'},
        ],
        'sample_variables': {'otp': '123456', 'expiry_minutes': '10'},
        'default_subject': 'mPayhub MPIN reset verification code',
        'default_body_html': (
            '<p>Your MPIN reset verification code is: <strong>{{otp}}</strong></p>'
            '<p>This code expires in {{expiry_minutes}} minutes.</p>'
            '<p>If you did not request this, ignore this email.</p>'
        ),
        'default_body_plain': (
            'Your MPIN reset verification code is: {{otp}}\n\n'
            'This code expires in {{expiry_minutes}} minutes.\n\n'
            'If you did not request this, ignore this email.'
        ),
    },
    {
        'event_key': 'onboarding.user_created',
        'module': 'onboarding',
        'label': 'New user credentials',
        'description': 'Sent when an admin creates a user with a unique temporary password.',
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'Display name'},
            {'name': 'user_id', 'required': True, 'description': 'User ID'},
            {'name': 'phone', 'required': True, 'description': 'Login phone'},
            {'name': 'email', 'required': True, 'description': 'Email address'},
            {'name': 'temporary_password', 'required': True, 'description': 'Initial password'},
            {'name': 'role', 'required': True, 'description': 'User role'},
            {'name': 'login_url', 'required': False, 'description': 'Portal login URL'},
        ],
        'sample_variables': {
            'name': 'Retailer Name',
            'user_id': 'RTL001',
            'phone': '9876543210',
            'email': 'user@example.com',
            'temporary_password': '********',
            'role': 'Retailer',
            'login_url': 'https://partner.mpayhub.in',
        },
        'default_subject': 'Welcome to mPayhub — your account credentials',
        'default_body_html': (
            '<p>Hello {{name}},</p>'
            '<p>Your mPayhub account has been created.</p>'
            '<ul>'
            '<li><strong>User ID:</strong> {{user_id}}</li>'
            '<li><strong>Phone:</strong> {{phone}}</li>'
            '<li><strong>Email:</strong> {{email}}</li>'
            '<li><strong>Role:</strong> {{role}}</li>'
            '<li><strong>Temporary password:</strong> {{temporary_password}}</li>'
            '</ul>'
            '<p>Log in at <a href="{{login_url}}">{{login_url}}</a> using your phone number and the temporary password above.</p>'
            '<p><strong>On first login you must reset your password</strong> using a one-time code (OTP) sent to your mobile or email.</p>'
            '<p>After that, complete KYC and MPIN setup.</p>'
        ),
        'default_body_plain': (
            'Hello {{name}},\n\n'
            'Your mPayhub account has been created.\n'
            'User ID: {{user_id}}\n'
            'Phone: {{phone}}\n'
            'Email: {{email}}\n'
            'Role: {{role}}\n'
            'Temporary password: {{temporary_password}}\n\n'
            'Log in at {{login_url}} using your phone and this temporary password.\n'
            'On first login you must reset your password via OTP (SMS or email), then complete KYC and MPIN setup.\n'
        ),
    },
    {
        'event_key': 'kyc.submitted.for_approval',
        'module': 'kyc',
        'label': 'KYC submitted for Admin approval',
        'description': 'Sent when PAN and Aadhaar are verified and KYC awaits Admin review.',
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'Display name'},
            {'name': 'user_id', 'required': True, 'description': 'User ID'},
            {'name': 'pan_masked', 'required': False, 'description': 'Masked PAN'},
            {'name': 'verification_status', 'required': True, 'description': 'KYC status'},
        ],
        'sample_variables': {
            'name': 'Retailer Name',
            'user_id': 'RTL001',
            'pan_masked': 'ABCDE****F',
            'verification_status': 'awaiting_approval',
        },
        'default_subject': 'mPayhub — KYC submitted for review',
        'default_body_html': (
            '<p>Hello {{name}},</p>'
            '<p>Your PAN and Aadhaar verification is complete. Your KYC is now '
            '<strong>awaiting Admin approval</strong> before your account becomes active.</p>'
            '<p>User ID: {{user_id}}</p>'
            '<p>PAN: {{pan_masked}}</p>'
            '<p>You will receive another email once an administrator reviews your KYC.</p>'
        ),
        'default_body_plain': (
            'Hello {{name}},\n\n'
            'Your PAN and Aadhaar verification is complete. Your KYC is awaiting Admin approval '
            'before your account becomes active.\n'
            'User ID: {{user_id}}\n'
            'PAN: {{pan_masked}}\n'
        ),
    },
    {
        'event_key': 'kyc.verification.complete',
        'module': 'kyc',
        'label': 'KYC verification complete',
        'description': 'Sent when an Admin approves KYC after provider verification.',
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'Display name'},
            {'name': 'user_id', 'required': True, 'description': 'User ID'},
            {'name': 'pan_masked', 'required': False, 'description': 'Masked PAN'},
            {'name': 'verification_status', 'required': True, 'description': 'KYC status'},
        ],
        'sample_variables': {
            'name': 'Retailer Name',
            'user_id': 'RTL001',
            'pan_masked': 'ABCDE****F',
            'verification_status': 'verified',
        },
        'default_subject': 'mPayhub — KYC approved',
        'default_body_html': (
            '<p>Hello {{name}},</p>'
            '<p>Your KYC has been <strong>approved</strong> by an administrator '
            '(status: <strong>{{verification_status}}</strong>).</p>'
            '<p>User ID: {{user_id}}</p>'
            '<p>PAN: {{pan_masked}}</p>'
            '<p>Please complete MPIN setup (if not already done) to start using mPayhub services.</p>'
        ),
        'default_body_plain': (
            'Hello {{name}},\n\n'
            'Your KYC has been approved by an administrator (status: {{verification_status}}).\n'
            'User ID: {{user_id}}\n'
            'PAN: {{pan_masked}}\n'
            'Please complete MPIN setup if needed to start using mPayhub services.\n'
        ),
    },
    {
        'event_key': 'kyc.verification.rejected',
        'module': 'kyc',
        'label': 'KYC verification rejected',
        'description': 'Sent when an Admin rejects KYC after review.',
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'Display name'},
            {'name': 'user_id', 'required': True, 'description': 'User ID'},
            {'name': 'pan_masked', 'required': False, 'description': 'Masked PAN'},
            {'name': 'verification_status', 'required': True, 'description': 'KYC status'},
            {'name': 'reason', 'required': True, 'description': 'Rejection reason'},
        ],
        'sample_variables': {
            'name': 'Retailer Name',
            'user_id': 'RTL001',
            'pan_masked': 'ABCDE****F',
            'verification_status': 'rejected',
            'reason': 'Document mismatch — please contact support.',
        },
        'default_subject': 'mPayhub — KYC requires attention',
        'default_body_html': (
            '<p>Hello {{name}},</p>'
            '<p>Your KYC review could not be approved (status: <strong>{{verification_status}}</strong>).</p>'
            '<p>Reason: {{reason}}</p>'
            '<p>User ID: {{user_id}}</p>'
            '<p>PAN: {{pan_masked}}</p>'
            '<p>Please contact your administrator or support for next steps.</p>'
        ),
        'default_body_plain': (
            'Hello {{name}},\n\n'
            'Your KYC review could not be approved (status: {{verification_status}}).\n'
            'Reason: {{reason}}\n'
            'User ID: {{user_id}}\n'
            'PAN: {{pan_masked}}\n'
        ),
    },
    {
        'event_key': 'payin.success',
        'module': 'payin',
        'label': 'Pay-in success',
        'description': 'Load money / pay-in credited successfully.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'reference', 'required': True, 'description': 'Reference'},
            {'name': 'transaction_id', 'required': True, 'description': 'Transaction ID'},
        ],
        'sample_variables': {'amount': '1000.00', 'reference': 'GTX123', 'transaction_id': 'LM123'},
        'default_subject': 'mPayhub — Pay-in successful',
        'default_body_html': (
            '<p>Your pay-in of <strong>₹{{amount}}</strong> was successful.</p>'
            '<p>Reference: {{reference}}</p>'
            '<p>Transaction ID: {{transaction_id}}</p>'
        ),
        'default_body_plain': (
            'Your pay-in of Rs {{amount}} was successful.\n'
            'Reference: {{reference}}\n'
            'Transaction ID: {{transaction_id}}'
        ),
    },
    {
        'event_key': 'payin.failed',
        'module': 'payin',
        'label': 'Pay-in failed',
        'description': 'Load money attempt failed.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'reference', 'required': True, 'description': 'Reference'},
            {'name': 'reason', 'required': False, 'description': 'Failure reason'},
        ],
        'sample_variables': {'amount': '1000.00', 'reference': 'LM123', 'reason': 'Payment failed'},
        'default_subject': 'mPayhub — Pay-in failed',
        'default_body_html': (
            '<p>Your pay-in of <strong>₹{{amount}}</strong> could not be completed.</p>'
            '<p>Reference: {{reference}}</p>'
            '<p>Reason: {{reason}}</p>'
        ),
        'default_body_plain': (
            'Your pay-in of Rs {{amount}} could not be completed.\n'
            'Reference: {{reference}}\n'
            'Reason: {{reason}}'
        ),
    },
    {
        'event_key': 'payin.pending',
        'module': 'payin',
        'label': 'Pay-in pending',
        'description': 'Optional: pay-in order pending confirmation.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'reference', 'required': True, 'description': 'Reference'},
        ],
        'sample_variables': {'amount': '1000.00', 'reference': 'LM123'},
        'default_subject': 'mPayhub — Pay-in pending',
        'default_body_html': (
            '<p>Your pay-in of <strong>₹{{amount}}</strong> is pending confirmation.</p>'
            '<p>Reference: {{reference}}</p>'
        ),
        'default_body_plain': (
            'Your pay-in of Rs {{amount}} is pending confirmation.\n'
            'Reference: {{reference}}'
        ),
    },
    {
        'event_key': 'payout.success',
        'module': 'payout',
        'label': 'Payout success',
        'description': 'Bank payout completed successfully.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'reference', 'required': True, 'description': 'Reference'},
            {'name': 'transfer_mode', 'required': False, 'description': 'Transfer mode'},
        ],
        'sample_variables': {'amount': '500.00', 'reference': 'PTX123', 'transfer_mode': 'IMPS'},
        'default_subject': 'mPayhub — Payout successful',
        'default_body_html': (
            '<p>Your payout of <strong>₹{{amount}}</strong> via {{transfer_mode}} was successful.</p>'
            '<p>Reference: {{reference}}</p>'
        ),
        'default_body_plain': (
            'Your payout of Rs {{amount}} via {{transfer_mode}} was successful.\n'
            'Reference: {{reference}}'
        ),
    },
    {
        'event_key': 'payout.failed',
        'module': 'payout',
        'label': 'Payout failed',
        'description': 'Bank payout failed.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'reference', 'required': True, 'description': 'Reference'},
            {'name': 'reason', 'required': False, 'description': 'Failure reason'},
        ],
        'sample_variables': {'amount': '500.00', 'reference': 'PTX123', 'reason': 'Insufficient balance'},
        'default_subject': 'mPayhub — Payout failed',
        'default_body_html': (
            '<p>Your payout of <strong>₹{{amount}}</strong> failed.</p>'
            '<p>Reference: {{reference}}</p>'
            '<p>Reason: {{reason}}</p>'
        ),
        'default_body_plain': (
            'Your payout of Rs {{amount}} failed.\n'
            'Reference: {{reference}}\n'
            'Reason: {{reason}}'
        ),
    },
    {
        'event_key': 'payout.pending',
        'module': 'payout',
        'label': 'Payout pending',
        'description': 'Optional: payout initiated, settlement pending.',
        'variable_schema': [
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'reference', 'required': True, 'description': 'Reference'},
        ],
        'sample_variables': {'amount': '500.00', 'reference': 'PTX123'},
        'default_subject': 'mPayhub — Payout pending',
        'default_body_html': (
            '<p>Your payout of <strong>₹{{amount}}</strong> is being processed.</p>'
            '<p>Reference: {{reference}}</p>'
        ),
        'default_body_plain': (
            'Your payout of Rs {{amount}} is being processed.\n'
            'Reference: {{reference}}'
        ),
    },
    {
        'event_key': 'bbps.payment.success',
        'module': 'bbps',
        'label': 'BBPS payment success',
        'description': 'Bill payment completed successfully.',
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'Account holder name'},
            {'name': 'service', 'required': True, 'description': 'Service category (e.g. Mobile Postpaid)'},
            {'name': 'consumer_id', 'required': False, 'description': 'Consumer ID for the service'},
            {'name': 'b_connect_txn_id', 'required': False, 'description': 'B-Connect transaction ID'},
            {'name': 'status', 'required': True, 'description': 'Payment status (e.g. Success)'},
            {'name': 'biller', 'required': True, 'description': 'Biller name'},
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'txn_ref', 'required': False, 'description': 'Transaction reference (legacy)'},
            {'name': 'service_id', 'required': True, 'description': 'Service ID'},
        ],
        'sample_variables': {
            'name': 'Retailer Name',
            'service': 'Mobile Postpaid',
            'consumer_id': '9876543210',
            'b_connect_txn_id': 'CC1234567890123456789012345678901234',
            'status': 'Success',
            'biller': 'Airtel Postpaid',
            'amount': '250.00',
            'txn_ref': 'CC1234567890123456789012345678901234',
            'service_id': 'BP123',
        },
        'default_subject': 'mPayhub — Bill payment successful',
        'default_body_html': (
            '<p>Hello {{name}},</p>'
            '<p>Your bill payment was completed successfully.</p>'
            '<ul>'
            '<li><strong>Service:</strong> {{service}}</li>'
            '<li><strong>Consumer ID:</strong> {{consumer_id}}</li>'
            '<li><strong>B-Connect Txn ID:</strong> {{b_connect_txn_id}}</li>'
            '<li><strong>Status:</strong> {{status}}</li>'
            '<li><strong>Biller:</strong> {{biller}}</li>'
            '<li><strong>Amount:</strong> ₹{{amount}}</li>'
            '</ul>'
        ),
        'default_body_plain': (
            'Hello {{name}},\n\n'
            'Your bill payment was completed successfully.\n'
            'Service: {{service}}\n'
            'Consumer ID: {{consumer_id}}\n'
            'B-Connect Txn ID: {{b_connect_txn_id}}\n'
            'Status: {{status}}\n'
            'Biller: {{biller}}\n'
            'Amount: Rs {{amount}}\n'
        ),
    },
    {
        'event_key': 'bbps.payment.failed',
        'module': 'bbps',
        'label': 'BBPS payment failed',
        'description': 'Bill payment failed.',
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'Account holder name'},
            {'name': 'service', 'required': True, 'description': 'Service category (e.g. Mobile Postpaid)'},
            {'name': 'consumer_id', 'required': False, 'description': 'Consumer ID for the service'},
            {'name': 'b_connect_txn_id', 'required': False, 'description': 'B-Connect transaction ID'},
            {'name': 'status', 'required': True, 'description': 'Payment status (e.g. Failed)'},
            {'name': 'biller', 'required': True, 'description': 'Biller name'},
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'reason', 'required': False, 'description': 'Failure reason'},
            {'name': 'service_id', 'required': True, 'description': 'Service ID'},
        ],
        'sample_variables': {
            'name': 'Retailer Name',
            'service': 'Mobile Postpaid',
            'consumer_id': '9876543210',
            'b_connect_txn_id': '',
            'status': 'Failed',
            'biller': 'Airtel Postpaid',
            'amount': '250.00',
            'reason': 'Declined by biller',
            'service_id': 'BP123',
        },
        'default_subject': 'mPayhub — Bill payment failed',
        'default_body_html': (
            '<p>Hello {{name}},</p>'
            '<p>Your bill payment could not be completed.</p>'
            '<ul>'
            '<li><strong>Service:</strong> {{service}}</li>'
            '<li><strong>Consumer ID:</strong> {{consumer_id}}</li>'
            '<li><strong>B-Connect Txn ID:</strong> {{b_connect_txn_id}}</li>'
            '<li><strong>Status:</strong> {{status}}</li>'
            '<li><strong>Biller:</strong> {{biller}}</li>'
            '<li><strong>Amount:</strong> ₹{{amount}}</li>'
            '<li><strong>Reason:</strong> {{reason}}</li>'
            '</ul>'
        ),
        'default_body_plain': (
            'Hello {{name}},\n\n'
            'Your bill payment could not be completed.\n'
            'Service: {{service}}\n'
            'Consumer ID: {{consumer_id}}\n'
            'B-Connect Txn ID: {{b_connect_txn_id}}\n'
            'Status: {{status}}\n'
            'Biller: {{biller}}\n'
            'Amount: Rs {{amount}}\n'
            'Reason: {{reason}}\n'
        ),
    },
    {
        'event_key': 'bbps.payment.awaited',
        'module': 'bbps',
        'label': 'BBPS payment awaited',
        'description': 'Payment in AWAITED state.',
        'variable_schema': [
            {'name': 'name', 'required': True, 'description': 'Account holder name'},
            {'name': 'service', 'required': True, 'description': 'Service category (e.g. Mobile Postpaid)'},
            {'name': 'consumer_id', 'required': False, 'description': 'Consumer ID for the service'},
            {'name': 'b_connect_txn_id', 'required': False, 'description': 'B-Connect transaction ID'},
            {'name': 'status', 'required': True, 'description': 'Payment status (e.g. Pending)'},
            {'name': 'biller', 'required': True, 'description': 'Biller name'},
            {'name': 'amount', 'required': True, 'description': 'Amount'},
            {'name': 'txn_ref', 'required': False, 'description': 'Transaction reference (legacy)'},
            {'name': 'service_id', 'required': True, 'description': 'Service ID'},
        ],
        'sample_variables': {
            'name': 'Retailer Name',
            'service': 'Mobile Postpaid',
            'consumer_id': '9876543210',
            'b_connect_txn_id': 'CC1234567890123456789012345678901234',
            'status': 'Pending',
            'biller': 'Airtel Postpaid',
            'amount': '250.00',
            'txn_ref': 'CC1234567890123456789012345678901234',
            'service_id': 'BP123',
        },
        'default_subject': 'mPayhub — Bill payment pending',
        'default_body_html': (
            '<p>Hello {{name}},</p>'
            '<p>Your bill payment is pending confirmation.</p>'
            '<ul>'
            '<li><strong>Service:</strong> {{service}}</li>'
            '<li><strong>Consumer ID:</strong> {{consumer_id}}</li>'
            '<li><strong>B-Connect Txn ID:</strong> {{b_connect_txn_id}}</li>'
            '<li><strong>Status:</strong> {{status}}</li>'
            '<li><strong>Biller:</strong> {{biller}}</li>'
            '<li><strong>Amount:</strong> ₹{{amount}}</li>'
            '</ul>'
        ),
        'default_body_plain': (
            'Hello {{name}},\n\n'
            'Your bill payment is pending confirmation.\n'
            'Service: {{service}}\n'
            'Consumer ID: {{consumer_id}}\n'
            'B-Connect Txn ID: {{b_connect_txn_id}}\n'
            'Status: {{status}}\n'
            'Biller: {{biller}}\n'
            'Amount: Rs {{amount}}\n'
        ),
    },
    {
        'event_key': 'complaint.registered',
        'module': 'complaints',
        'label': 'BBPS complaint registered',
        'description': 'Complaint registered with BillAvenue.',
        'variable_schema': [
            {'name': 'complaint_id', 'required': True, 'description': 'Complaint ID'},
            {'name': 'txn_ref', 'required': True, 'description': 'Transaction reference'},
            {'name': 'disposition', 'required': True, 'description': 'Complaint disposition'},
            {'name': 'status', 'required': True, 'description': 'Complaint status'},
        ],
        'sample_variables': {
            'complaint_id': 'CMP456',
            'txn_ref': 'TXN123',
            'disposition': 'Transaction',
            'status': 'ASSIGNED',
        },
        'default_subject': 'mPayhub — BBPS complaint registered',
        'default_body_html': (
            '<p>Your BBPS complaint has been registered.</p>'
            '<p><strong>Complaint ID:</strong> {{complaint_id}}</p>'
            '<p><strong>Transaction ref:</strong> {{txn_ref}}</p>'
            '<p><strong>Disposition:</strong> {{disposition}}</p>'
            '<p><strong>Status:</strong> {{status}}</p>'
        ),
        'default_body_plain': (
            'Your BBPS complaint has been registered.\n'
            'Complaint ID: {{complaint_id}}\n'
            'Transaction ref: {{txn_ref}}\n'
            'Disposition: {{disposition}}\n'
            'Status: {{status}}'
        ),
    },
]

EMAIL_CATALOG_EVENT_KEYS = {e['event_key'] for e in EMAIL_EVENT_CATALOG}
