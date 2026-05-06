"""BBPS adapter over BillAvenue client (live UAT/PROD only)."""
from decimal import Decimal

from apps.integrations.base import BaseIntegration
from apps.integrations.billavenue.client import BillAvenueClient
from apps.integrations.billavenue.errors import BillAvenueClientError, BillAvenueValidationError
from apps.integrations.billavenue.parsers import _get_ci
from apps.integrations.models import BillAvenueAgentProfile, BillAvenueConfig


def _norm_key(key: str) -> str:
    return str(key).lower().replace(':', '').replace('-', '').replace('_', '')


def _ext_bill_pay_root(normalized: dict) -> dict:
    """BillAvenue often wraps the payload under ExtBillPayResponse (mixed casing)."""
    if not isinstance(normalized, dict):
        return {}
    inner = normalized.get('ExtBillPayResponse')
    if isinstance(inner, dict):
        return inner
    inner = _get_ci(normalized, 'ExtBillPayResponse')
    return inner if isinstance(inner, dict) else normalized


def _scalar_leaf_value(v) -> str:
    if v is None or isinstance(v, (dict, list)):
        return ''
    s = str(v).strip()
    return s


def _value_by_key_suffix(d: dict, suffix: str) -> str:
    """
    Read BillAvenue / XML-style fields: txnRefId, ns0:TxnRefId, txn-ref-id, etc.
    """
    if not isinstance(d, dict):
        return ''
    sn = _norm_key(suffix)
    hit = _get_ci(d, suffix) or _get_ci(d, suffix.replace('_', ''))
    if hit is not None and _scalar_leaf_value(hit):
        return _scalar_leaf_value(hit)
    for k, v in d.items():
        kn = _norm_key(k)
        if kn.endswith(sn) or kn == sn:
            s = _scalar_leaf_value(v)
            if s:
                return s
    return ''


def _txn_resp_type_value(d: dict) -> str:
    if not isinstance(d, dict):
        return ''
    for hint in (
        'txnRespType',
        'txnResponseType',
        'respType',
        'txnStatus',
        'transactionResponseType',
        'bbpsTxnRespType',
    ):
        s = _value_by_key_suffix(d, hint)
        if s:
            return s
    for k, v in d.items():
        kn = _norm_key(k)
        if 'txnresptype' in kn or (kn.endswith('txntype') and 'resp' in kn):
            s = _scalar_leaf_value(v)
            if s:
                return s
    return ''


def _walk_dicts(node, depth: int = 0, max_depth: int = 20):
    if depth > max_depth:
        return
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_dicts(v, depth + 1, max_depth)
    elif isinstance(node, list):
        for it in node:
            yield from _walk_dicts(it, depth + 1, max_depth)


def _score_bill_pay_candidate(d: dict) -> int:
    if not isinstance(d, dict):
        return 0
    score = 0
    if _txn_resp_type_value(d):
        score += 12
    if _value_by_key_suffix(d, 'txnRefId'):
        score += 4
    if _value_by_key_suffix(d, 'approvalRefNumber') or _value_by_key_suffix(d, 'approvalRefNum'):
        score += 4
    if _value_by_key_suffix(d, 'responseReason') or _value_by_key_suffix(d, 'errorMessage'):
        score += 2
    return score


def _best_bill_pay_transaction_dict(normalized: dict) -> dict:
    """Pick the deepest dict that actually carries txn / ref fields (handles XML namespaces and nesting)."""
    if not isinstance(normalized, dict):
        return {}
    best: dict = {}
    best_score = -1
    for d in _walk_dicts(normalized, 0, 20):
        sc = _score_bill_pay_candidate(d)
        if sc > best_score:
            best_score, best = sc, d
    if best_score > 0:
        return best
    root = _ext_bill_pay_root(normalized)
    return root if isinstance(root, dict) else {}


def _first_nested_reason(tree, max_depth: int = 20) -> str:
    """Longest non-empty human message anywhere in the decrypted tree."""
    best = ''
    if not isinstance(tree, dict):
        return ''

    def walk(x, depth):
        nonlocal best
        if depth > max_depth:
            return
        if isinstance(x, dict):
            for rk in (
                'responseReason',
                'responseDesc',
                'errorMessage',
                'errorDesc',
                'respMessage',
                'failureReason',
                'reason',
            ):
                s = _value_by_key_suffix(x, rk)
                if len(s) > len(best):
                    best = s
            for v in x.values():
                walk(v, depth + 1)
        elif isinstance(x, list):
            for it in x:
                walk(it, depth + 1)

    walk(tree, 0)
    return best


