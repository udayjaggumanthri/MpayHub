"""
BBPS (Bharat Bill Payment System) models.
"""
from django.db import models
from decimal import Decimal
from apps.core.models import BaseModel
from apps.authentication.models import User
from django.conf import settings


class Biller(BaseModel):
    """
    Biller model for BBPS.
    """
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=50, db_index=True)
    biller_id = models.CharField(max_length=100, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'biller'
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} - {self.category}"


class Bill(BaseModel):
    """
    Bill model for storing bill details.
    """
    biller = models.ForeignKey(Biller, on_delete=models.CASCADE, related_name='bills')
    customer_details = models.JSONField(default=dict)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    
    class Meta:
        db_table = 'bills'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Bill - {self.biller.name} - ₹{self.amount}"


class BillPayment(BaseModel):
    """
    Bill payment transaction model.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bill_payments',
        db_index=True
    )
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='payments', null=True, blank=True)
    biller = models.CharField(max_length=200)
    biller_id = models.CharField(max_length=100, blank=True, null=True)
    bill_type = models.CharField(max_length=50)
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    charge = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal(str(settings.BBPS_SERVICE_CHARGE)))
    total_deducted = models.DecimalField(max_digits=18, decimal_places=4)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    service_id = models.CharField(max_length=100, unique=True, db_index=True)
    request_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    failure_reason = models.TextField(blank=True, null=True)
    commission_rule_code = models.CharField(max_length=80, blank=True, default='')
    commission_rule_snapshot = models.JSONField(default=dict, blank=True)
    commission_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    
    class Meta:
        db_table = 'bill_payments'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status', 'created_at']),
            models.Index(fields=['service_id']),
        ]
    
    def __str__(self):
        return f"{self.service_id} - {self.user.user_id} - ₹{self.amount}"


class BbpsBillerMaster(BaseModel):
    """Cached BillAvenue biller (MDM) master."""

    biller_id = models.CharField(max_length=20, unique=True, db_index=True)
    biller_name = models.CharField(max_length=255, blank=True, default='')
    biller_alias_name = models.CharField(max_length=255, blank=True, default='')
    biller_category = models.CharField(max_length=120, blank=True, default='', db_index=True)
    biller_status = models.CharField(max_length=30, blank=True, default='', db_index=True)
    biller_adhoc = models.BooleanField(default=False)
    biller_coverage = models.CharField(max_length=30, blank=True, default='')
    biller_fetch_requirement = models.CharField(max_length=30, blank=True, default='')
    biller_payment_exactness = models.CharField(max_length=50, blank=True, default='')
    biller_support_bill_validation = models.CharField(max_length=30, blank=True, default='')
    support_pending_status = models.CharField(max_length=10, blank=True, default='')
    support_deemed = models.CharField(max_length=10, blank=True, default='')
    biller_timeout = models.CharField(max_length=20, blank=True, default='')
    biller_amount_options = models.CharField(max_length=100, blank=True, default='')
    recharge_amount_in_validation_request = models.CharField(max_length=30, blank=True, default='')
    plan_mdm_requirement = models.CharField(max_length=30, blank=True, default='')
    source_hash = models.CharField(max_length=128, blank=True, default='')
    source_version = models.CharField(max_length=20, blank=True, default='')
    last_synced_at = models.DateTimeField(null=True, blank=True, db_index=True)
    sync_error = models.TextField(blank=True, default='')
    is_stale = models.BooleanField(default=False, db_index=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'bbps_biller_master'
        ordering = ['biller_name']

    def __str__(self):
        return f'{self.biller_id} - {self.biller_name}'


class BbpsServiceCategory(BaseModel):
    """Canonical BBPS category catalogue managed by admin."""

    code = models.SlugField(max_length=60, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'bbps_service_category'
        ordering = ['display_order', 'name']

    def __str__(self):
        return f'{self.name} ({self.code})'


class BbpsServiceProvider(BaseModel):
    """Internal provider/operator/bank master used by discovery and routing."""

    PROVIDER_TYPE_CHOICES = [
        ('operator', 'Operator'),
        ('bank', 'Bank'),
        ('utility', 'Utility'),
        ('other', 'Other'),
    ]

    category = models.ForeignKey(
        BbpsServiceCategory, on_delete=models.CASCADE, related_name='providers'
    )
    code = models.SlugField(max_length=80, db_index=True)
    name = models.CharField(max_length=150)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_TYPE_CHOICES, default='other')
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(default=0, db_index=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'bbps_service_provider'
        ordering = ['category__display_order', 'priority', 'name']
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'code'],
                condition=models.Q(is_deleted=False),
                name='uniq_bbps_provider_code_per_category',
            )
        ]

    def __str__(self):
        return f'{self.name} ({self.category.code})'


class BbpsProviderBillerMap(BaseModel):
    """Map internal provider master entries to BillAvenue billers."""

    provider = models.ForeignKey(
        BbpsServiceProvider, on_delete=models.CASCADE, related_name='biller_maps'
    )
    biller_master = models.ForeignKey(
        BbpsBillerMaster, on_delete=models.CASCADE, related_name='provider_maps'
    )
    is_active = models.BooleanField(default=True, db_index=True)
    priority = models.PositiveIntegerField(default=0, db_index=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'bbps_provider_biller_map'
        ordering = ['provider__category__display_order', 'provider__priority', 'priority', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['provider', 'biller_master'],
                condition=models.Q(is_deleted=False),
                name='uniq_bbps_provider_biller_map',
            )
        ]


class BbpsCategoryCommissionRule(BaseModel):
    """Category-level commission policy with effective dates."""

    COMMISSION_TYPE_CHOICES = [('flat', 'Flat'), ('percentage', 'Percentage')]

    category = models.ForeignKey(
        BbpsServiceCategory, on_delete=models.CASCADE, related_name='commission_rules'
    )
    rule_code = models.CharField(max_length=80, db_index=True)
    commission_type = models.CharField(max_length=20, choices=COMMISSION_TYPE_CHOICES, default='flat')
    value = models.DecimalField(max_digits=18, decimal_places=6, default=Decimal('0'))
    min_commission = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    max_commission = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    is_active = models.BooleanField(default=True, db_index=True)
    effective_from = models.DateTimeField(null=True, blank=True, db_index=True)
    effective_to = models.DateTimeField(null=True, blank=True, db_index=True)
    notes = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'bbps_category_commission_rule'
        ordering = ['-is_active', '-effective_from', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['category', 'rule_code'],
                condition=models.Q(is_deleted=False),
                name='uniq_bbps_commission_rule_code_per_category',
            )
        ]


class BbpsCommissionAudit(BaseModel):
    """Immutable commission policy change audit."""

    rule = models.ForeignKey(
        BbpsCategoryCommissionRule, on_delete=models.CASCADE, related_name='audits'
    )
    changed_by_user_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    action = models.CharField(max_length=30, default='upsert', db_index=True)
    previous_snapshot = models.JSONField(default=dict, blank=True)
    new_snapshot = models.JSONField(default=dict, blank=True)
    reason = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'bbps_commission_audit'
        ordering = ['-created_at']


class BbpsBillerInputParam(BaseModel):
    """Input parameter definitions from biller MDM."""

    biller = models.ForeignKey(
        BbpsBillerMaster, on_delete=models.CASCADE, related_name='input_params'
    )
    param_name = models.CharField(max_length=120, db_index=True)
    data_type = models.CharField(max_length=30, blank=True, default='')
    is_optional = models.BooleanField(default=False)
    min_length = models.PositiveIntegerField(default=0)
    max_length = models.PositiveIntegerField(default=0)
    regex = models.CharField(max_length=500, blank=True, default='')
    visibility = models.BooleanField(default=True)
    default_values = models.JSONField(default=list, blank=True)
    display_order = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'bbps_biller_input_param'
        ordering = ['display_order', 'id']
        unique_together = [['biller', 'param_name']]


class BbpsBillerPaymentModeLimit(BaseModel):
    """Payment modes and amount limits supported by a biller."""

    biller = models.ForeignKey(BbpsBillerMaster, on_delete=models.CASCADE, related_name='payment_modes')
    payment_mode = models.CharField(max_length=50, db_index=True)
    min_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    max_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'bbps_biller_payment_mode_limit'
        ordering = ['payment_mode']
        unique_together = [['biller', 'payment_mode']]


class BbpsBillerPaymentChannelLimit(BaseModel):
    """Payment channels and amount limits supported by a biller."""

    biller = models.ForeignKey(
        BbpsBillerMaster, on_delete=models.CASCADE, related_name='payment_channels'
    )
    payment_channel = models.CharField(max_length=20, db_index=True)
    min_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    max_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'bbps_biller_payment_channel_limit'
        ordering = ['payment_channel']
        unique_together = [['biller', 'payment_channel']]


class BbpsBillerAdditionalInfoSchema(BaseModel):
    """Additional info schema received for payment or plan-related tags."""

    biller = models.ForeignKey(
        BbpsBillerMaster, on_delete=models.CASCADE, related_name='additional_info_schema'
    )
    info_group = models.CharField(max_length=40, default='additional')
    info_name = models.CharField(max_length=120)
    data_type = models.CharField(max_length=30, blank=True, default='')
    is_optional = models.BooleanField(default=True)

    class Meta:
        db_table = 'bbps_biller_additional_info_schema'
        ordering = ['info_group', 'info_name']


class BbpsBillerPlanMeta(BaseModel):
    """Plan metadata and response parameters for billers supporting plan pull/plan mdm."""

    biller = models.ForeignKey(BbpsBillerMaster, on_delete=models.CASCADE, related_name='plan_meta')
    plan_id = models.CharField(max_length=60, blank=True, default='')
    category_type = models.CharField(max_length=80, blank=True, default='')
    category_sub_type = models.CharField(max_length=80, blank=True, default='')
    amount_in_rupees = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    plan_desc = models.TextField(blank=True, default='')
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, blank=True, default='')
    plan_additional_info = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'bbps_biller_plan_meta'
        ordering = ['-updated_at']


class BbpsBillerCcf1Config(BaseModel):
    """CCF1 fee metadata sent in MDM response."""

    biller = models.ForeignKey(BbpsBillerMaster, on_delete=models.CASCADE, related_name='ccf1_configs')
    fee_code = models.CharField(max_length=20, blank=True, default='CCF1')
    fee_direction = models.CharField(max_length=20, blank=True, default='')
    flat_fee = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    percent_fee = models.DecimalField(max_digits=9, decimal_places=4, default=Decimal('0'))
    fee_min_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    fee_max_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))

    class Meta:
        db_table = 'bbps_biller_ccf1_config'


class BbpsApiAuditLog(BaseModel):
    """Redacted API-level request/response telemetry."""

    endpoint_name = models.CharField(max_length=80, db_index=True)
    request_id = models.CharField(max_length=50, blank=True, default='', db_index=True)
    service_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    status_code = models.CharField(max_length=20, blank=True, default='')
    latency_ms = models.PositiveIntegerField(default=0)
    success = models.BooleanField(default=False, db_index=True)
    request_meta = models.JSONField(default=dict, blank=True)
    response_meta = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'bbps_api_audit_log'
        ordering = ['-created_at']


class BbpsFetchSession(BaseModel):
    """Persisted bill fetch snapshot used later for validation/payment replay safety."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bbps_fetch_sessions')
    biller_master = models.ForeignKey(
        BbpsBillerMaster, null=True, blank=True, on_delete=models.SET_NULL, related_name='fetch_sessions'
    )
    request_id = models.CharField(max_length=50, blank=True, default='', db_index=True)
    service_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    input_params = models.JSONField(default=dict, blank=True)
    biller_response = models.JSONField(default=dict, blank=True)
    additional_info = models.JSONField(default=dict, blank=True)
    amount_paise = models.BigIntegerField(default=0)
    raw_response = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, default='FETCHED', db_index=True)

    class Meta:
        db_table = 'bbps_fetch_session'
        ordering = ['-created_at']


