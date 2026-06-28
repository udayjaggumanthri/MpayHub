"""Bank account verification result types."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BavVerifyResult:
    success: bool
    beneficiary_name: str
    bank_name: str
    branch: str
    city: str
    ifsc: str
    account_status: str
    account_status_code: str
    name_match_score: str
    name_match_result: str
    reference_id: str
    utr: str
    raw: dict[str, Any]