def extract_biller_response_dict(raw: dict | None) -> dict:
    """
    Resolve ``billerResponse`` from BillAvenue bill-fetch snapshots.

    Stored JSON may be flat, nested under ``billFetchResponse``, or wrapped in
    ``ExtBillFetchResponse`` (common in UAT). Without this, pay flows miss ``customerName``
    and BillAvenue returns E092 (Remitter Name required).
    """
    if not isinstance(raw, dict) or not raw:
        return {}
    direct = raw.get('billerResponse')
    if isinstance(direct, dict) and direct:
        return direct
    bfr = raw.get('billFetchResponse')
    if isinstance(bfr, dict):
        inner = bfr.get('billerResponse')
        if isinstance(inner, dict) and inner:
            return inner
    ext = raw.get('ExtBillFetchResponse') or _get_ci(raw, 'ExtBillFetchResponse')
    if isinstance(ext, dict):
        return extract_biller_response_dict(ext)
    return {}


def _billavenue_correlation_ref(*, bill_data: dict, request_id: str = '', service_id: str = '') -> str:
    """BillAvenue bill-pay must echo the same correlation id as bill-fetch (not internal PMBBPS service_id)."""
    return str(
        (request_id or '').strip()
        or str(bill_data.get('request_id') or '').strip()
        or str(bill_data.get('fetch_request_id') or '').strip()
        or str(bill_data.get('service_id') or '').strip()
        or str(service_id or '').strip()
    ).strip()


def _normalize_bbps_payment_mode(mode: str) -> str:
    m = str(mode or '').strip()
    if not m:
        return 'Cash'
    key = m.lower().replace('_', ' ').replace('-', ' ')
    table = {
        'cash': 'Cash',
        'upi': 'UPI',
        'bharat qr': 'Bharat QR',
        'debit card': 'Debit Card',
        'credit card': 'Credit Card',
        'prepaid card': 'Prepaid Card',
        'wallet': 'Wallet',
        'net banking': 'Internet Banking',
        'internet banking': 'Internet Banking',
        'neft': 'NEFT',
        'imps': 'IMPS',
    }
    return table.get(key, m[:1].upper() + m[1:] if len(m) > 1 else m.upper())


def _scalar_field(d: dict, key: str) -> str:
    """First non-empty string for key or case-insensitive match."""
    if not isinstance(d, dict):
        return ''
    raw = d.get(key)
    if raw is not None and not isinstance(raw, (dict, list)):
        s = str(raw).strip()
        if s:
            return s
    hit = _get_ci(d, key)
    if hit is not None and not isinstance(hit, (dict, list)):
        s = str(hit).strip()
        if s:
            return s
    return ''


def resolve_remitter_display_name(bill_data: dict) -> str:
    """
    BBPS/BillAvenue expects a real remitter (paymentInfo + often customerInfo.customerName).
    Gather from bill snapshot, explicit bill_data fields, form customer_details, then customer_info.
    """
    if not isinstance(bill_data, dict):
        return ''
    br = bill_data.get('biller_response') if isinstance(bill_data.get('biller_response'), dict) else {}
    for key in (
        'customerName',
        'ConsumerName',
        'consumerName',
        'accountHolderName',
        'AccountHolderName',
        'customer_name',
        'name',
        'Name',
    ):
        s = _scalar_field(br, key)
        if s:
            return s
    for key in ('remitter_name', 'customer_name'):
        s = str(bill_data.get(key) or '').strip()
        if s:
            return s
    cd = bill_data.get('customer_details') if isinstance(bill_data.get('customer_details'), dict) else {}
    for key in ('Customer Name', 'Name', 'Account Holder Name', 'Consumer Name'):
        s = str(cd.get(key) or '').strip()
        if s:
            return s
    ci = bill_data.get('customer_info') if isinstance(bill_data.get('customer_info'), dict) else {}
    s = _scalar_field(ci, 'customerName')
    if s:
        return s
    return ''