class BbpsPaymentAttempt(BaseModel):
    """Idempotent payment attempt lifecycle for BBPS payment orchestration."""

    STATUS_CHOICES = [
        ('CREATED', 'Created'),
        ('FETCHED', 'Fetched'),
        ('VALIDATED', 'Validated'),
        ('PAY_INITIATED', 'Payment Initiated'),
        ('AWAITED', 'Awaited'),
        ('SUCCESS', 'Success'),
        ('FAILED', 'Failed'),
        ('REFUNDED', 'Refunded'),
        ('REVERSED', 'Reversed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bbps_payment_attempts')
    bill_payment = models.ForeignKey(
        BillPayment, null=True, blank=True, on_delete=models.SET_NULL, related_name='attempts'
    )
    fetch_session = models.ForeignKey(
        BbpsFetchSession, null=True, blank=True, on_delete=models.SET_NULL, related_name='attempts'
    )
    idempotency_key = models.CharField(max_length=200, db_index=True)
    request_id = models.CharField(max_length=50, blank=True, default='', db_index=True)
    service_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    biller_id = models.CharField(max_length=20, blank=True, default='', db_index=True)
    amount_paise = models.BigIntegerField(default=0)
    payment_mode = models.CharField(max_length=50, blank=True, default='')
    payment_channel = models.CharField(max_length=20, blank=True, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='CREATED', db_index=True)
    txn_ref_id = models.CharField(max_length=40, blank=True, default='', db_index=True)
    approval_ref_number = models.CharField(max_length=60, blank=True, default='')
    last_error_code = models.CharField(max_length=50, blank=True, default='')
    last_error_message = models.TextField(blank=True, default='')
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    commission_rule_code = models.CharField(max_length=80, blank=True, default='')
    commission_rule_snapshot = models.JSONField(default=dict, blank=True)
    commission_amount = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'bbps_payment_attempt'
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['idempotency_key'],
                condition=models.Q(is_deleted=False),
                name='uniq_bbps_payment_attempt_idempotency',
            )
        ]


