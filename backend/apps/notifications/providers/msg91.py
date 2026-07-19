"""
MSG91 transactional SMS via Flow API v5.

Send: POST {api_base_url}/api/v5/flow/
Fetch template: POST {api_base_url}/api/v5/sms/getTemplateVersions
"""
from __future__ import annotations

import logging
import re
from typing import Any

import requests

from apps.notifications.providers.base import SendResult

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = 'https://control.msg91.com'
# Flow templates may use ##var1## OR named vars like ##amount## / ##transaction_id##
_HASH_VAR_PATTERN = re.compile(r'##\s*([A-Za-z_][A-Za-z0-9_]*)\s*##')
_DLT_VAR_PATTERN = re.compile(r'\{#\s*var\s*#\}', re.IGNORECASE)


def extract_msg91_vars(template_data: str) -> list[str]:
    """
    Return ordered unique MSG91 Flow recipient keys from template body.

    Supports:
    - ##amount## / ##transaction_id## (named Flow placeholders — keys must match exactly)
    - ##var1## / ##VAR2## (positional Flow placeholders)
    - {#var#} (DLT sample text — mapped in order to var1, var2, …)
    """
    found: list[str] = []
    seen: set[str] = set()
    for match in _HASH_VAR_PATTERN.finditer(template_data or ''):
        key = match.group(1).strip()
        # Preserve original casing for named vars; normalize varN to lowercase
        if re.fullmatch(r'var\d+', key, flags=re.IGNORECASE):
            key = key.lower()
        if key not in seen:
            seen.add(key)
            found.append(key)
    if found:
        return found
    # DLT-style {#var#} appears without index — assign var1, var2, … in order
    for idx, _ in enumerate(_DLT_VAR_PATTERN.finditer(template_data or ''), start=1):
        key = f'var{idx}'
        if key not in seen:
            seen.add(key)
            found.append(key)
    return found


def suggest_variable_map(
    schema: list[dict] | None,
    detected_vars: list[str] | None,
) -> dict[str, str]:
    """
    Build app_key → MSG91 recipient key map from schema + detected placeholders.

    Strategy (enterprise-safe):
    1. Exact name match (case-insensitive): amount→##amount##
    2. Remaining required schema fields filled by leftover placeholder order
    3. Remaining optional schema fields filled by any leftover placeholders
    """
    schema_rows = [v for v in (schema or []) if isinstance(v, dict) and str(v.get('name') or '').strip()]
    required_names = [
        str(v.get('name')).strip() for v in schema_rows if v.get('required', True)
    ]
    optional_names = [
        str(v.get('name')).strip() for v in schema_rows if not v.get('required', True)
    ]
    # Preserve schema order for required+optional
    schema_names = required_names + [n for n in optional_names if n not in required_names]
    detected = [str(d).strip() for d in (detected_vars or []) if str(d).strip()]
    if not schema_names:
        return {}

    out: dict[str, str] = {}
    used_targets: set[str] = set()
    detected_lower = {d.lower(): d for d in detected}

    for name in schema_names:
        match = detected_lower.get(name.lower())
        if match and match not in used_targets:
            out[name] = match
            used_targets.add(match)

    remaining_detected = [d for d in detected if d not in used_targets]

    def _fill(names: list[str]) -> None:
        nonlocal remaining_detected
        for name in names:
            if name in out:
                continue
            if not remaining_detected:
                break
            target = remaining_detected.pop(0)
            out[name] = target
            used_targets.add(target)

    _fill([n for n in required_names if n not in out])
    _fill([n for n in optional_names if n not in out])
    return out