def _derive_payment_account_info(*, payment_mode: str, bill_data: dict, correlation_ref: str = '') -> str:
    mode = str(payment_mode or '').strip().lower()
    customer_info = bill_data.get('customer_info') if isinstance(bill_data.get('customer_info'), dict) else {}
    customer_details = bill_data.get('customer_details') if isinstance(bill_data.get('customer_details'), dict) else {}
    mobile = str(
        customer_info.get('customerMobile')
        or customer_details.get('Mobile Number')
        or ''
    ).strip()
    payment_ref = str(correlation_ref or '').strip() or _billavenue_correlation_ref(bill_data=bill_data)
    if mode == 'cash':
        if payment_ref:
            return f'{payment_ref}|{payment_ref}'
        return 'Cash Payment'
    if mode in ('upi', 'bharat qr'):
        return str(bill_data.get('vpa') or customer_details.get('VPA') or '').strip() or (f"{mobile}@upi" if mobile else 'UPI Payment')
    if mode in ('debit card', 'credit card'):
        last4 = str(customer_details.get('Card Last4 Digits') or customer_details.get('Card Last 4 Digits') or '').strip()
        issuer = str(customer_details.get('Card Issuer') or '').strip()
        if last4 and issuer:
            return f'{last4}|{issuer}'
        if payment_ref:
            return f'{payment_ref}|{payment_ref}'
        return 'Card Payment'
    if mode == 'wallet':
        wallet_name = str(customer_details.get('Wallet Name') or 'Wallet').strip()
        return f'{wallet_name}|{mobile}' if mobile else wallet_name
    if payment_ref:
        return f'{payment_ref}|{payment_ref}'
    return 'Payment'


