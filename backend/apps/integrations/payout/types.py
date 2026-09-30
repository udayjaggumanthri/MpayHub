"""Canonical payout provider DTOs — domain never sees Vidual field names."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any


# Domain-facing status after adapter maps provider codes.
DOMAIN_PENDING = 'PENDING'
DOMAIN_SUCCESS = 'SUCCESS'
DOMAIN_FAILED = 'FAILED'


@dataclass(frozen=True)
class MasterItem:
    code: str
    description: str


@dataclass(frozen=True)
class PayoutInitiateRequest:
    merchant_ref_id: str
    amount: Decimal
    payment_mode: str  # IMPS | NEFT
    beneficiary_account_number: str
    beneficiary_ifsc: str
    beneficiary_name: str
    beneficiary_mobile: str
    beneficiary_bank_code: str
    beneficiary_location: str  # state code e.g. JH
    payment_purpose: str = '004'
    lat: str = '28.7041'
    long: str = '77.1025'
    udf1: str = ''
    udf2: str = ''
    udf3: str = ''


@dataclass(frozen=True)
class PayoutInitiateResult:
    """Immediate response after initiate (usually Queued/Pending)."""

    domain_status: str  # PENDING | SUCCESS | FAILED
    provider_status_code: str  # 000..004
    provider_txn_id: str = ''
    response_message: str = ''
    charges: Decimal | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PayoutCallbackEvent:
    merchant_ref_id: str
    domain_status: str  # PENDING | SUCCESS | FAILED
    provider_status_code: str
    provider_txn_id: str = ''
    rrn: str = ''
    response_message: str = ''
    amount: Decimal | None = None
    charges: Decimal | None = None
    payment_mode: str = ''
    raw: dict[str, Any] = field(default_factory=dict)


def map_provider_status_code(code: str | int | None, *, txn_status: str = '') -> str:
    """
    Map Vidual / common payout status codes to domain PENDING|SUCCESS|FAILED.
    000 Success, 001 Failed, 002 Pending, 003 Validation Failed, 004 Queued.
    """
    c = str(code or '').strip()
    if c in ('000', '0'):
        return DOMAIN_SUCCESS
    if c in ('001', '1', '003', '3'):
        return DOMAIN_FAILED
    if c in ('002', '2', '004', '4'):
        return DOMAIN_PENDING
    # Fallback on textual txnStatus from callback
    ts = (txn_status or '').strip().lower()
    if ts in ('success', 'successful', 'completed'):
        return DOMAIN_SUCCESS
    if ts in ('failed', 'failure', 'fail', 'rejected'):
        return DOMAIN_FAILED
    if ts in ('pending', 'queued', 'inprogress', 'in progress', 'in_progress'):
        return DOMAIN_PENDING
    return DOMAIN_PENDING