class Msg91Adapter:
    """Send template SMS and fetch DLT template metadata through MSG91 APIs."""

    def __init__(self, *, auth_key: str, api_base_url: str = DEFAULT_BASE_URL, route: str = ''):
        self.auth_key = (auth_key or '').strip()
        self.base = (api_base_url or DEFAULT_BASE_URL).rstrip('/')
        self.api_url = f'{self.base}/api/v5/flow/'
        self.template_versions_url = f'{self.base}/api/v5/sms/getTemplateVersions'
        self.route = (route or '').strip()

    def _headers(self) -> dict[str, str]:
        return {
            'authkey': self.auth_key,
            'Content-Type': 'application/json',
            'accept': 'application/json',
        }

    def send_template(
        self,
        phone_e164: str,
        template_id: str,
        variables: dict[str, Any],
        *,
        sender_id: str = '',
        short_url: str = '0',
    ) -> SendResult:
        if not self.auth_key:
            return SendResult(success=False, error='MSG91 auth key not configured')
        if not template_id:
            return SendResult(success=False, error='template_id required')

        recipient: dict[str, Any] = {'mobiles': phone_e164}
        for key, val in (variables or {}).items():
            if val is None:
                continue
            recipient[str(key)] = str(val)

        body: dict[str, Any] = {
            'template_id': str(template_id),
            'short_url': str(short_url or '0'),
            'recipients': [recipient],
        }
        if self.route:
            body['route'] = self.route
        if sender_id:
            body['sender'] = sender_id

        try:
            resp = requests.post(self.api_url, json=body, headers=self._headers(), timeout=30)
        except requests.RequestException as exc:
            logger.warning('MSG91 Flow request failed: %s', exc)
            return SendResult(success=False, error=str(exc))

        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = {}

        if resp.ok:
            msg_id = ''
            if isinstance(data, dict):
                # Flow success: {"message": "<request_id>", "type": "success"}
                if str(data.get('type') or '').lower() == 'success' or data.get('message'):
                    msg_id = str(data.get('message') or data.get('request_id') or '')
                elif data.get('hasError') is False:
                    msg_id = str(data.get('message') or data.get('request_id') or 'ok')
                else:
                    msg_id = str(data.get('message') or data.get('request_id') or 'ok')
            return SendResult(success=True, message_id=msg_id or 'ok')

        err = ''
        if isinstance(data, dict):
            err = str(data.get('message') or data.get('error') or data)
        else:
            err = resp.text[:500]
        if not err:
            err = f'HTTP {resp.status_code}'
        logger.warning('MSG91 Flow send failed: %s', err)
        return SendResult(success=False, error=err)

    def get_template_versions(self, template_id: str) -> dict[str, Any]:
        """
        Fetch MSG91 DLT template metadata for a template_id.

        Returns:
            {success, error?, versions: [...], primary: {...}|None}
        """
        tid = (template_id or '').strip()
        if not self.auth_key:
            return {'success': False, 'error': 'MSG91 auth key not configured', 'versions': [], 'primary': None}
        if not tid:
            return {'success': False, 'error': 'template_id required', 'versions': [], 'primary': None}

        try:
            resp = requests.post(
                self.template_versions_url,
                json={'template_id': tid},
                headers=self._headers(),
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.warning('MSG91 getTemplateVersions failed: %s', exc)
            return {'success': False, 'error': str(exc), 'versions': [], 'primary': None}

        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = {}

        if not resp.ok:
            err = ''
            if isinstance(data, dict):
                err = str(data.get('message') or data.get('error') or data)
            else:
                err = resp.text[:500]
            return {
                'success': False,
                'error': err or f'HTTP {resp.status_code}',
                'versions': [],
                'primary': None,
            }

        if isinstance(data, dict) and data.get('hasError'):
            errs = data.get('errors') or []
            return {
                'success': False,
                'error': str(errs or data.get('message') or 'MSG91 returned hasError'),
                'versions': [],
                'primary': None,
            }

        raw_list = []
        if isinstance(data, dict):
            raw_list = data.get('data') or []
        if not isinstance(raw_list, list):
            raw_list = []

        versions = []
        for row in raw_list:
            if not isinstance(row, dict):
                continue
            body = str(row.get('template_data') or '')
            versions.append(
                {
                    'id': str(row.get('id') or ''),
                    'template_id': str(row.get('template_id') or tid),
                    'template_name': str(row.get('template_name') or ''),
                    'template_data': body,
                    'dlt_id': str(row.get('DLT_ID') or row.get('dlt_id') or ''),
                    'sender_id': str(row.get('sender_id') or ''),
                    'version': str(row.get('version') or ''),
                    'status': str(row.get('status') or ''),
                    'active_status': str(row.get('active_status') or ''),
                    'sms_type': str(row.get('sms_type') or ''),
                    'detected_vars': extract_msg91_vars(body),
                }
            )

        primary = versions[0] if versions else None
        return {'success': True, 'error': '', 'versions': versions, 'primary': primary}
