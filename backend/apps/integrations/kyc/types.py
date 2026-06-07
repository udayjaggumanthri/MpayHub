from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PanVerifyResult:
    success: bool
    pan: str = ''
    registered_name: str = ''
    date_of_birth: str = ''
    pan_type: str = ''
    reference_id: str = ''
    verification_id: str = ''
    status: str = ''
    message: str = ''
    raw: dict = field(default_factory=dict)


@dataclass
class DigilockerInitResult:
    verification_id: str
    reference_id: str = ''
    url: str = ''
    status: str = 'PENDING'
    user_flow: str = ''
    raw: dict = field(default_factory=dict)


@dataclass
class DigilockerStatusResult:
    verification_id: str
    status: str = 'PENDING'
    reference_id: str = ''
    user_details: dict = field(default_factory=dict)
    document_consent: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class DigilockerDocumentResult:
    verification_id: str
    status: str = ''
    uid_masked: str = ''
    name: str = ''
    date_of_birth: str = ''
    gender: str = ''
    raw: dict = field(default_factory=dict)
