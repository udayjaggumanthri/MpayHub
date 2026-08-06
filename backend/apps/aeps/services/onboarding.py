"""Merchant onboarding + eKYC orchestration."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.aeps.models import AepsApiAuditLog, AepsTransaction
from apps.aeps.services.gates import assert_entitled, get_merchant
from apps.aeps.services.ids import generate_merchant_tran_id, merchant_pin_plain
from apps.integrations.fingpay.crypto import mask_aadhaar, scrub_sensitive
from apps.integrations.fingpay.registry import get_fingpay_client

# Flat draft keys used by the Setup UI (also accepted nested on submit).
DRAFT_KEYS = (
    'firstName',
    'lastName',
    'middleName',
    'merchantPhoneNumber',
    'emailId',
    'merchantAddress1',
    'merchantAddress2',
    'merchantCityName',
    'merchantDistrictName',
    'merchantPinCode',
    'merchantState',
    'companyLegalName',
    'companyType',
    'userPan',
    'aadhaarNumber',
    'gstinNumber',
    'companyOrShopPan',
    'companyBankAccountNumber',
    'bankIfscCode',
    'companyBankName',
    'bankBranchName',
    'bankAccountName',
    'shopName',
    'shopAddress',
    'shopCity',
    'shopDistrict',
    'shopState',
    'shopPincode',
    'merchantPanImage',
    'maskedAadharImage',
    'backgroundImageOfShop',
)


def _safe_str(value) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    if text.lower() in ('[redacted]', 'none', 'null'):
        return ''
    return text


def flatten_onboarding_payload(payload: dict | None) -> dict:
    """Normalize stored draft (flat or nested submit shape) into UI flat keys."""
    src = payload if isinstance(payload, dict) else {}
    out = {k: '' for k in DRAFT_KEYS}

    for key in DRAFT_KEYS:
        if key in src and src.get(key) not in (None, ''):
            out[key] = _safe_str(src.get(key))

    addr = src.get('merchantAddress') if isinstance(src.get('merchantAddress'), dict) else {}
    kyc = src.get('kyc') if isinstance(src.get('kyc'), dict) else {}
    settle = src.get('settlementV1') if isinstance(src.get('settlementV1'), dict) else {}
    shop = src.get('merchantKycAddressData') if isinstance(src.get('merchantKycAddressData'), dict) else {}

    mapping = [
        ('merchantAddress1', addr.get('merchantAddress1')),
        ('merchantAddress2', addr.get('merchantAddress2')),
        ('merchantCityName', addr.get('merchantCityName')),
        ('merchantDistrictName', addr.get('merchantDistrictName')),
        ('merchantPinCode', addr.get('merchantPinCode')),
        ('merchantState', addr.get('merchantState')),
        ('userPan', kyc.get('userPan')),
        ('aadhaarNumber', kyc.get('aadhaarNumber')),
        ('gstinNumber', kyc.get('gstinNumber') or kyc.get('gstInNumber')),
        ('companyOrShopPan', kyc.get('companyOrShopPan')),
        ('companyBankAccountNumber', settle.get('companyBankAccountNumber')),
        ('bankIfscCode', settle.get('bankIfscCode')),
        ('companyBankName', settle.get('companyBankName')),
        ('bankBranchName', settle.get('bankBranchName')),
        ('bankAccountName', settle.get('bankAccountName')),
        ('merchantPanImage', kyc.get('merchantPanImage') or src.get('merchantPanImage')),
        ('maskedAadharImage', kyc.get('maskedAadharImage') or src.get('maskedAadharImage')),
        ('backgroundImageOfShop', shop.get('backgroundImageOfShop') or src.get('backgroundImageOfShop')),
        ('shopAddress', shop.get('shopAddress')),
        ('shopCity', shop.get('shopCity')),
        ('shopDistrict', shop.get('shopDistrict')),
        ('shopState', shop.get('shopState')),
        ('shopPincode', shop.get('shopPincode')),
        ('shopName', shop.get('shopName') or src.get('shopName')),
        ('firstName', src.get('firstName')),
        ('lastName', src.get('lastName')),
        ('middleName', src.get('middleName')),
        ('merchantPhoneNumber', src.get('merchantPhoneNumber')),
        ('emailId', src.get('emailId')),
        ('companyLegalName', src.get('companyLegalName')),
        ('companyType', src.get('companyType')),
    ]
    for key, value in mapping:
        if not out.get(key) and value not in (None, ''):
            out[key] = _safe_str(value)
    return out


def build_onboarding_prefill(user) -> dict:
    """Best-effort autofill from User / Profile / KYC / BankAccount (no full Aadhaar secrets)."""
    prefill = {k: '' for k in DRAFT_KEYS}
    sources = []

    profile = getattr(user, 'profile', None)
    if profile is None:
        try:
            from apps.users.models import UserProfile

            profile = UserProfile.objects.filter(user=user).first()
        except Exception:
            profile = None

    first = _safe_str(getattr(profile, 'first_name', None) or getattr(user, 'first_name', None))
    last = _safe_str(getattr(profile, 'last_name', None) or getattr(user, 'last_name', None))
    if first or last:
        prefill['firstName'] = first
        prefill['lastName'] = last
        sources.append('profile')

    phone = _safe_str(getattr(user, 'phone', None) or getattr(profile, 'alternate_phone', None))
    if phone:
        prefill['merchantPhoneNumber'] = phone
        sources.append('user.phone')

    email = _safe_str(getattr(user, 'email', None))
    if email:
        prefill['emailId'] = email
        sources.append('user.email')

    business_name = _safe_str(getattr(profile, 'business_name', None))
    business_address = _safe_str(getattr(profile, 'business_address', None))
    if business_name:
        prefill['shopName'] = business_name
        prefill['companyLegalName'] = business_name
        prefill['bankAccountName'] = prefill['bankAccountName'] or business_name
    if business_address:
        prefill['merchantAddress1'] = business_address
        prefill['shopAddress'] = business_address
        sources.append('profile.business')

    # Super-merchant GST / company PAN from provider secrets (doc: mandatory KYC fields)
    try:
        from apps.core.utils import decrypt_secret_payload
        from apps.integrations.fingpay.registry import get_active_provider

        provider = get_active_provider()
        secrets = decrypt_secret_payload(provider.secrets_encrypted or '') or {}
        gst = _safe_str(secrets.get('gstin_number') or secrets.get('gstinNumber'))
        company_pan = _safe_str(secrets.get('company_or_shop_pan') or secrets.get('companyOrShopPan'))
        if gst:
            prefill['gstinNumber'] = gst
            sources.append('provider.gstin')
        if company_pan:
            prefill['companyOrShopPan'] = company_pan.upper()
            sources.append('provider.company_pan')
    except Exception:
        pass

    kyc = getattr(user, 'kyc', None)
    if kyc is None:
        try:
            from apps.users.models import KYC

            kyc = KYC.objects.filter(user=user).first()
        except Exception:
            kyc = None

    if kyc:
        pan = _safe_str(getattr(kyc, 'pan', None))
        if pan:
            prefill['userPan'] = pan.upper()
            sources.append('kyc.pan')

        identity = getattr(kyc, 'verified_identity', None) or {}
        aadhaar_block = identity.get('aadhaar') if isinstance(identity, dict) else {}
        pan_block = identity.get('pan') if isinstance(identity, dict) else {}
        if isinstance(pan_block, dict) and not prefill['userPan']:
            prefill['userPan'] = _safe_str(pan_block.get('pan')).upper()
        if isinstance(aadhaar_block, dict):
            addr = _safe_str(aadhaar_block.get('address'))
            district = _safe_str(aadhaar_block.get('district'))
            state = _safe_str(aadhaar_block.get('state'))
            pincode = _safe_str(aadhaar_block.get('pincode'))
            if addr:
                prefill['merchantAddress1'] = prefill['merchantAddress1'] or addr
                prefill['shopAddress'] = prefill['shopAddress'] or addr
            if district:
                prefill['merchantDistrictName'] = district
                prefill['shopDistrict'] = district
                prefill['merchantCityName'] = prefill['merchantCityName'] or district
                prefill['shopCity'] = prefill['shopCity'] or district
            if state:
                # Keep name for display; UI will map to Fingpay stateId via masters
                prefill['merchantState'] = state
                prefill['shopState'] = state
            if pincode:
                prefill['merchantPinCode'] = pincode
                prefill['shopPincode'] = pincode
            sources.append('kyc.aadhaar_identity')

        # Never auto-fill full Aadhaar; show masked hint only when known.
        masked = mask_aadhaar(_safe_str(getattr(kyc, 'aadhaar', None)))
        if masked and masked != 'xxxxxxxxxxxx':
            prefill['aadhaarNumber'] = ''  # user must re-enter full 12 digits for submit
            prefill['_aadhaarHint'] = masked

        if not prefill.get('companyOrShopPan') and prefill.get('userPan'):
            prefill['companyOrShopPan'] = prefill['userPan']

    try:
        from apps.bank_accounts.models import BankAccount

        bank = (
            BankAccount.objects.filter(user=user, is_deleted=False)
            .order_by('-is_verified', '-updated_at')
            .first()
        )
        if bank:
            prefill['companyBankAccountNumber'] = _safe_str(bank.account_number)
            prefill['bankIfscCode'] = _safe_str(bank.ifsc).upper()
            prefill['companyBankName'] = _safe_str(getattr(bank, 'bank_name', '') or '')
            prefill['bankAccountName'] = _safe_str(
                bank.account_holder_name or bank.beneficiary_name or prefill['bankAccountName']
            )
            if not prefill['merchantCityName'] and getattr(bank, 'city', None):
                prefill['merchantCityName'] = _safe_str(bank.city)
            sources.append('bank_account')
    except Exception:
        pass

    return {
        'fields': {k: v for k, v in prefill.items() if not k.startswith('_')},
        'hints': {k[1:]: v for k, v in prefill.items() if k.startswith('_') and v},
        'sources': sorted(set(sources)),
    }


def get_onboarding_form(*, user) -> dict:
    """Draft + profile prefill for Setup UI."""
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing. Contact Admin to re-enable AEPS.'})
    draft = flatten_onboarding_payload(merchant.onboarding_payload)
    prefill = build_onboarding_prefill(user)
    # Draft wins over prefill; empty draft keys filled from profile.
    merged = dict(prefill['fields'])
    for key, value in draft.items():
        if _safe_str(value):
            merged[key] = _safe_str(value)

    from apps.aeps.services.masters import fetch_company_types, fetch_states, resolve_state_id

    states = fetch_states()
    company_types = fetch_company_types()
    # Normalize state names in merged form to stateId when possible
    for key in ('merchantState', 'shopState'):
        sid = resolve_state_id(merged.get(key), states)
        if sid is not None:
            merged[key] = str(sid)

    has_draft = any(_safe_str(draft.get(k)) for k in DRAFT_KEYS if k != 'aadhaarNumber')
    return {
        'stage': merchant.stage,
        'merchant_login_id': merchant.merchant_login_id,
        'masked_aadhaar': merchant.masked_aadhaar or '',
        'device_imei': merchant.device_imei or '',
        'device_ready': bool(merchant.device_ready),
        'form': merged,
        'draft': draft,
        'prefill': prefill,
        'masters': {
            'states': states,
            'company_types': company_types,
        },
        'has_saved_draft': has_draft or merchant.stage == 'onboarding_draft',
        'last_error': merchant.last_error or '',
    }


def save_onboarding_draft(*, user, payload: dict) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing. Contact Admin to re-enable AEPS.'})
    if merchant.stage == 'active':
        raise ValidationError({'message': 'Merchant already active.'})

    raw = payload if isinstance(payload, dict) else {}
    # Accept nested or flat; store flat for reliable restore.
    flat = flatten_onboarding_payload(raw)
    for key in DRAFT_KEYS:
        if key in raw and raw.get(key) is not None:
            flat[key] = _safe_str(raw.get(key))

    aadhaar = _safe_str(raw.get('aadhaarNumber') or raw.get('aadhaar') or flat.get('aadhaarNumber'))
    if aadhaar and not aadhaar.lower().startswith('x') and aadhaar.isdigit() and len(aadhaar) >= 4:
        merchant.masked_aadhaar = mask_aadhaar(aadhaar)
        flat['aadhaarNumber'] = merchant.masked_aadhaar
    elif merchant.masked_aadhaar:
        flat['aadhaarNumber'] = merchant.masked_aadhaar

    # Drop empty keys so we don't wipe good values with blanks on partial saves
    incoming = {k: v for k, v in flat.items() if _safe_str(v)}
    merchant.onboarding_payload = {**(merchant.onboarding_payload or {}), **incoming}
    if merchant.stage in ('not_started', ''):
        merchant.stage = 'onboarding_draft'
    merchant.save()
    return {
        'stage': merchant.stage,
        'onboarding_payload': flatten_onboarding_payload(merchant.onboarding_payload),
        'masked_aadhaar': merchant.masked_aadhaar,
    }


def _sanitize_first_name(value: str) -> str:
    """Fingpay: firstName — no spaces / special chars, max 40."""
    import re

    cleaned = re.sub(r'[^A-Za-z]', '', _safe_str(value))
    return cleaned[:40]


def _sanitize_last_name(value: str) -> str:
    """Allow letters/spaces only; collapse whitespace (sample uses a single token)."""
    import re

    cleaned = re.sub(r'[^A-Za-z\s]', '', _safe_str(value))
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned[:40]


def _ensure_min_len(value: str, minimum: int, pad_from: str = '') -> str:
    text = _safe_str(value)
    if len(text) >= minimum:
        return text
    filler = _safe_str(pad_from) or 'AddressLine'
    combined = f'{text} {filler}'.strip()
    if len(combined) < minimum:
        combined = (combined + ' ' + ('X' * minimum))[: minimum]
    return combined[:120]


# Tiny 1x1 PNG — Fingpay sample includes base64 images for KYC / shop proof fields.
_PLACEHOLDER_PNG_B64 = (
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)


def _provider_kyc_defaults() -> dict:
    try:
        from apps.core.utils import decrypt_secret_payload
        from apps.integrations.fingpay.registry import get_active_provider

        provider = get_active_provider()
        secrets = decrypt_secret_payload(provider.secrets_encrypted or '') or {}
        return {
            'gstinNumber': _safe_str(secrets.get('gstin_number') or secrets.get('gstinNumber')),
            'companyOrShopPan': _safe_str(
                secrets.get('company_or_shop_pan') or secrets.get('companyOrShopPan')
            ).upper(),
        }
    except Exception:
        return {'gstinNumber': '', 'companyOrShopPan': ''}


def _image_b64(flat: dict, key: str) -> str:
    """Accept raw base64 or data-URL; fall back to tiny placeholder only if empty."""
    raw = _safe_str(flat.get(key))
    if raw.startswith('data:') and ',' in raw:
        raw = raw.split(',', 1)[1]
    raw = ''.join(raw.split())
    if len(raw) > 40:
        return raw
    return _PLACEHOLDER_PNG_B64


def build_fingpay_merchant_payload(*, merchant, flat: dict, latitude, longitude, aadhaar_full: str = '') -> dict:
    """
    Build MerchantModelV1 per Fingpay Services API Doc (Merchant Onboarding).
    merchantState / shopState / companyType must be integers from master APIs.
    """
    from apps.aeps.services.masters import fetch_states, resolve_state_id

    states = fetch_states()
    state_id = resolve_state_id(flat.get('merchantState'), states)
    shop_state_id = resolve_state_id(flat.get('shopState') or flat.get('merchantState'), states)
    if state_id is None:
        raise ValidationError(
            {
                'code': 'INVALID_STATE',
                'message': 'Select merchant state from the Fingpay state list (getstates).',
            }
        )
    if shop_state_id is None:
        raise ValidationError(
            {
                'code': 'INVALID_SHOP_STATE',
                'message': 'Select shop state from the Fingpay state list (getstates).',
            }
        )

    try:
        company_type = int(flat.get('companyType'))
    except (TypeError, ValueError):
        raise ValidationError(
            {
                'code': 'INVALID_COMPANY_TYPE',
                'message': 'Select company / shop category (companyType) from Fingpay master list.',
            }
        ) from None

    defaults = _provider_kyc_defaults()
    user_pan = _safe_str(flat.get('userPan')).upper()
    # Java field is gstinNumber; table alias gstInNumber — accept both on input.
    gstin = (
        _safe_str(flat.get('gstinNumber'))
        or _safe_str(flat.get('gstInNumber'))
        or defaults['gstinNumber']
    )
    company_pan = _safe_str(flat.get('companyOrShopPan')).upper() or defaults['companyOrShopPan'] or user_pan
    if not gstin:
        raise ValidationError(
            {
                'code': 'GSTIN_REQUIRED',
                'message': 'GSTIN is mandatory. Admin must set Super Merchant GSTIN in AEPS provider settings, or enter it on the form.',
            }
        )
    if not company_pan:
        raise ValidationError(
            {
                'code': 'COMPANY_PAN_REQUIRED',
                'message': 'Company/Shop PAN is mandatory (kyc.companyOrShopPan).',
            }
        )

    addr2 = _ensure_min_len(
        flat.get('merchantAddress2') or '',
        11,
        pad_from=f"{flat.get('merchantCityName') or ''} {flat.get('merchantDistrictName') or ''}",
    )
    pin = merchant_pin_plain(merchant)
    if not pin:
        raise ValidationError(
            {
                'code': 'MERCHANT_PIN_MISSING',
                'message': 'Merchant PIN missing. Ask Admin to re-enable AEPS so a pin is generated.',
            }
        )
    aadhaar = _safe_str(aadhaar_full or flat.get('aadhaarNumber'))
    legal = _safe_str(
        flat.get('companyLegalName') or flat.get('shopName') or f"{flat.get('firstName')} {flat.get('lastName')}"
    )
    legal = ''.join(ch for ch in legal if ch.isalnum() or ch.isspace()).strip() or 'Merchant Shop'
    first = _sanitize_first_name(flat.get('firstName'))
    last = _sanitize_last_name(flat.get('lastName'))
    middle = ''.join(ch for ch in _safe_str(flat.get('middleName')) if ch.isalpha())[:40]
    if not first or not last:
        raise ValidationError({'message': 'First name and last name are required (letters only for first name).'})
    if first.lower() == last.lower().replace(' ', ''):
        raise ValidationError({'code': '5005', 'message': 'First name and last name cannot be the same.'})

    # Doc: shopLatitude/shopLongitude are Double; flags are True/False strings.
    shop_lat = float(latitude)
    shop_lng = float(longitude)

    return {
        'merchantLoginId': merchant.merchant_login_id,
        # Doc: "Plain password must be sent" for merchantLoginPin (not MD5).
        'merchantLoginPin': pin,
        'firstName': first,
        'lastName': last,
        'middleName': middle,
        'merchantPhoneNumber': _safe_str(flat.get('merchantPhoneNumber'))[-10:],
        'merchantAddress': {
            'merchantAddress1': _safe_str(flat.get('merchantAddress1')),
            'merchantAddress2': addr2,
            'merchantState': int(state_id),
            'merchantCityName': _safe_str(flat.get('merchantCityName')),
            'merchantDistrictName': _safe_str(flat.get('merchantDistrictName')),
            'merchantPinCode': _safe_str(flat.get('merchantPinCode')),
        },
        'companyLegalName': legal[:100],
        'companyType': company_type,
        'emailId': _safe_str(flat.get('emailId')),
        # Doc: True/False for certificate / shopAndPanImage flags
        'certificateOfIncorporationImage': 'True',
        'kyc': {
            'userPan': user_pan,
            'aadhaarNumber': aadhaar,
            # Java model: private String gstinNumber (param table also writes gstInNumber)
            'gstinNumber': gstin,
            'companyOrShopPan': company_pan,
            'merchantPanImage': _image_b64(flat, 'merchantPanImage'),
            'maskedAadharImage': _image_b64(flat, 'maskedAadharImage'),
            'shopAndPanImage': 'True',
        },
        'settlementV1': {
            'companyBankAccountNumber': _safe_str(flat.get('companyBankAccountNumber')),
            'bankIfscCode': _safe_str(flat.get('bankIfscCode')).upper(),
            'companyBankName': _safe_str(flat.get('companyBankName') or 'State Bank of India'),
            'bankBranchName': _safe_str(flat.get('bankBranchName') or flat.get('companyBankName') or 'Main'),
            'bankAccountName': _safe_str(flat.get('bankAccountName')),
        },
        'tradeBusinessProof': 'True',
        'termsConditionCheck': 'True',
        'cancelledChequeImages': 'True',
        'physicalVerification': 'True',
        # Doc spelling (not the older "vedio..." typo)
        'videoKycWithLatLongData': 'True',
        'merchantKycAddressData': {
            'shopAddress': _safe_str(flat.get('shopAddress')),
            'shopCity': _safe_str(flat.get('shopCity')),
            'shopDistrict': _safe_str(flat.get('shopDistrict')),
            'shopState': int(shop_state_id),
            'shopPincode': _safe_str(flat.get('shopPincode')),
            'shopLatitude': shop_lat,
            'shopLongitude': shop_lng,
            'backgroundImageOfShop': _image_b64(flat, 'backgroundImageOfShop'),
        },
    }


def submit_onboarding(*, user, latitude, longitude, ip_address: str, merchant_body: dict | None = None) -> dict:
    """Submit merchant creation to Fingpay. Not fully atomic so failed attempts stay auditable."""
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})

    raw = merchant_body if isinstance(merchant_body, dict) else {}
    flat = flatten_onboarding_payload(raw)
    # Overlay top-level flat keys from request (UI may send flat + nested)
    for key in DRAFT_KEYS:
        if key in raw and raw.get(key) not in (None, ''):
            flat[key] = _safe_str(raw.get(key))
    if isinstance(raw.get('kyc'), dict):
        for k in ('userPan', 'aadhaarNumber', 'gstinNumber', 'gstInNumber', 'companyOrShopPan'):
            if raw['kyc'].get(k):
                flat['gstinNumber' if k == 'gstInNumber' else k] = _safe_str(raw['kyc'].get(k))
    if raw.get('companyType') not in (None, ''):
        flat['companyType'] = _safe_str(raw.get('companyType'))
    if raw.get('companyLegalName'):
        flat['companyLegalName'] = _safe_str(raw.get('companyLegalName'))

    aadhaar_full = ''
    if isinstance(raw.get('kyc'), dict):
        aadhaar_full = _safe_str(raw['kyc'].get('aadhaarNumber'))
    aadhaar_full = aadhaar_full or _safe_str(raw.get('aadhaarNumber')) or _safe_str(flat.get('aadhaarNumber'))
    if not (aadhaar_full.isdigit() and len(aadhaar_full) == 12):
        raise ValidationError(
            {
                'code': 'AADHAAR_REQUIRED',
                'message': 'Enter a valid 12-digit Aadhaar number to submit onboarding.',
            }
        )

    fingpay_merchant = build_fingpay_merchant_payload(
        merchant=merchant,
        flat=flat,
        latitude=latitude,
        longitude=longitude,
        aadhaar_full=aadhaar_full,
    )
    merchant.masked_aadhaar = mask_aadhaar(aadhaar_full)

    # Persist flat draft (masked aadhaar) before calling provider
    save_onboarding_draft(user=user, payload={**flat, 'aadhaarNumber': aadhaar_full})

    client = get_fingpay_client()
    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=generate_merchant_tran_id('ONB'),
        product='ONB',
        status='pending',
        latitude=latitude,
        longitude=longitude,
        client_ip=ip_address or None,
        device_imei=merchant.device_imei or '',
        masked_aadhaar=merchant.masked_aadhaar,
    )
    try:
        # Production php/creation (encrypted). UAT simple API only if URL still contains fpuat.
        use_simple = 'fpuat' in (client.onboarding_base_url or '').lower()
        if use_simple:
            resp = client.create_merchant_simple(
                fingpay_merchant,
                latitude=latitude,
                longitude=longitude,
                ip_address=ip_address or '0.0.0.0',
            )
        else:
            resp = client.create_merchant(
                fingpay_merchant,
                latitude=latitude,
                longitude=longitude,
                ip_address=ip_address or '0.0.0.0',
            )
    except Exception as exc:
        from apps.integrations.fingpay.client import FingpayClientError

        err_msg = str(exc)
        if isinstance(exc, FingpayClientError) and exc.status_code == 403:
            err_msg = (
                'Fingpay Production blocked our server (HTTP 403). '
                'IP 57.131.39.21 is not whitelisted on fingpayap.tapits.in yet. '
                'Ask Tapits/Sumit to whitelist this IP on Production — then retry Submit. '
                'Your form data is fine; this is not a merchant-field validation error.'
            )
        txn.status = 'failed'
        txn.response_code = str(getattr(exc, 'status_code', '') or '')
        txn.response_message = err_msg[:500]
        txn.save(update_fields=['status', 'response_code', 'response_message', 'updated_at'])
        merchant.last_error = err_msg[:1000]
        merchant.save(update_fields=['last_error', 'updated_at'])
        AepsApiAuditLog.objects.create(
            endpoint='onboarding/create',
            merchant_tran_id=txn.merchant_tran_id,
            user=user,
            success=False,
            provider_status_code=str(getattr(exc, 'status_code', '') or '')[:32],
            error_message=err_msg[:500],
            request_summary=scrub_sensitive(
                {
                    'merchantLoginId': merchant.merchant_login_id,
                    'companyType': fingpay_merchant.get('companyType'),
                    'merchantState': (fingpay_merchant.get('merchantAddress') or {}).get('merchantState'),
                    'onboarding_url': getattr(client, 'onboarding_base_url', ''),
                    'server_ip': '57.131.39.21',
                }
            ),
        )
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': err_msg}) from exc

    # Prefer nested data remarks when present
    data_obj = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    provider_message = str(
        resp.get('message') or data_obj.get('remarks') or data_obj.get('message') or ''
    ).strip()
    status_code = str(resp.get('statusCode') or '')
    error_codes = data_obj.get('errorCodes')
    if error_codes:
        provider_message = f'{provider_message} [errorCodes={error_codes}]'.strip()

    if status_code == '10005' or 'invalid super merchant' in provider_message.lower():
        provider_message = (
            'Invalid super merchant — Fingpay rejected Integration credentials. '
            'Use Production URL (fingpayap.tapits.in) with Super merchant login Mpayhubd / '
            'password 1234d / ID 1501 (not Analytics Portal Mpayhub). '
            f'Currently login={client.super_merchant_login_id!r} id={client.super_merchant_id!r} '
            f'url={client.onboarding_base_url!r}.'
        )
    elif status_code == '10004' and 'modelcreation' in provider_message.lower().replace(' ', ''):
        provider_message = (
            f'{provider_message} — usually bad request shape or credentials. '
            'Confirm Production provider password/login/id with Fingpay and share plain JSON '
            'request/response on the mail trail.'
        )

    # Map common Fingpay onboarding codes for clearer UI
    code_hints = {
        '5002': 'Merchant login pin missing',
        '5005': 'First name and last name cannot be the same',
        '5007': 'Merchant phone number invalid/missing',
        '5021': 'GSTIN is not valid — use a real GSTIN for the super merchant',
        '5022': 'CompanyOrShopPan is not valid',
        '5023': 'Merchant PAN image missing',
        '5024': 'Masked Aadhaar image missing',
        '5025': 'User PAN missing',
        '5041': 'Shop background image missing',
        '5043': 'Bank IFSC invalid',
    }
    if error_codes:
        hints = []
        for raw_code in str(error_codes).replace(' ', '').split(','):
            if raw_code and raw_code in code_hints:
                hints.append(f'{raw_code}: {code_hints[raw_code]}')
        if hints:
            provider_message = f"{provider_message} — {'; '.join(hints)}"

    ok = bool(resp.get('status') is True or resp.get('statusCode') in (10000, '10000'))
    if data_obj.get('merchantStatus') is False:
        ok = False
    txn.status = 'success' if ok else 'failed'
    txn.response_code = status_code
    txn.response_message = (provider_message or 'Onboarding failed')[:500]
    txn.provider_meta = scrub_sensitive(resp)
    txn.fp_transaction_id = str(data_obj.get('encodeFPTxnId') or resp.get('encodeFPTxnId') or '')
    txn.save()

    AepsApiAuditLog.objects.create(
        endpoint='onboarding/create',
        merchant_tran_id=txn.merchant_tran_id,
        user=user,
        success=ok,
        provider_status_code=txn.response_code,
        latency_ms=(resp.get('_meta') or {}).get('latency_ms'),
        request_summary=scrub_sensitive(
            {
                'merchantLoginId': merchant.merchant_login_id,
                'companyType': fingpay_merchant.get('companyType'),
                'merchantState': (fingpay_merchant.get('merchantAddress') or {}).get('merchantState'),
                'has_images': True,
            }
        ),
        response_summary=scrub_sensitive(
            {
                'status': resp.get('status'),
                'statusCode': resp.get('statusCode'),
                'message': provider_message,
                'errorCodes': error_codes,
            }
        ),
    )

    if ok:
        merchant.stage = 'ekyc_pending'
        merchant.fingpay_onboarding_ref = txn.fp_transaction_id or txn.merchant_tran_id
        merchant.onboarding_payload = {
            **(merchant.onboarding_payload or {}),
            **{k: flat.get(k) for k in DRAFT_KEYS if _safe_str(flat.get(k))},
            'aadhaarNumber': merchant.masked_aadhaar,
        }
        merchant.last_latitude = latitude
        merchant.last_longitude = longitude
        merchant.last_error = ''
        merchant.save()
    else:
        merchant.last_error = txn.response_message
        merchant.save(update_fields=['last_error', 'updated_at'])
        raise ValidationError(
            {
                'code': 'PROVIDER_REJECTED',
                'message': txn.response_message or 'Onboarding failed at Fingpay (modelCreation).',
            }
        )

    return {'transaction': _txn_dict(txn), 'merchant_stage': merchant.stage}


def ekyc_start(*, user, payload: dict, device_imei: str, latitude, longitude) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    client = get_fingpay_client()
    body = {
        'superMerchantId': int(client.super_merchant_id) if str(client.super_merchant_id).isdigit() else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'transactionType': 'EKY',
        'mobileNumber': payload.get('mobileNumber') or getattr(user, 'phone', ''),
        'aadharNumber': payload.get('aadhaarNumber') or payload.get('aadharNumber'),
        'panNumber': payload.get('panNumber'),
        'matmSerialNumber': payload.get('matmSerialNumber') or '',
        'latitude': float(latitude),
        'longitude': float(longitude),
    }
    if body['aadharNumber']:
        merchant.masked_aadhaar = mask_aadhaar(body['aadharNumber'])
    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=generate_merchant_tran_id('EKY'),
        product='EKY',
        status='pending',
        latitude=latitude,
        longitude=longitude,
        device_imei=device_imei or merchant.device_imei,
        masked_aadhaar=merchant.masked_aadhaar,
    )
    try:
        resp = client.ekyc_post('fpekyc/api/ekyc/merchant/php/sendotp', body, device_imei=device_imei or merchant.device_imei)
    except Exception as exc:
        txn.status = 'failed'
        txn.response_message = str(exc)[:500]
        txn.save()
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    data = resp.get('data') or {}
    merchant.ekyc_primary_key_id = str(data.get('primaryKeyId') or '')
    merchant.ekyc_encode_fp_txn_id = str(data.get('encodeFPTxnId') or '')
    merchant.stage = 'ekyc_pending'
    merchant.device_imei = device_imei or merchant.device_imei
    merchant.save()
    txn.fp_transaction_id = merchant.ekyc_encode_fp_txn_id
    txn.provider_meta = scrub_sensitive(resp)
    txn.response_code = str(resp.get('statusCode') or '')
    txn.response_message = str(resp.get('message') or '')[:500]
    txn.status = 'pending'
    txn.save()
    return {
        'transaction': _txn_dict(txn),
        'primaryKeyId': merchant.ekyc_primary_key_id,
        'encodeFPTxnId': merchant.ekyc_encode_fp_txn_id,
    }


def ekyc_verify_otp(*, user, otp: str) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    client = get_fingpay_client()
    body = {
        'superMerchantId': int(client.super_merchant_id) if str(client.super_merchant_id).isdigit() else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'otp': otp,
        'primaryKeyId': int(merchant.ekyc_primary_key_id) if str(merchant.ekyc_primary_key_id).isdigit() else merchant.ekyc_primary_key_id,
        'encodeFPTxnId': merchant.ekyc_encode_fp_txn_id,
    }
    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=generate_merchant_tran_id('EKY'),
        product='EKY',
        status='pending',
        device_imei=merchant.device_imei,
        masked_aadhaar=merchant.masked_aadhaar,
        fp_transaction_id=merchant.ekyc_encode_fp_txn_id or '',
    )
    try:
        resp = client.ekyc_post('fpekyc/api/ekyc/merchant/php/validateotp', body, device_imei=merchant.device_imei)
    except Exception as exc:
        txn.status = 'failed'
        txn.response_message = str(exc)[:500]
        txn.save()
        AepsApiAuditLog.objects.create(
            endpoint='ekyc/validateotp',
            merchant_tran_id=txn.merchant_tran_id,
            user=user,
            success=False,
            error_message=str(exc)[:500],
        )
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    ok = bool(resp.get('status') is True or str(resp.get('statusCode')) == '10000')
    txn.status = 'success' if ok else 'failed'
    txn.response_code = str(resp.get('statusCode') or '')
    txn.response_message = str(resp.get('message') or '')[:500]
    txn.provider_meta = scrub_sensitive(resp)
    txn.save()
    AepsApiAuditLog.objects.create(
        endpoint='ekyc/validateotp',
        merchant_tran_id=txn.merchant_tran_id,
        user=user,
        success=ok,
        provider_status_code=txn.response_code,
        response_summary=scrub_sensitive({'status': resp.get('status'), 'statusCode': resp.get('statusCode')}),
    )
    if not ok:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': txn.response_message or 'OTP validation failed'})
    meta = dict(merchant.onboarding_payload or {})
    meta['ekyc_otp_validated'] = True
    merchant.onboarding_payload = meta
    merchant.save(update_fields=['onboarding_payload', 'updated_at'])
    return {'ok': True, 'transaction': _txn_dict(txn), 'provider': scrub_sensitive(resp)}


def ekyc_resend_otp(*, user) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    if not merchant.ekyc_primary_key_id or not merchant.ekyc_encode_fp_txn_id:
        raise ValidationError({'message': 'Start eKYC (send OTP) before resending.'})
    client = get_fingpay_client()
    body = {
        'superMerchantId': int(client.super_merchant_id) if str(client.super_merchant_id).isdigit() else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'primaryKeyId': int(merchant.ekyc_primary_key_id) if str(merchant.ekyc_primary_key_id).isdigit() else merchant.ekyc_primary_key_id,
        'encodeFPTxnId': merchant.ekyc_encode_fp_txn_id,
    }
    try:
        resp = client.ekyc_post('fpekyc/api/ekyc/merchant/php/resendotp', body, device_imei=merchant.device_imei)
    except Exception as exc:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc
    ok = bool(resp.get('status') is True or str(resp.get('statusCode')) == '10000')
    if not ok:
        raise ValidationError(
            {'code': 'PROVIDER_REJECTED', 'message': str(resp.get('message') or 'Resend OTP failed')}
        )
    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    if data.get('primaryKeyId'):
        merchant.ekyc_primary_key_id = str(data.get('primaryKeyId'))
    if data.get('encodeFPTxnId'):
        merchant.ekyc_encode_fp_txn_id = str(data.get('encodeFPTxnId'))
        merchant.save(update_fields=['ekyc_primary_key_id', 'ekyc_encode_fp_txn_id', 'updated_at'])
    return {
        'ok': True,
        'primaryKeyId': merchant.ekyc_primary_key_id,
        'encodeFPTxnId': merchant.ekyc_encode_fp_txn_id,
        'provider': scrub_sensitive(resp),
    }


def ekyc_status_check(*, user, kyc_type: str = 'EKYC') -> dict:
    """EKYC / Bank KYC status check — fpekyc/api/ekyc/status/check"""
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    client = get_fingpay_client()
    kyc_type = (kyc_type or 'EKYC').strip() or 'EKYC'
    body = {
        'superMerchantId': int(client.super_merchant_id) if str(client.super_merchant_id).isdigit() else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'kycType': kyc_type,
    }
    if merchant.ekyc_encode_fp_txn_id:
        body['encodeFPTxnId'] = merchant.ekyc_encode_fp_txn_id
    if merchant.ekyc_primary_key_id:
        body['primaryKeyId'] = (
            int(merchant.ekyc_primary_key_id)
            if str(merchant.ekyc_primary_key_id).isdigit()
            else merchant.ekyc_primary_key_id
        )
    try:
        resp = client.ekyc_post('fpekyc/api/ekyc/status/check', body, device_imei=merchant.device_imei or 'UNKNOWN')
    except Exception as exc:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc
    return scrub_sensitive(resp)


def ekyc_biometric(*, user, capture_response: dict, latitude, longitude) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    client = get_fingpay_client()
    body = {
        'superMerchantId': int(client.super_merchant_id) if str(client.super_merchant_id).isdigit() else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'primaryKeyId': int(merchant.ekyc_primary_key_id) if str(merchant.ekyc_primary_key_id).isdigit() else merchant.ekyc_primary_key_id,
        'encodeFPTxnId': merchant.ekyc_encode_fp_txn_id,
        'captureResponse': capture_response,
        'latitude': float(latitude),
        'longitude': float(longitude),
    }
    # Pass captureResponse through unchanged
    try:
        resp = client.ekyc_post('fpekyc/api/ekyc/merchant/php/biometric', body, device_imei=merchant.device_imei)
    except Exception as exc:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    ok = bool(resp.get('status') is True or str(resp.get('statusCode')) == '10000')
    data = resp.get('data') or {}
    kyc_code = str(data.get('kycResponseCode') or data.get('responseCode') or '')
    if ok and kyc_code in ('0', '00', ''):
        merchant.stage = 'active'
        merchant.activated_at = timezone.now()
        merchant.fingpay_ekyc_ref = str(data.get('fingpayTransactionId') or '')
        merchant.last_error = ''
        merchant.save()
    else:
        merchant.last_error = str(resp.get('message') or data.get('responseMessage') or 'eKYC failed')[:1000]
        merchant.save(update_fields=['last_error', 'updated_at'])

    txn = AepsTransaction.objects.filter(user=user, product='EKY').order_by('-created_at').first()
    if txn:
        txn.status = 'success' if merchant.stage == 'active' else 'failed'
        txn.response_code = kyc_code or str(resp.get('statusCode') or '')
        txn.response_message = str(resp.get('message') or data.get('responseMessage') or '')[:500]
        txn.fp_transaction_id = str(data.get('fingpayTransactionId') or txn.fp_transaction_id)
        txn.bank_rrn = str(data.get('rrn') or '')
        txn.provider_meta = scrub_sensitive(resp)
        txn.save()

    AepsApiAuditLog.objects.create(
        endpoint='ekyc/biometric',
        merchant_tran_id=txn.merchant_tran_id if txn else '',
        user=user,
        success=merchant.stage == 'active',
        response_summary=scrub_sensitive({'status': resp.get('status'), 'statusCode': resp.get('statusCode')}),
    )
    if merchant.stage != 'active':
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': merchant.last_error or 'eKYC failed'})
    return {'merchant_stage': merchant.stage, 'transaction': _txn_dict(txn) if txn else None}


def register_device(*, user, device_imei: str) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    serial = (device_imei or '').strip()
    if not serial:
        raise ValidationError({'message': 'Mantra device serial is required.'})
    merchant.device_imei = serial
    merchant.device_ready = True
    merchant.save(update_fields=['device_imei', 'device_ready', 'updated_at'])
    return {'device_imei': merchant.device_imei, 'device_ready': True}


def _txn_dict(txn: AepsTransaction | None) -> dict | None:
    if not txn:
        return None
    return {
        'id': txn.pk,
        'merchant_tran_id': txn.merchant_tran_id,
        'product': txn.product,
        'status': txn.status,
        'amount': str(txn.amount),
        'bank_rrn': txn.bank_rrn,
        'fp_transaction_id': txn.fp_transaction_id,
        'response_code': txn.response_code,
        'response_message': txn.response_message,
        'masked_aadhaar': txn.masked_aadhaar,
        'created_at': txn.created_at.isoformat() if txn.created_at else None,
    }
