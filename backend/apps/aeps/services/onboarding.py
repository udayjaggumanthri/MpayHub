"""Merchant onboarding + eKYC orchestration."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.aeps.models import AepsApiAuditLog, AepsTransaction
from apps.aeps.services.gates import assert_entitled, get_merchant
from apps.aeps.services.ids import generate_merchant_tran_id, merchant_pin_plain
from apps.core.utils import decrypt_secret_payload, encrypt_secret_payload
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

# Large base64 KYC images — never include raw content in GET /me/status or GET draft list payloads.
IMAGE_DRAFT_KEYS = (
    'merchantPanImage',
    'maskedAadharImage',
    'backgroundImageOfShop',
)

# Cap base64 (~135–150KB JPEG) so Fingpay/UAT POSTs stay fast. UI compresses to ≤180k chars.
_MAX_KYC_IMAGE_B64_LEN = 200_000
# Minimum decoded-ish length for a real KYC photo (reject tiny placeholders).
_MIN_KYC_IMAGE_B64_LEN = 2000

AADHAAR_ENC_KEY = '_aadhaar_enc'


def _store_aadhaar_encrypted(merchant, aadhaar: str) -> None:
    digits = ''.join(c for c in str(aadhaar or '') if c.isdigit())
    if len(digits) != 12:
        return
    payload = dict(merchant.onboarding_payload or {})
    payload[AADHAAR_ENC_KEY] = encrypt_secret_payload({'v': digits})
    merchant.onboarding_payload = payload


def _load_stored_aadhaar(merchant) -> str:
    enc = (merchant.onboarding_payload or {}).get(AADHAAR_ENC_KEY)
    if enc:
        val = (decrypt_secret_payload(enc) or {}).get('v') or ''
        digits = ''.join(c for c in str(val) if c.isdigit())
        if len(digits) == 12:
            return digits
    kyc = getattr(merchant.user, 'kyc', None)
    if kyc and kyc.aadhaar_verified:
        digits = ''.join(c for c in str(kyc.aadhaar or '') if c.isdigit())
        if len(digits) == 12:
            return digits
    return ''


def _has_stored_aadhaar(merchant) -> bool:
    return bool(_load_stored_aadhaar(merchant))


def _strip_internal_onboarding(payload: dict | None) -> dict:
    out = dict(payload or {})
    out.pop(AADHAAR_ENC_KEY, None)
    return out


def _fingpay_ok(resp: dict | None) -> bool:
    if not isinstance(resp, dict):
        return False
    return resp.get('status') is True or str(resp.get('statusCode')) == '10000'


def _safe_str(value) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    if text.lower() in ('[redacted]', 'none', 'null'):
        return ''
    return text


def _is_image_payload(value) -> bool:
    text = _safe_str(value)
    if not text:
        return False
    if text.startswith('data:image') or text.startswith('data:application'):
        return True
    # Raw base64 KYC images are typically tens of KB+.
    return len(text) > 500


def _strip_images_for_client(form: dict) -> tuple[dict, dict]:
    """Return (client_form without image blobs, saved_images flags)."""
    out = dict(form or {})
    saved = {}
    for key in IMAGE_DRAFT_KEYS:
        present = _is_image_payload(out.get(key))
        saved[key] = present
        out[key] = ''
    return out, saved


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
    # Drop oversized KYC base64 left from older uploads so the UI asks for a compact re-pick.
    payload = dict(merchant.onboarding_payload or {})
    dropped = False
    for key in IMAGE_DRAFT_KEYS:
        raw = _safe_str(payload.get(key))
        if raw.startswith('data:') and ',' in raw:
            raw = raw.split(',', 1)[1]
        raw = ''.join(raw.split())
        if raw and len(raw) > _MAX_KYC_IMAGE_B64_LEN:
            payload.pop(key, None)
            dropped = True
    if dropped:
        merchant.onboarding_payload = payload
        merchant.save(update_fields=['onboarding_payload', 'updated_at'])
    draft = flatten_onboarding_payload(merchant.onboarding_payload)
    prefill = build_onboarding_prefill(user)
    # Draft wins over prefill; empty draft keys filled from profile.
    merged = dict(prefill['fields'])
    for key, value in draft.items():
        if _safe_str(value):
            merged[key] = _safe_str(value)

    from apps.aeps.services.masters import (
        fetch_company_types,
        fetch_states,
        resolve_company_type,
        resolve_state_id,
    )

    states = fetch_states()
    company_types = fetch_company_types()
    # Normalize state names in merged form to stateId when possible
    for key in ('merchantState', 'shopState'):
        sid = resolve_state_id(merged.get(key), states)
        if sid is not None:
            merged[key] = str(sid)
    # Legacy drafts stored master row id; Fingpay needs MCC code (e.g. 4812)
    mcc = resolve_company_type(merged.get('companyType'), company_types)
    if mcc is not None:
        merged['companyType'] = str(mcc)

    has_draft = any(_safe_str(draft.get(k)) for k in DRAFT_KEYS if k not in IMAGE_DRAFT_KEYS and k != 'aadhaarNumber')
    has_draft = has_draft or any(_is_image_payload(draft.get(k)) for k in IMAGE_DRAFT_KEYS)
    client_form, saved_images = _strip_images_for_client(merged)
    client_draft, _ = _strip_images_for_client(draft)
    return {
        'stage': merchant.stage,
        'merchant_login_id': merchant.merchant_login_id,
        'masked_aadhaar': merchant.masked_aadhaar or '',
            'device_imei': merchant.device_imei or '',
            'scanner_serial': merchant.scanner_serial or '',
            'device_ready': bool(merchant.device_ready),
        'form': client_form,
        'draft': client_draft,
        'saved_images': saved_images,
        'prefill': prefill,
        'masters': {
            'states': states,
            'company_types': company_types,
        },
        'has_saved_draft': has_draft or merchant.stage == 'onboarding_draft',
        'last_error': merchant.last_error or '',
        'has_stored_aadhaar': _has_stored_aadhaar(merchant),
        'scanner_serial': merchant.scanner_serial or '',
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
    aadhaar_digits = ''.join(c for c in aadhaar if c.isdigit())
    if aadhaar and not aadhaar.lower().startswith('x') and aadhaar_digits.isdigit() and len(aadhaar_digits) == 12:
        _store_aadhaar_encrypted(merchant, aadhaar_digits)
        merchant.masked_aadhaar = mask_aadhaar(aadhaar_digits)
        flat['aadhaarNumber'] = merchant.masked_aadhaar
    elif aadhaar and not aadhaar.lower().startswith('x') and aadhaar.isdigit() and len(aadhaar) >= 4:
        merchant.masked_aadhaar = mask_aadhaar(aadhaar)
        flat['aadhaarNumber'] = merchant.masked_aadhaar
    elif merchant.masked_aadhaar:
        flat['aadhaarNumber'] = merchant.masked_aadhaar

    # Drop empty keys so we don't wipe good values with blanks on partial saves
    incoming = {k: v for k, v in flat.items() if _safe_str(v)}
    # Reject oversized base64 early (UI compresses; old drafts may still be huge).
    for key in IMAGE_DRAFT_KEYS:
        if key in incoming and _is_image_payload(incoming.get(key)):
            incoming[key] = _normalize_image_b64(incoming[key], field_name=key, required=False)
    # Never clear previously saved KYC images when the client omits them (slim GET form).
    stored = flatten_onboarding_payload(merchant.onboarding_payload)
    drop_oversized: list[str] = []
    for key in IMAGE_DRAFT_KEYS:
        if key not in incoming and _is_image_payload(stored.get(key)):
            try:
                incoming[key] = _normalize_image_b64(stored[key], field_name=key, required=False)
            except ValidationError:
                # Force re-upload in the UI (saved_images flips off after we drop the key).
                drop_oversized.append(key)
    # Keep encrypted aadhaar blob across merges (incoming flat never includes it).
    enc_blob = (merchant.onboarding_payload or {}).get(AADHAAR_ENC_KEY)
    merchant.onboarding_payload = {**(merchant.onboarding_payload or {}), **incoming}
    for key in drop_oversized:
        merchant.onboarding_payload.pop(key, None)
    if enc_blob and AADHAAR_ENC_KEY not in merchant.onboarding_payload:
        merchant.onboarding_payload[AADHAAR_ENC_KEY] = enc_blob
    if merchant.stage in ('not_started', ''):
        merchant.stage = 'onboarding_draft'
    merchant.save()
    light_payload, saved_images = _strip_images_for_client(
        flatten_onboarding_payload(merchant.onboarding_payload)
    )
    return {
        'stage': merchant.stage,
        'onboarding_payload': light_payload,
        'saved_images': saved_images,
        'masked_aadhaar': merchant.masked_aadhaar,
    }


def get_onboarding_image(*, user, field: str) -> dict:
    """Return one stored KYC image as raw base64 for preview / JPG download in the browser."""
    assert_entitled(user)
    key = _safe_str(field)
    if key not in IMAGE_DRAFT_KEYS:
        raise ValidationError({'message': 'Unknown image field.'})
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    flat = flatten_onboarding_payload(merchant.onboarding_payload)
    raw = _safe_str(flat.get(key))
    if raw.startswith('data:') and ',' in raw:
        raw = raw.split(',', 1)[1]
    raw = ''.join(raw.split())
    if not _is_image_payload(raw):
        raise ValidationError({'message': f'No saved {key} yet.'})
    return {'field': key, 'base64': raw, 'mime': 'image/jpeg'}


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


def _sanitize_address(value: str, *, minimum: int = 11, pad_from: str = '') -> str:
    """
    Fingpay 5009/5036 reject special chars (e.g. &, (), quotes).
    Keep letters/digits/spaces and common street punctuation only.
    """
    import re

    text = _safe_str(value)
    text = text.replace('&', ' and ')
    text = re.sub(r'[^A-Za-z0-9\s,.\-/#]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip(' ,.-/#')
    return _ensure_min_len(text, minimum, pad_from=pad_from)


# Minimum decoded-ish length for a real KYC photo (reject tiny placeholders).
# Cap / min lengths defined near IMAGE_DRAFT_KEYS at module top.


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
            # Doc sample MerchantModelV1.userType (e.g. "lakshmi")
            'userType': _safe_str(secrets.get('user_type') or secrets.get('userType')) or 'lakshmi',
        }
    except Exception:
        return {'gstinNumber': '', 'companyOrShopPan': '', 'userType': 'lakshmi'}


def _normalize_image_b64(value, *, field_name: str, required: bool = True) -> str:
    """
    Return raw base64 only (strip data-URL prefix). Simple API curl sample sends full JPEG/PNG base64.
    """
    raw = _safe_str(value)
    if raw.startswith('data:') and ',' in raw:
        raw = raw.split(',', 1)[1]
    raw = ''.join(raw.split())
    if len(raw) > _MAX_KYC_IMAGE_B64_LEN:
        raise ValidationError(
            {
                'code': 'KYC_IMAGE_TOO_LARGE',
                'message': (
                    f'{field_name} is too large for Fingpay onboarding '
                    f'({len(raw)} base64 chars). Re-pick the photo so the app converts it to compact base64, then submit.'
                ),
            }
        )
    if len(raw) >= _MIN_KYC_IMAGE_B64_LEN:
        return raw
    if required:
        raise ValidationError(
            {
                'code': 'KYC_IMAGE_REQUIRED',
                'message': (
                    f'{field_name} must be a full base64 image (not a flag or tiny placeholder). '
                    'Re-upload the photo and submit again.'
                ),
            }
        )
    return raw


def _image_b64(flat: dict, key: str, *, required: bool = True) -> str:
    labels = {
        'merchantPanImage': 'PAN image (kyc.merchantPanImage)',
        'maskedAadharImage': 'Masked Aadhaar image (kyc.maskedAadharImage)',
        'backgroundImageOfShop': 'Shop background image (merchantKycAddressData.backgroundImageOfShop)',
    }
    return _normalize_image_b64(flat.get(key), field_name=labels.get(key, key), required=required)


def _use_plain_merchant_pin() -> bool:
    """Simple API field table + curl.txt use plain merchantLoginPin; encrypted sample uses MD5."""
    try:
        client = get_fingpay_client()
        return getattr(client, 'api_mode', '') == 'simple' or getattr(client, 'onboarding_api_style', '') == 'simple'
    except Exception:
        return False


def build_fingpay_merchant_payload(*, merchant, flat: dict, latitude, longitude, aadhaar_full: str = '') -> dict:
    """
    Build MerchantModelV1 per Fingpay Services API Doc / Simple API curl sample.
    merchantState / shopState = getstates stateId; companyType = MCC code from companyType master.
    """
    from apps.aeps.services.masters import fetch_company_types, fetch_states, resolve_company_type, resolve_state_id
    from apps.integrations.fingpay.crypto import md5_hex

    states = fetch_states()
    company_types = fetch_company_types()
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

    company_type = resolve_company_type(flat.get('companyType'), company_types)
    if company_type is None:
        raise ValidationError(
            {
                'code': 'INVALID_COMPANY_TYPE',
                'message': (
                    'Select company / shop category from the Fingpay master list. '
                    'companyType must be the MCC code (e.g. 4812), not the list row id.'
                ),
            }
        )

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

    addr2 = _sanitize_address(
        flat.get('merchantAddress2') or '',
        minimum=11,
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
    # Simple API curl.txt + field table: plain PIN. Encrypted SAMPLE REQUEST: MD5 hex.
    if _use_plain_merchant_pin():
        pin_for_fingpay = pin
    else:
        pin_for_fingpay = md5_hex(pin) if len(pin) != 32 else pin

    aadhaar_raw = _safe_str(aadhaar_full or flat.get('aadhaarNumber'))
    if 'x' in aadhaar_raw.lower():
        raise ValidationError(
            {
                'code': 'AADHAAR_REQUIRED',
                'message': 'Enter the full 12-digit Aadhaar number (masked values like xxxxxxxx8750 are rejected).',
            }
        )
    aadhaar = ''.join(c for c in aadhaar_raw if c.isdigit())
    if len(aadhaar) != 12:
        raise ValidationError(
            {
                'code': 'AADHAAR_REQUIRED',
                'message': 'Enter the full 12-digit Aadhaar number (masked values like xxxxxxxx8750 are rejected).',
            }
        )
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

    pan_image = _image_b64(flat, 'merchantPanImage')
    aadhaar_image = _image_b64(flat, 'maskedAadharImage')
    shop_image = _image_b64(flat, 'backgroundImageOfShop')

    payload = {
        'merchantLoginId': merchant.merchant_login_id,
        'merchantLoginPin': pin_for_fingpay,
        'firstName': first,
        'lastName': last,
        'middleName': middle,
        'merchantPhoneNumber': _safe_str(flat.get('merchantPhoneNumber'))[-10:],
        'merchantAddress': {
            # Fingpay 5009/5036: no special chars (&, parentheses, etc.); min length.
            'merchantAddress1': _sanitize_address(
                flat.get('merchantAddress1'),
                minimum=11,
                pad_from=f"{flat.get('merchantCityName') or ''} {flat.get('merchantDistrictName') or ''}",
            ),
            'merchantAddress2': addr2,
            'merchantState': int(state_id),
            'merchantCityName': _safe_str(flat.get('merchantCityName')),
            'merchantDistrictName': _safe_str(flat.get('merchantDistrictName')),
            'merchantPinCode': _safe_str(flat.get('merchantPinCode')),
        },
        'companyLegalName': legal[:100],
        # Present in MerchantModelV1 + SAMPLE REQUEST (Fingpay Services API Doc 270426)
        'userType': _safe_str(flat.get('userType')) or defaults.get('userType') or 'lakshmi',
        'companyType': int(company_type),
        'emailId': _safe_str(flat.get('emailId')),
        # Param table: True/False. Sample also shows "yes" — True/False is documented.
        'certificateOfIncorporationImage': 'True',
        'kyc': {
            'userPan': user_pan,
            'aadhaarNumber': aadhaar,
            # Java model: private String gstinNumber (param table also writes gstInNumber)
            'gstinNumber': gstin,
            'companyOrShopPan': company_pan,
            'merchantPanImage': pan_image,
            'maskedAadharImage': aadhaar_image,
            'shopAndPanImage': 'True',
        },
        'settlementV1': {
            'companyBankAccountNumber': _safe_str(flat.get('companyBankAccountNumber')),
            'bankIfscCode': _safe_str(flat.get('bankIfscCode')).upper(),
            'companyBankName': _safe_str(flat.get('companyBankName') or 'State Bank of India'),
            # Param table 13.4 (optional in sample JSON)
            'bankBranchName': _safe_str(flat.get('bankBranchName') or flat.get('companyBankName') or 'Main'),
            'bankAccountName': _safe_str(flat.get('bankAccountName')),
        },
        'tradeBusinessProof': 'True',
        'termsConditionCheck': 'True',
        'cancelledChequeImages': 'True',
        'physicalVerification': 'True',
        # Java model / param table: videoKycWithLatLongData
        'videoKycWithLatLongData': 'True',
        'merchantKycAddressData': {
            'shopAddress': _sanitize_address(
                flat.get('shopAddress'),
                minimum=11,
                pad_from=f"{flat.get('shopCity') or ''} {flat.get('shopDistrict') or ''}",
            ),
            'shopCity': _safe_str(flat.get('shopCity')),
            'shopDistrict': _safe_str(flat.get('shopDistrict')),
            'shopState': int(shop_state_id),
            'shopPincode': _safe_str(flat.get('shopPincode')),
            'shopLatitude': shop_lat,
            'shopLongitude': shop_lng,
            'backgroundImageOfShop': shop_image,
        },
    }
    # Encrypted SAMPLE REQUEST sometimes uses typo key "vedio..."; Simple curl.txt does not.
    if not _use_plain_merchant_pin():
        payload['vedioKycWithLatLongData'] = 'True'
    return payload


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
    # Reuse previously saved KYC images when the slim form does not re-upload them.
    stored = flatten_onboarding_payload(merchant.onboarding_payload)
    for key in IMAGE_DRAFT_KEYS:
        if not _is_image_payload(flat.get(key)) and _is_image_payload(stored.get(key)):
            flat[key] = stored[key]
    if isinstance(raw.get('kyc'), dict):
        for k in ('userPan', 'aadhaarNumber', 'gstinNumber', 'gstInNumber', 'companyOrShopPan'):
            if raw['kyc'].get(k):
                flat['gstinNumber' if k == 'gstInNumber' else k] = _safe_str(raw['kyc'].get(k))
        for k in IMAGE_DRAFT_KEYS:
            if _is_image_payload(raw['kyc'].get(k)):
                flat[k] = _safe_str(raw['kyc'].get(k))
    if raw.get('companyType') not in (None, ''):
        flat['companyType'] = _safe_str(raw.get('companyType'))
    if raw.get('companyLegalName'):
        flat['companyLegalName'] = _safe_str(raw.get('companyLegalName'))

    aadhaar_full = ''
    if isinstance(raw.get('kyc'), dict):
        aadhaar_full = _safe_str(raw['kyc'].get('aadhaarNumber'))
    aadhaar_full = aadhaar_full or _safe_str(raw.get('aadhaarNumber')) or _safe_str(flat.get('aadhaarNumber'))
    aadhaar_full = ''.join(c for c in aadhaar_full if c.isdigit())
    # Draft GET returns a masked value; reuse encrypted / KYC-stored full Aadhaar when present.
    if len(aadhaar_full) != 12:
        aadhaar_full = _load_stored_aadhaar(merchant)
    if len(aadhaar_full) != 12:
        raise ValidationError(
            {
                'code': 'AADHAAR_REQUIRED',
                'message': (
                    'Enter the full 12-digit Aadhaar number (masked values like xxxxxxxx8750 are rejected). '
                    'Save draft once with the full number, then submit again.'
                ),
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
        # Always use the admin-selected Java/.NET or PHP encrypted create URL.
        # (Do not auto-switch to /simple/creation just because the host is fpuat —
        # that hid the request/response pack shape and ignored the Activate cards.)
        resp = client.create_merchant(
            fingpay_merchant,
            latitude=latitude,
            longitude=longitude,
            ip_address=ip_address or getattr(client, 'egress_ip', '') or '0.0.0.0',
        )
    except Exception as exc:
        from apps.integrations.fingpay.client import FingpayClientError

        err_msg = str(exc)
        exchange = getattr(exc, 'exchange', None) if isinstance(exc, FingpayClientError) else None
        if not exchange and isinstance(exc, FingpayClientError) and isinstance(exc.payload, dict):
            exchange = exc.payload.get('exchange')
        egress = getattr(client, 'egress_ip', '') or '139.99.47.143'
        if isinstance(exc, FingpayClientError) and exc.status_code == 403:
            err_msg = (
                'Fingpay blocked our server (HTTP 403). '
                f'IP {egress} is not whitelisted on the active host yet. '
                'Ask Tapits to whitelist this IP — then retry Submit. '
                'Your form data is fine; this is not a merchant-field validation error. '
                'Copy the Request/Response pack below and send it to Tapits.'
            )
        txn.status = 'failed'
        txn.response_code = str(getattr(exc, 'status_code', '') or '')
        txn.response_message = err_msg[:500]
        if exchange:
            # Never persist full KYC base64 inside provider_meta (DB bloat / slow saves).
            txn.provider_meta = {
                **(txn.provider_meta or {}),
                'fingpay_exchange': scrub_sensitive(exchange, for_tapits=False),
            }
        txn.save(update_fields=['status', 'response_code', 'response_message', 'provider_meta', 'updated_at'])
        merchant.last_error = err_msg[:1000]
        merchant.save(update_fields=['last_error', 'updated_at'])
        AepsApiAuditLog.objects.create(
            endpoint='onboarding/create',
            merchant_tran_id=txn.merchant_tran_id,
            user=user,
            success=False,
            http_status=getattr(exc, 'status_code', None) if isinstance(exc, FingpayClientError) else None,
            provider_status_code=str(getattr(exc, 'status_code', '') or '')[:32],
            error_message=err_msg[:500],
            request_summary=scrub_sensitive(
                {
                    'merchantLoginId': merchant.merchant_login_id,
                    'companyType': fingpay_merchant.get('companyType'),
                    'merchantState': (fingpay_merchant.get('merchantAddress') or {}).get('merchantState'),
                    'onboarding_url': getattr(client, 'onboarding_base_url', ''),
                    'server_ip': egress,
                    'api_mode': getattr(client, 'api_mode', ''),
                    'url': (exchange or {}).get('request', {}).get('url') if exchange else None,
                }
            ),
            response_summary=scrub_sensitive(exchange or {}, for_tapits=False),
        )
        # NOTE: don't put the exchange inside ValidationError detail — DRF coerces
        # every leaf (ints/bools/floats) to ErrorDetail strings and wrecks the JSON.
        # UI exchange is scrubbed in views._exc_exchange; keep raw only on the exception.
        err = ValidationError({'code': 'PROVIDER_REJECTED', 'message': err_msg})
        err.fingpay_exchange = scrub_sensitive(exchange or {}, for_tapits=False)
        raise err from exc

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
        env_label = (getattr(client, 'environment', '') or '').upper() or 'ACTIVE'
        style = getattr(client, 'onboarding_api_style', '') or ''
        create_url = ''
        try:
            create_url = client.onboarding_create_url()
        except Exception:
            create_url = getattr(client, 'onboarding_base_url', '')
        if 'fpuat' in (create_url or '').lower() or env_label == 'UAT':
            provider_message = (
                'Invalid super merchant — Fingpay rejected these UAT Integration credentials (10005). '
                'Ask Tapits for a UAT SuperMerchant login/ID/password (Production Mpayhubd/1501 is not valid on fpuat), '
                'save them under Admin → AEPS Provider → UAT, then retry. '
                f'Currently env={env_label!r} style={style!r} login={client.super_merchant_login_id!r} '
                f'id={client.super_merchant_id!r} url={create_url!r}.'
            )
        else:
            provider_message = (
                'Invalid super merchant — Fingpay rejected Integration credentials. '
                'Use Production URL (fingpayap.tapits.in) with Super merchant login Mpayhubd / '
                'password 1234d / ID 1501 (not Analytics Portal Mpayhub). '
                f'Currently login={client.super_merchant_login_id!r} id={client.super_merchant_id!r} '
                f'url={create_url!r}.'
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
        '5009': 'Merchant address line 1 not valid — avoid special characters like & ( ) and use a plain street address',
        '5036': 'Shop address not valid — avoid special characters like & ( ) and use a plain outlet address',
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
    exchange = resp.get('_exchange') if isinstance(resp, dict) else None
    txn.status = 'success' if ok else 'failed'
    txn.response_code = status_code
    txn.response_message = (provider_message or 'Onboarding failed')[:500]
    meta = scrub_sensitive({k: v for k, v in (resp or {}).items() if k != '_exchange'})
    if exchange:
        meta['fingpay_exchange'] = scrub_sensitive(exchange, for_tapits=False)
    txn.provider_meta = meta
    txn.fp_transaction_id = str(data_obj.get('encodeFPTxnId') or resp.get('encodeFPTxnId') or '')
    txn.save()

    AepsApiAuditLog.objects.create(
        endpoint='onboarding/create',
        merchant_tran_id=txn.merchant_tran_id,
        user=user,
        success=ok,
        http_status=(resp.get('_meta') or {}).get('http_status'),
        provider_status_code=txn.response_code,
        latency_ms=(resp.get('_meta') or {}).get('latency_ms'),
        request_summary=scrub_sensitive(
            {
                'merchantLoginId': merchant.merchant_login_id,
                'companyType': fingpay_merchant.get('companyType'),
                'merchantState': (fingpay_merchant.get('merchantAddress') or {}).get('merchantState'),
                'has_images': True,
                'onboarding_url': getattr(client, 'onboarding_base_url', ''),
                'onboarding_api_style': getattr(client, 'onboarding_api_style', ''),
                'url': (exchange or {}).get('request', {}).get('url') if exchange else None,
            }
        ),
        response_summary=scrub_sensitive(
            {
                'status': resp.get('status'),
                'statusCode': resp.get('statusCode'),
                'message': provider_message,
                'errorCodes': error_codes,
                'exchange': exchange or {},
            }
        ),
    )

    if ok:
        merchant.stage = 'ekyc_pending'
        merchant.fingpay_onboarding_ref = txn.fp_transaction_id or txn.merchant_tran_id
        merchant.onboarding_payload = {
            **_strip_internal_onboarding(merchant.onboarding_payload),
            **{k: flat.get(k) for k in DRAFT_KEYS if _safe_str(flat.get(k))},
            'aadhaarNumber': merchant.masked_aadhaar,
        }
        _store_aadhaar_encrypted(merchant, aadhaar_full)
        merchant.last_latitude = latitude
        merchant.last_longitude = longitude
        merchant.last_error = ''
        merchant.save()
    else:
        merchant.last_error = txn.response_message
        merchant.save(update_fields=['last_error', 'updated_at'])
        err = ValidationError(
            {
                'code': 'PROVIDER_REJECTED',
                'message': txn.response_message or 'Onboarding failed at Fingpay (modelCreation).',
            }
        )
        # Preserve typed exchange for frontend Copy pack (any failure, incl. 10005 on UAT).
        err.fingpay_exchange = exchange or {}
        raise err

    return {'transaction': _txn_dict(txn), 'merchant_stage': merchant.stage}


def reset_merchant_pin_via_onboarding(*, merchant, new_pin: str = '') -> dict:
    """
    Re-hit Simple onboarding create with the stored PIN so Fingpay can reset
    merchantLoginPin (Tapits 14 Aug 2026). Does not change eKYC/active stage.
    Optional new_pin replaces the stored PIN before the re-hit.
    """
    from apps.integrations.fingpay.client import FingpayClientError

    pin = str(new_pin or '').strip()
    if pin:
        if not pin.isdigit() or not (4 <= len(pin) <= 8):
            raise ValidationError({'message': 'New PIN must be 4 to 8 digits.'})
        merchant.merchant_pin_encrypted = encrypt_secret_payload({'pin': pin})
        merchant.save(update_fields=['merchant_pin_encrypted', 'updated_at'])

    user = merchant.user
    flat = flatten_onboarding_payload(merchant.onboarding_payload)
    aadhaar_full = _load_stored_aadhaar(merchant)
    if len(aadhaar_full) != 12:
        raise ValidationError({'message': 'Stored Aadhaar is missing; cannot reset PIN via onboarding.'})
    latitude = merchant.last_latitude or 17.79
    longitude = merchant.last_longitude or 82.80
    fingpay_merchant = build_fingpay_merchant_payload(
        merchant=merchant,
        flat=flat,
        latitude=latitude,
        longitude=longitude,
        aadhaar_full=aadhaar_full,
    )
    client = get_fingpay_client()
    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=generate_merchant_tran_id('ONB'),
        product='ONB',
        status='pending',
        latitude=latitude,
        longitude=longitude,
        client_ip=getattr(client, 'egress_ip', '') or None,
        device_imei=merchant.device_imei or '',
        masked_aadhaar=merchant.masked_aadhaar,
    )
    try:
        resp = client.create_merchant(
            fingpay_merchant,
            latitude=latitude,
            longitude=longitude,
            ip_address=getattr(client, 'egress_ip', '') or '0.0.0.0',
        )
    except Exception as exc:
        err_msg = str(exc)[:500]
        exchange = getattr(exc, 'exchange', None) if isinstance(exc, FingpayClientError) else None
        txn.status = 'failed'
        txn.response_code = str(getattr(exc, 'status_code', '') or '')
        txn.response_message = err_msg
        if exchange:
            txn.provider_meta = {
                **(txn.provider_meta or {}),
                'fingpay_exchange': scrub_sensitive(exchange, for_tapits=False),
            }
        txn.save()
        merchant.last_error = err_msg[:1000]
        merchant.save(update_fields=['last_error', 'updated_at'])
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': err_msg}) from exc

    data_obj = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    ok = bool(resp.get('status') is True or resp.get('statusCode') in (10000, '10000'))
    if data_obj.get('merchantStatus') is False:
        ok = False
    provider_message = str(resp.get('message') or data_obj.get('remarks') or '')[:500]
    txn.status = 'success' if ok else 'failed'
    txn.response_code = str(resp.get('statusCode') or '')
    txn.response_message = provider_message or ('PIN reset via onboarding' if ok else 'Onboarding PIN reset failed')
    txn.provider_meta = scrub_sensitive({k: v for k, v in (resp or {}).items() if k != '_exchange'})
    txn.save()
    AepsApiAuditLog.objects.create(
        endpoint='onboarding/create',
        merchant_tran_id=txn.merchant_tran_id,
        user=user,
        success=ok,
        provider_status_code=txn.response_code,
        request_summary=scrub_sensitive(
            {
                'merchantLoginId': merchant.merchant_login_id,
                'purpose': 'reset_merchant_pin',
                'onboarding_url': getattr(client, 'onboarding_create_url', lambda: '')(),
            }
        ),
        response_summary=scrub_sensitive({'status': resp.get('status'), 'statusCode': resp.get('statusCode'), 'message': provider_message}),
    )
    if not ok:
        merchant.last_error = txn.response_message
        merchant.save(update_fields=['last_error', 'updated_at'])
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': txn.response_message})
    merchant.last_error = ''
    merchant.save(update_fields=['last_error', 'updated_at'])
    return {
        'ok': True,
        'merchant_login_id': merchant.merchant_login_id,
        'status_code': txn.response_code,
        'message': txn.response_message,
        'url': client.onboarding_create_url(),
        'merchant_stage': merchant.stage,
    }


def ekyc_start(*, user, payload: dict, device_imei: str, latitude, longitude) -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    imei = _safe_str(device_imei or merchant.device_imei).strip()
    if not imei:
        raise ValidationError(
            {
                'code': 'DEVICE_IMEI_REQUIRED',
                'message': (
                    'Phone/tablet IMEI is required for Fingpay eKYC (deviceIMEI header). '
                    'Open AEPS → Device and save your device IMEI (15 digits, e.g. from phone settings).'
                ),
            }
        )
    client = get_fingpay_client()
    aadhaar_raw = _safe_str(payload.get('aadhaarNumber') or payload.get('aadharNumber'))
    aadhaar = ''.join(c for c in aadhaar_raw if c.isdigit())
    if len(aadhaar) != 12:
        aadhaar = _load_stored_aadhaar(merchant)
    if len(aadhaar) != 12:
        raise ValidationError(
            {
                'code': 'AADHAAR_REQUIRED',
                'message': (
                    'Aadhaar from onboarding is not available. Enter the full 12-digit Aadhaar once for eKYC.'
                    if merchant.masked_aadhaar
                    else 'Enter the full 12-digit Aadhaar number before starting eKYC.'
                ),
            }
        )
    pan = _safe_str(payload.get('panNumber')).upper()
    if not pan:
        flat = flatten_onboarding_payload(merchant.onboarding_payload)
        pan = _safe_str(flat.get('userPan')).upper()
    if not pan:
        raise ValidationError({'code': 'PAN_REQUIRED', 'message': 'PAN is required for eKYC send OTP.'})
    mobile = _safe_str(payload.get('mobileNumber') or getattr(user, 'phone', ''))[-10:]
    if len(mobile) != 10:
        flat = flatten_onboarding_payload(merchant.onboarding_payload)
        mobile = _safe_str(flat.get('merchantPhoneNumber') or getattr(user, 'phone', ''))[-10:]
    if len(mobile) != 10:
        raise ValidationError({'code': 'MOBILE_REQUIRED', 'message': 'Valid 10-digit mobile number is required.'})

    scanner_serial = _safe_str(payload.get('matmSerialNumber') or merchant.scanner_serial)

    # Field order matches verified Simple API curl (hash is sensitive to exact JSON string).
    body = {
        'superMerchantId': int(client.super_merchant_id)
        if str(client.super_merchant_id).isdigit()
        else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'transactionType': 'EKY',
        'mobileNumber': mobile,
        'aadharNumber': aadhaar,
        'panNumber': pan,
        'matmSerialNumber': scanner_serial,
        'latitude': float(latitude),
        'longitude': float(longitude),
    }
    _store_aadhaar_encrypted(merchant, aadhaar)
    merchant.masked_aadhaar = mask_aadhaar(aadhaar)
    merchant.device_imei = imei
    merchant.device_ready = True
    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=generate_merchant_tran_id('EKY'),
        product='EKY',
        status='pending',
        latitude=latitude,
        longitude=longitude,
        device_imei=imei,
        masked_aadhaar=merchant.masked_aadhaar,
    )
    try:
        resp = client.ekyc_post(
            client.endpoint('ekyc_send_otp', 'fpekyc/api/ekyc/merchant/v1/sendotp'),
            body,
            device_imei=imei,
            endpoint_key='ekyc_send_otp',
        )
    except Exception as exc:
        txn.status = 'failed'
        txn.response_message = str(exc)[:500]
        txn.save()
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    ok = _fingpay_ok(resp)
    data = resp.get('data') or {}
    txn.fp_transaction_id = str(data.get('encodeFPTxnId') or '')
    txn.provider_meta = scrub_sensitive(resp)
    txn.response_code = str(resp.get('statusCode') or '')
    txn.response_message = str(resp.get('message') or '')[:500]
    txn.status = 'pending' if ok else 'failed'
    txn.save()

    if not ok:
        merchant.last_error = txn.response_message
        merchant.save(update_fields=['last_error', 'updated_at'])
        raise ValidationError(
            {
                'code': 'PROVIDER_REJECTED',
                'message': txn.response_message or 'eKYC send OTP failed at Fingpay.',
            }
        )

    merchant.ekyc_primary_key_id = str(data.get('primaryKeyId') or '')
    merchant.ekyc_encode_fp_txn_id = str(data.get('encodeFPTxnId') or '')
    merchant.stage = 'ekyc_pending'
    merchant.last_error = ''
    merchant.save(
        update_fields=[
            'ekyc_primary_key_id',
            'ekyc_encode_fp_txn_id',
            'stage',
            'device_imei',
            'device_ready',
            'masked_aadhaar',
            'onboarding_payload',
            'last_error',
            'updated_at',
        ]
    )
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
        resp = client.ekyc_post(
            client.endpoint('ekyc_validate_otp', 'fpekyc/api/ekyc/merchant/php/validateotp'),
            body,
            device_imei=merchant.device_imei,
            endpoint_key='ekyc_validate_otp',
        )
    except Exception as exc:
        txn.status = 'failed'
        txn.response_message = str(exc)[:500]
        txn.save()
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    ok = bool(resp.get('status') is True or str(resp.get('statusCode')) == '10000')
    txn.status = 'success' if ok else 'failed'
    txn.response_code = str(resp.get('statusCode') or '')
    txn.response_message = str(resp.get('message') or '')[:500]
    txn.provider_meta = scrub_sensitive(resp)
    txn.save()
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
        resp = client.ekyc_post(
            client.endpoint('ekyc_resend_otp', 'fpekyc/api/ekyc/merchant/php/resendotp'),
            body,
            device_imei=merchant.device_imei,
            endpoint_key='ekyc_resend_otp',
        )
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
        resp = client.ekyc_post(
            client.endpoint('ekyc_status', 'fpekyc/api/ekyc/status/check'),
            body,
            device_imei=merchant.device_imei or 'UNKNOWN',
            endpoint_key='ekyc_status',
        )
    except Exception as exc:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc
    return scrub_sensitive(resp)


def ekyc_biometric(*, user, capture_response: dict, latitude, longitude, aadhaar_number: str = '') -> dict:
    """
    Simple API biometric body (SIMPLE API FOR E-KYC doc):
    superMerchantId, merchantLoginId, primaryKeyId, encodeFPTxnId, requestRemarks,
    cardnumberORUID {adhaarNumber, indicatorforUID, nationalBankIdentificationNumber},
    captureResponse {...}
    """
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    if not merchant.ekyc_primary_key_id or not merchant.ekyc_encode_fp_txn_id:
        raise ValidationError(
            {
                'code': 'EKYC_OTP_REQUIRED',
                'message': 'Complete Send OTP and Verify OTP before fingerprint capture.',
            }
        )
    if not merchant.device_imei:
        raise ValidationError(
            {
                'code': 'DEVICE_IMEI_REQUIRED',
                'message': 'Phone/tablet IMEI is required for eKYC biometric. Save it under AEPS → Device.',
            }
        )
    aadhaar = ''.join(c for c in str(aadhaar_number or '') if c.isdigit())
    if len(aadhaar) != 12:
        aadhaar = _load_stored_aadhaar(merchant)
    if len(aadhaar) != 12:
        raise ValidationError(
            {
                'code': 'AADHAAR_REQUIRED',
                'message': 'Aadhaar is required for eKYC biometric. Re-run Send OTP with full Aadhaar first.',
            }
        )
    _store_aadhaar_encrypted(merchant, aadhaar)
    if not isinstance(capture_response, dict) or not (
        capture_response.get('Piddata') or capture_response.get('PidData')
    ):
        raise ValidationError(
            {
                'code': 'DEVICE_REQUIRED',
                'message': 'Fingerprint capture data is missing. Capture again with Mantra RD Service.',
            }
        )

    client = get_fingpay_client()
    # Field order matches Simple API eKYC biometric sample JSON.
    body = {
        'superMerchantId': int(client.super_merchant_id)
        if str(client.super_merchant_id).isdigit()
        else client.super_merchant_id,
        'merchantLoginId': merchant.merchant_login_id,
        'primaryKeyId': int(merchant.ekyc_primary_key_id)
        if str(merchant.ekyc_primary_key_id).isdigit()
        else merchant.ekyc_primary_key_id,
        'encodeFPTxnId': merchant.ekyc_encode_fp_txn_id,
        'requestRemarks': 'ekyc',
        'cardnumberORUID': {
            'nationalBankIdentificationNumber': '',
            'indicatorforUID': 0,
            'adhaarNumber': aadhaar,
        },
        'captureResponse': capture_response,
    }
    try:
        resp = client.ekyc_post(
            client.endpoint('ekyc_biometric', 'fpekyc/api/ekyc/merchant/v1/biometric'),
            body,
            device_imei=merchant.device_imei,
            endpoint_key='ekyc_biometric',
        )
    except Exception as exc:
        raise ValidationError({'code': 'PROVIDER_REJECTED', 'message': str(exc)}) from exc

    ok = _fingpay_ok(resp)
    data = resp.get('data') if isinstance(resp.get('data'), dict) else {}
    kyc_code = str(data.get('kycResponseCode') or data.get('responseCode') or '')
    provider_msg = str(resp.get('message') or data.get('responseMessage') or '')[:1000]

    txn = AepsTransaction.objects.create(
        user=user,
        merchant=merchant,
        merchant_tran_id=generate_merchant_tran_id('EKY'),
        product='EKY',
        status='pending',
        latitude=latitude,
        longitude=longitude,
        device_imei=merchant.device_imei or '',
        masked_aadhaar=merchant.masked_aadhaar,
        fp_transaction_id=merchant.ekyc_encode_fp_txn_id or '',
    )
    txn.provider_meta = scrub_sensitive(resp)
    txn.response_code = kyc_code or str(resp.get('statusCode') or '')
    txn.response_message = provider_msg[:500]
    txn.fp_transaction_id = str(data.get('fingpayTransactionId') or txn.fp_transaction_id)
    txn.bank_rrn = str(data.get('rrn') or '')

    # Doc success: status true + message "EKYC Completed Successfully" (data may be null).
    # FP097 = primary eKYC done; Fingpay still requires Bank eKYC before txn APIs.
    needs_bank = kyc_code.upper() == 'FP097' or 'bank ekyc' in provider_msg.lower() and 'complete' in provider_msg.lower()
    bank_done = (
        kyc_code in ('0', '00')
        or 'bank ekyc successfully' in provider_msg.lower()
        or 'ekyc completed successfully' in provider_msg.lower()
    )
    if ok and (bank_done or needs_bank or kyc_code in ('',)):
        if needs_bank and not bank_done:
            # Primary biometric accepted — keep merchant ready for Bank eKYC OTP/biometric.
            if merchant.stage in ('onboarding_submitted', 'ekyc_pending', 'not_started', 'onboarding_draft'):
                merchant.stage = 'ekyc_pending'
            merchant.last_error = ''
            merchant.last_latitude = latitude
            merchant.last_longitude = longitude
            merchant.save()
            txn.status = 'success'
            txn.save()
            return {
                'merchant_stage': merchant.stage,
                'transaction': _txn_dict(txn),
                'needs_bank_ekyc': True,
                'message': provider_msg or 'Primary eKYC done. Complete Bank eKYC next.',
            }
        merchant.stage = 'active'
        merchant.activated_at = timezone.now()
        merchant.fingpay_ekyc_ref = str(data.get('fingpayTransactionId') or merchant.ekyc_encode_fp_txn_id or '')
        merchant.last_error = ''
        merchant.last_latitude = latitude
        merchant.last_longitude = longitude
        merchant.save()
        txn.status = 'success'
        txn.save()
    else:
        merchant.last_error = provider_msg or 'eKYC biometric failed'
        merchant.save(update_fields=['onboarding_payload', 'last_error', 'updated_at'])
        txn.status = 'failed'
        txn.save()
        raise ValidationError(
            {'code': 'PROVIDER_REJECTED', 'message': merchant.last_error or 'eKYC failed'}
        )

    return {
        'merchant_stage': merchant.stage,
        'transaction': _txn_dict(txn),
        'needs_bank_ekyc': False,
        'message': provider_msg or 'eKYC completed.',
    }


def register_device(*, user, device_imei: str, scanner_serial: str = '') -> dict:
    assert_entitled(user)
    merchant = get_merchant(user)
    if not merchant:
        raise ValidationError({'message': 'Merchant profile missing.'})
    imei = (device_imei or '').strip()
    if not imei:
        raise ValidationError({'message': 'Phone/tablet IMEI is required (Fingpay deviceIMEI header).'})
    serial = (scanner_serial or '').strip()
    merchant.device_imei = imei
    if serial:
        merchant.scanner_serial = serial
    merchant.device_ready = True
    merchant.save(update_fields=['device_imei', 'scanner_serial', 'device_ready', 'updated_at'])
    return {
        'device_imei': merchant.device_imei,
        'scanner_serial': merchant.scanner_serial,
        'device_ready': True,
    }


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


def admin_merchant_detail_payload(merchant) -> dict:
    """Scrubbed merchant detail for admin UI — no raw base64 or full Aadhaar."""
    from apps.notifications.email_helpers import mask_pan

    user = merchant.user
    kyc = getattr(user, 'kyc', None)
    payload_flat = flatten_onboarding_payload(merchant.onboarding_payload)
    light_payload, saved_images = _strip_images_for_client(payload_flat)

    kyc_block = None
    if kyc:
        kyc_block = {
            'pan_verified': bool(kyc.pan_verified),
            'aadhaar_verified': bool(kyc.aadhaar_verified),
            'verification_status': kyc.verification_status,
            'masked_pan': mask_pan(kyc.pan or '') if kyc.pan else '',
            'masked_aadhaar': mask_aadhaar(kyc.aadhaar or '') if kyc.aadhaar else '',
            'pan_verified_at': kyc.pan_verified_at.isoformat() if kyc.pan_verified_at else None,
            'aadhaar_verified_at': kyc.aadhaar_verified_at.isoformat() if kyc.aadhaar_verified_at else None,
        }

    txns = (
        AepsTransaction.objects.filter(merchant=merchant, is_deleted=False)
        .order_by('-created_at')[:5]
        .values('id', 'product', 'status', 'response_message', 'merchant_tran_id', 'created_at')
    )
    recent_transactions = [
        {
            **t,
            'created_at': t['created_at'].isoformat() if t.get('created_at') else None,
        }
        for t in txns
    ]

    audit_qs = AepsApiAuditLog.objects.filter(user_id=user.pk).order_by('-created_at')
    audit_count = audit_qs.count()
    recent_audit = [
        {
            'id': row.pk,
            'endpoint': row.endpoint,
            'success': row.success,
            'error_message': row.error_message,
            'http_status': row.http_status,
            'created_at': row.created_at.isoformat() if row.created_at else None,
        }
        for row in audit_qs[:5]
    ]

    return {
        'merchant': {
            'id': merchant.pk,
            'merchant_login_id': merchant.merchant_login_id,
            'stage': merchant.stage,
            'device_ready': merchant.device_ready,
            'device_imei': merchant.device_imei or '',
            'masked_aadhaar': merchant.masked_aadhaar or '',
            'last_error': merchant.last_error or '',
            'last_latitude': str(merchant.last_latitude) if merchant.last_latitude is not None else None,
            'last_longitude': str(merchant.last_longitude) if merchant.last_longitude is not None else None,
            'fingpay_onboarding_ref': merchant.fingpay_onboarding_ref or '',
            'fingpay_ekyc_ref': merchant.fingpay_ekyc_ref or '',
            'has_merchant_pin': bool(merchant_pin_plain(merchant)),
            'ekyc_primary_key_id': merchant.ekyc_primary_key_id or '',
            'ekyc_encode_fp_txn_id': merchant.ekyc_encode_fp_txn_id or '',
            'activated_at': merchant.activated_at.isoformat() if merchant.activated_at else None,
            'last_2fa_at': merchant.last_2fa_at.isoformat() if merchant.last_2fa_at else None,
            'created_at': merchant.created_at.isoformat() if merchant.created_at else None,
            'updated_at': merchant.updated_at.isoformat() if merchant.updated_at else None,
        },
        'user': {
            'id': user.pk,
            'name': f'{user.first_name} {user.last_name}'.strip(),
            'phone': user.phone,
            'email': getattr(user, 'email', '') or '',
            'role': user.role,
        },
        'kyc': kyc_block,
        'onboarding': {
            'fields': light_payload,
            'saved_images': saved_images,
        },
        'recent_transactions': recent_transactions,
        'audit_logs': {
            'count': audit_count,
            'recent': recent_audit,
            'filter_url_hint': f'/admin/aeps/debug-logs?user_id={user.pk}',
        },
    }
