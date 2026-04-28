"""BBPS adapter over BillAvenue client (live UAT/PROD only)."""
from decimal import Decimal

from apps.integrations.base import BaseIntegration
from apps.integrations.billavenue.client import BillAvenueClient
from apps.integrations.billavenue.errors import BillAvenueClientError, BillAvenueValidationError
from apps.integrations.models import BillAvenueAgentProfile, BillAvenueConfig


class BBPSClient(BaseIntegration):
    """
    BBPS API client for bill fetching and payment processing.
    """
    
    def __init__(self):
        self.config = None
        self.client = None
        super().__init__()
    
    def _load_config(self):
        """Load BillAvenue admin config if available."""
        self.config = BillAvenueConfig.objects.filter(
            is_active=True,
            enabled=True,
            is_deleted=False,
            mode__in=['uat', 'prod'],
            base_url__isnull=False,
        ).first()
        if self.config and str(self.config.base_url or '').strip():
            self.client = BillAvenueClient(self.config)

    def is_available(self):
        """True when an active enabled UAT/PROD BillAvenue config exists and client is ready."""
        return self.client is not None

    def _require_live_client(self) -> BillAvenueClient:
        if not self.client:
            raise BillAvenueClientError(
                'BillAvenue live configuration missing. Configure active enabled UAT/PROD config in Admin.'
            )
        return self.client
    
    def handle_error(self, error):
        """Handle BBPS service errors."""
        print(f'BBPS Service Error: {error}')

    def _default_agent_id(self) -> str:
        if not self.config:
            return ''
        prof = (
            BillAvenueAgentProfile.objects.filter(
                config=self.config,
                is_deleted=False,
                enabled=True,
            )
            .order_by('name')
            .first()
        )
        return str(prof.agent_id).strip() if prof else ''
    
    def fetch_bill(self, biller_id, category, **kwargs):
        """
        Fetch bill details from BBPS.
        
        Args:
            biller_id: Biller ID
            category: Bill category
            **kwargs: Category-specific parameters
        
        Returns:
            dict with bill details
        """
        client = self._require_live_client()
        try:
            payload = {
                'agentId': kwargs.get('agent_id', '') or self._default_agent_id(),
                'billerAdhoc': bool(kwargs.get('biller_adhoc', False)),
                'agentDeviceInfo': kwargs.get('agentDeviceInfo', {}),
                'customerInfo': kwargs.get('customerInfo', {}),
                'billerId': biller_id,
                'inputParams': {'input': kwargs.get('input', [])},
            }
            if not payload['agentId']:
                raise BillAvenueValidationError('agentId is required for bill fetch.')
            out = client.bill_fetch(payload)
            normalized = out.normalized
            bill_response = normalized.get('billerResponse') or normalized.get('billFetchResponse', {}).get('billerResponse', {})
            amount_paise = (
                bill_response.get('billAmount')
                or normalized.get('billAmount')
                or 0
            )
            amount = Decimal(str(amount_paise or 0)) / Decimal('100')
            return {
                'amount': amount,
                'due_date': bill_response.get('dueDate'),
                'customer_details': kwargs,
                'raw': normalized,
                'request_id': out.request_id,
                'response_code': out.response_code,
            }
        except Exception as exc:
            self.handle_error(exc)
            raise BillAvenueClientError(str(exc)) from exc
    
    def process_payment(self, service_id, request_id, amount, bill_data):
        """
        Process bill payment via BBPS.
        
        Args:
            service_id: Service ID
            request_id: Request ID
            amount: Payment amount
            bill_data: Bill data
        
        Returns:
            dict with payment result
        """
        client = self._require_live_client()
        try:
            payload = bill_data.get('bill_payment_payload') or {}
            if not payload:
                payload = self._build_bill_payment_payload(
                    service_id=service_id,
                    request_id=request_id,
                    amount=amount,
                    bill_data=bill_data,
                )
            out = client.bill_pay(payload, request_id=request_id or None)
            normalized = out.normalized
            body = normalized.get('ExtBillPayResponse') if 'ExtBillPayResponse' in normalized else normalized
            txn_type = str(body.get('txnRespType') or '').upper()
            if 'FORWARD' in txn_type:
                return {
                    'status': 'SUCCESS',
                    'message': body.get('responseReason') or 'Payment processed successfully',
                    'transaction_id': body.get('txnRefId') or service_id,
                    'txn_ref_id': body.get('txnRefId') or '',
                    'approval_ref_number': body.get('approvalRefNumber') or '',
                    'response_payload': normalized,
                }
            if 'AWAIT' in txn_type:
                return {
                    'status': 'AWAITED',
                    'message': body.get('responseReason') or 'Payment awaiting final status',
                    'transaction_id': body.get('txnRefId') or service_id,
                    'txn_ref_id': body.get('txnRefId') or '',
                    'approval_ref_number': body.get('approvalRefNumber') or '',
                    'response_payload': normalized,
                }
            return {
                'status': 'FAILED',
                'message': body.get('responseReason') or 'Payment failed',
                'transaction_id': service_id,
                'response_payload': normalized,
            }
        except BillAvenueClientError as e:
            self.handle_error(e)
            return {'status': 'FAILED', 'message': str(e)}
        except Exception as e:
            self.handle_error(e)
            return {
                'status': 'FAILED',
                'message': str(e)
            }

    def _build_bill_payment_payload(self, *, service_id, request_id, amount, bill_data: dict) -> dict:
        biller_id = str(bill_data.get('biller_id') or '').strip()
        if not biller_id:
            raise BillAvenueValidationError('biller_id is required for live BillAvenue payment.')
        input_params = bill_data.get('input_params') or []
        if not isinstance(input_params, list):
            raise BillAvenueValidationError('input_params must be a list for live BillAvenue payment.')
        customer_info = bill_data.get('customer_info') or {}
        if not isinstance(customer_info, dict):
            raise BillAvenueValidationError('customer_info must be an object for live BillAvenue payment.')
        amount_paise = int((Decimal(str(amount)) * Decimal('100')).to_integral_value())
        payment_method = bill_data.get('payment_method_payload')
        if not isinstance(payment_method, dict):
            payment_method = {
                'paymentMode': str(bill_data.get('payment_mode') or ''),
                'quickPay': 'N',
                'splitPay': 'N',
            }
        return {
            'agentId': str(bill_data.get('agent_id') or self._default_agent_id()),
            'billerId': biller_id,
            'customerInfo': customer_info,
            'inputParams': {'input': input_params},
            'agentDeviceInfo': bill_data.get('agent_device_info') or {},
            'billerAdhoc': bool(bill_data.get('biller_adhoc', False)),
            'initChannel': str(bill_data.get('init_channel') or ''),
            'paymentMethod': payment_method,
            'amount': str(amount_paise),
            'paymentInfo': {
                'paymentRefId': str(service_id or ''),
                'remarks': str(bill_data.get('remarks') or ''),
                'requestId': str(request_id or ''),
            },
        }

    def biller_info(self, payload: dict):
        return self._require_live_client().biller_info(payload).normalized

    def validate_bill(self, payload: dict):
        return self._require_live_client().bill_validate(payload).normalized

    def transaction_status(self, *, track_type: str, track_value: str, from_date: str = '', to_date: str = ''):
        client = self._require_live_client()
        payload = {'trackingType': track_type, 'trackingValue': track_value}
        if from_date:
            payload['fromDate'] = from_date
        if to_date:
            payload['toDate'] = to_date
        out = client.transaction_status(payload)
        return out.normalized

    def register_complaint(self, payload: dict):
        return self._require_live_client().complaint_register(payload).normalized

    def track_complaint(self, payload: dict):
        return self._require_live_client().complaint_track(payload).normalized

    def pull_plans(self, payload: dict):
        return self._require_live_client().plan_pull(payload).normalized

    def enquire_deposits(self, payload: dict):
        return self._require_live_client().deposit_enquiry(payload).normalized