class BbpsStatusPollLog(BaseModel):
    """Status poll attempts against BillAvenue transaction status API."""

    attempt = models.ForeignKey(
        BbpsPaymentAttempt, on_delete=models.CASCADE, related_name='status_polls'
    )
    track_type = models.CharField(max_length=20, default='REQUEST_ID')
    track_value = models.CharField(max_length=80, blank=True, default='')
    response_code = models.CharField(max_length=20, blank=True, default='')
    txn_status = models.CharField(max_length=30, blank=True, default='', db_index=True)
    request_payload = models.JSONField(default=dict, blank=True)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'bbps_status_poll_log'
        ordering = ['-created_at']


class BbpsComplaint(BaseModel):
    """Complaint registry and tracking information."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bbps_complaints')
    attempt = models.ForeignKey(
        BbpsPaymentAttempt, null=True, blank=True, on_delete=models.SET_NULL, related_name='complaints'
    )
    txn_ref_id = models.CharField(max_length=40, blank=True, default='', db_index=True)
    complaint_id = models.CharField(max_length=60, blank=True, default='', db_index=True)
    complaint_desc = models.CharField(max_length=255, blank=True, default='')
    complaint_disposition = models.CharField(max_length=255, blank=True, default='')
    complaint_status = models.CharField(max_length=40, blank=True, default='', db_index=True)
    response_code = models.CharField(max_length=20, blank=True, default='')
    response_reason = models.CharField(max_length=100, blank=True, default='')
    raw_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'bbps_complaint'
        ordering = ['-created_at']


class BbpsComplaintEvent(BaseModel):
    """Complaint timeline events from track calls."""

    complaint = models.ForeignKey(
        BbpsComplaint, on_delete=models.CASCADE, related_name='events'
    )
    complaint_status = models.CharField(max_length=40, blank=True, default='')
    remarks = models.TextField(blank=True, default='')
    response_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'bbps_complaint_event'
        ordering = ['-created_at']


class BbpsPlanPullRun(BaseModel):
    """Plan pull snapshots and run metadata."""

    response_code = models.CharField(max_length=20, blank=True, default='')
    requested_biller_ids = models.JSONField(default=list, blank=True)
    plan_count = models.PositiveIntegerField(default=0)
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'bbps_plan_pull_run'
        ordering = ['-created_at']


class BbpsDepositEnquirySnapshot(BaseModel):
    """Deposit enquiry snapshots for admin operations panel."""

    request_id = models.CharField(max_length=50, blank=True, default='', db_index=True)
    from_date = models.CharField(max_length=25, blank=True, default='')
    to_date = models.CharField(max_length=25, blank=True, default='')
    trans_type = models.CharField(max_length=10, blank=True, default='')
    current_balance = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal('0'))
    currency = models.CharField(max_length=10, blank=True, default='INR')
    response_payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'bbps_deposit_enquiry_snapshot'
        ordering = ['-created_at']


class BbpsPushWebhookEvent(BaseModel):
    """Inbound push/callback events from BillAvenue."""

    request_id = models.CharField(max_length=50, blank=True, default='', db_index=True)
    txn_ref_id = models.CharField(max_length=40, blank=True, default='', db_index=True)
    event_type = models.CharField(max_length=30, blank=True, default='PAYMENT_STATUS', db_index=True)
    response_code = models.CharField(max_length=20, blank=True, default='')
    response_reason = models.CharField(max_length=100, blank=True, default='')
    payload = models.JSONField(default=dict, blank=True)
    processed = models.BooleanField(default=False, db_index=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    processing_error = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'bbps_push_webhook_event'
        ordering = ['-created_at']