def _build_remitter_payment_info(*, service_id: str, request_id: str, payment_mode: str, bill_data: dict) -> list[dict]:
    remitter_name = resolve_remitter_display_name(bill_data)
    if not remitter_name:
        raise BillAvenueValidationError(
            'Remitter name is required for BBPS bill pay. Update your profile name, ensure the bill fetch '
            'returned a customer name, or pass customer_name / remitter_name on the pay request.'
        )
    payment_ref = _billavenue_correlation_ref(bill_data=bill_data, request_id=request_id, service_id=service_id)
    account_info = _derive_payment_account_info(
        payment_mode=payment_mode, bill_data=bill_data, correlation_ref=payment_ref
    )
    mode_label = _normalize_bbps_payment_mode(payment_mode)
    return [
        {'infoName': 'Remitter Name', 'infoValue': remitter_name},
        {'infoName': 'PaymentRefId', 'infoValue': payment_ref},
        {'infoName': 'Payment Account Info', 'infoValue': account_info},
        {'infoName': 'Payment mode', 'infoValue': mode_label},
    ]


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
            def _to_rupees(value):
                raw = str(value or '').strip()
                if not raw:
                    return '0'
                try:
                    dec = Decimal(raw)
                except Exception:
                    return raw
                # BillAvenue billAmount is usually paise (integer). Additional info often arrives in rupees with decimals.
                if '.' in raw:
                    return str(dec)
                return str(dec / Decimal('100'))

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
            bill_response = extract_biller_response_dict(normalized) or normalized.get('billerResponse') or {}
            if not bill_response and isinstance(normalized.get('billFetchResponse'), dict):
                bill_response = (normalized.get('billFetchResponse') or {}).get('billerResponse') or {}
            additional_info_rows = (
                normalized.get('additionalInfo', {}).get('info')
                or normalized.get('billFetchResponse', {}).get('additionalInfo', {}).get('info')
                or []
            )
            additional_info_for_pay: list[dict] = []
            if isinstance(additional_info_rows, list):
                for row in additional_info_rows:
                    if not isinstance(row, dict):
                        continue
                    name = str(row.get('infoName') or row.get('info_name') or '').strip()
                    if not name:
                        continue
                    val = row.get('infoValue') if 'infoValue' in row else row.get('info_value')
                    additional_info_for_pay.append(
                        {'infoName': name, 'infoValue': '' if val is None else str(val)}
                    )
            info_map = {}
            if isinstance(additional_info_rows, list):
                for row in additional_info_rows:
                    if not isinstance(row, dict):
                        continue
                    key = str(row.get('infoName') or '').strip().lower()
                    if key:
                        info_map[key] = str(row.get('infoValue') or '').strip()
            amount_paise = (
                bill_response.get('billAmount')
                or normalized.get('billAmount')
                or 0
            )
            amount = Decimal(str(amount_paise or 0)) / Decimal('100')
            min_due = (
                info_map.get('minimum amount due')
                or info_map.get('minimum due amount')
                or bill_response.get('minimumDueAmount')
                or bill_response.get('minimumAmountDue')
                or '0'
            )
            total_due = (
                info_map.get('current outstanding amount')
                or info_map.get('total due amount')
                or bill_response.get('totalDueAmount')
                or bill_response.get('billAmount')
                or normalized.get('billAmount')
                or '0'
            )
            return {
                'amount': amount,
                'due_date': bill_response.get('dueDate'),
                'bill_date': bill_response.get('billDate'),
                'bill_number': bill_response.get('billNumber') or bill_response.get('bill_number') or '',
                'customer_name': bill_response.get('customerName') or '',
                'minimum_due': _to_rupees(min_due),
                'total_due': _to_rupees(total_due),
                'customer_details': kwargs,
                'raw': normalized,
                'request_id': out.request_id,
                'response_code': out.response_code,
                'additional_info': additional_info_for_pay,
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
            raw_extra = bill_data.get('bill_payment_payload') or {}
            payload = self._build_bill_payment_payload(
                service_id=service_id,
                request_id=request_id,
                amount=amount,
                bill_data=bill_data,
            )
            if isinstance(raw_extra, dict):
                ex_ai = raw_extra.get('amountInfo')
                if isinstance(ex_ai, dict) and isinstance(payload.get('amountInfo'), dict):
                    merged = dict(payload['amountInfo'])
                    merged.update(ex_ai)
                    payload['amountInfo'] = merged
            # Outer HTTP ``requestId`` must match the successful bill-fetch envelope id so BillAvenue can
            # resolve fetch context (E210 otherwise). Retrying pay with the same id returns E204 — consume
            # the fetch session after a pay attempt so the user must fetch again.
            pay_transport = _billavenue_correlation_ref(
                bill_data=bill_data,
                request_id=str(request_id or '').strip(),
                service_id=str(service_id or '').strip(),
            )
            out = client.bill_pay(payload, request_id=pay_transport or None)
            normalized = out.normalized if isinstance(out.normalized, dict) else {}
            body = _best_bill_pay_transaction_dict(normalized)
            txn_raw = _txn_resp_type_value(body)
            txn_type = str(txn_raw).upper()
            reason = _value_by_key_suffix(body, 'responseReason') or _value_by_key_suffix(body, 'responseDesc')
            txn_ref = _value_by_key_suffix(body, 'txnRefId')
            approval_ref = _value_by_key_suffix(body, 'approvalRefNumber') or _value_by_key_suffix(
                body, 'approvalRefNum'
            )
            inner_code = _value_by_key_suffix(body, 'responseCode')
            env_ok = str(out.response_code or '').strip() in ('000', '0', '')
            if env_ok and txn_ref and approval_ref and inner_code in ('', '000', '0') and not txn_type:
                return {
                    'status': 'SUCCESS',
                    'message': reason or 'Payment processed successfully',
                    'transaction_id': txn_ref or service_id,
                    'txn_ref_id': txn_ref or '',
                    'approval_ref_number': approval_ref or '',
                    'response_payload': normalized,
                }
            if 'FORWARD' in txn_type:
                return {
                    'status': 'SUCCESS',
                    'message': reason or 'Payment processed successfully',
                    'transaction_id': txn_ref or service_id,
                    'txn_ref_id': txn_ref or '',
                    'approval_ref_number': approval_ref or '',
                    'response_payload': normalized,
                }
            if 'AWAIT' in txn_type:
                return {
                    'status': 'AWAITED',
                    'message': reason or 'Payment awaiting final status',
                    'transaction_id': txn_ref or service_id,
                    'txn_ref_id': txn_ref or '',
                    'approval_ref_number': approval_ref or '',
                    'response_payload': normalized,
                }
            msg = reason.strip() if reason else _first_nested_reason(normalized)
            if not msg:
                top_keys = list(normalized.keys())[:12] if isinstance(normalized, dict) else []
                msg = (
                    f'Bill pay declined (txnRespType={txn_raw or "?"})'
                    + (f'; response keys: {top_keys}' if top_keys else '')
                )
            if inner_code and inner_code not in ('000', '0', ''):
                msg = f'{msg} (responseCode={inner_code})'.strip()
            return {
                'status': 'FAILED',
                'message': msg,
                'transaction_id': txn_ref or service_id,
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
        payment_mode = _normalize_bbps_payment_mode(str(bill_data.get('payment_mode') or '').strip() or 'Cash')
        remitter_display = resolve_remitter_display_name(bill_data)
        if not remitter_display:
            raise BillAvenueValidationError(
                'Remitter name is required for BBPS bill pay. Update your profile name, ensure the bill fetch '
                'returned a customer name, or pass customer_name / remitter_name on the pay request.'
            )
        ci_merged = dict(customer_info)
        if not str(ci_merged.get('customerName') or '').strip():
            ci_merged['customerName'] = remitter_display
        payer_email = str(bill_data.get('payer_email') or bill_data.get('customer_email') or '').strip()
        if payer_email and not str(ci_merged.get('customerEmail') or '').strip():
            ci_merged['customerEmail'] = payer_email
        corr = _billavenue_correlation_ref(bill_data=bill_data, request_id=str(request_id or ''), service_id=str(service_id or ''))
        payload = {
            'agentId': str(bill_data.get('agent_id') or self._default_agent_id()),
            'billerId': biller_id,
            'customerInfo': ci_merged,
            'inputParams': {'input': input_params},
            'agentDeviceInfo': bill_data.get('agent_device_info') or {'initChannel': str(bill_data.get('init_channel') or '').strip() or 'AGT'},
            'billerAdhoc': bool(bill_data.get('biller_adhoc', False)),
            # Match BillAvenue XML sample object shape to avoid UM001 Invalid XML request.
            'amountInfo': {
                'amount': str(amount_paise),
                'currency': '356',
                'custConvFee': '0',
            },
            'paymentMethod': {
                'paymentMode': payment_mode,
                'quickPay': 'N',
                'splitPay': 'N',
            },
        }
        if corr:
            payload['requestId'] = corr
            payload['paymentRefId'] = corr
        biller_response = bill_data.get('biller_response') or {}
        if isinstance(biller_response, dict) and biller_response:
            payload['billerResponse'] = biller_response
        payment_info = bill_data.get('payment_info')
        infos = []
        if isinstance(payment_info, list):
            infos = [row for row in payment_info if isinstance(row, dict)]
        elif isinstance(payment_info, dict):
            # Accept both {"info":[...]} and single {"infoName":"...","infoValue":"..."} shapes.
            if isinstance(payment_info.get('info'), list):
                infos = [row for row in payment_info.get('info') if isinstance(row, dict)]
            elif str(payment_info.get('infoName') or '').strip():
                infos = [payment_info]
        def _has_nonempty_remitter(rows: list) -> bool:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                if str(row.get('infoName') or '').strip().lower() != 'remitter name':
                    continue
                if str(row.get('infoValue') or '').strip():
                    return True
            return False

        remitter_block = _build_remitter_payment_info(
            service_id=str(service_id or ''),
            request_id=str(request_id or ''),
            payment_mode=payment_mode,
            bill_data=bill_data,
        )
        if not infos:
            infos = remitter_block
        elif not _has_nonempty_remitter(infos):
            infos = remitter_block + infos
        payload['paymentInfo'] = {'info': infos}
        additional_info = bill_data.get('additional_info')
        if isinstance(additional_info, list) and additional_info:
            payload['additionalInfo'] = {'info': additional_info}
        return payload

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
        client = self._require_live_client()
        req = dict(payload or {})
        biller_ids = req.get('billerId')
        # Normalize billerId to provider-friendly scalar/list and strip empty values.
        if isinstance(biller_ids, list):
            biller_ids = [str(x or '').strip() for x in biller_ids if str(x or '').strip()]
            if len(biller_ids) == 1:
                req['billerId'] = biller_ids[0]
            elif biller_ids:
                req['billerId'] = biller_ids
            else:
                req.pop('billerId', None)
        elif biller_ids is not None:
            biller_id = str(biller_ids or '').strip()
            if biller_id:
                req['billerId'] = biller_id
            else:
                req.pop('billerId', None)
        agent_id = str(req.get('agentId') or self._default_agent_id()).strip()
        if agent_id:
            req['agentId'] = agent_id
        return client.plan_pull(req).normalized

    def enquire_deposits(self, payload: dict):
        return self._require_live_client().deposit_enquiry(payload).normalized
