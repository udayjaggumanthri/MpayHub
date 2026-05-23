"""
MSG91 transactional SMS via Flow API v5.

See https://docs.msg91.com/overview — use approved DLT template_id + variables.
POST {api_base_url}/api/v5/flow/ with authkey header.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from apps.notifications.providers.base import SendResult

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = 'https://control.msg91.com'


class Msg91Adapter:
    """Send template SMS through MSG91 Flow API."""

    def __init__(self, *, auth_key: str, api_base_url: str = DEFAULT_BASE_URL, route: str = ''):
        self.auth_key = (auth_key or '').strip()
        base = (api_base_url or DEFAULT_BASE_URL).rstrip('/')
        self.api_url = f'{base}/api/v5/flow/'
        self.route = (route or '').strip()

    def send_template(
        self,
        phone_e164: str,
        template_id: str,
        variables: dict[str, Any],
        *,
        sender_id: str = '',
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
            'short_url': '0',
            'recipients': [recipient],
        }
        if self.route:
            body['route'] = self.route
        if sender_id:
            body['sender'] = sender_id

        headers = {
            'authkey': self.auth_key,
            'Content-Type': 'application/json',
            'accept': 'application/json',
        }

        try:
            resp = requests.post(self.api_url, json=body, headers=headers, timeout=30)
        except requests.RequestException as exc:
            logger.warning('MSG91 request failed: %s', exc)
            return SendResult(success=False, error=str(exc))

        try:
            data = resp.json() if resp.content else {}
        except ValueError:
            data = {}

        if resp.ok:
            msg_id = ''
            if isinstance(data, dict):
                msg_id = str(data.get('message') or data.get('request_id') or data.get('type') or '')
            return SendResult(success=True, message_id=msg_id or 'ok')

        err = ''
        if isinstance(data, dict):
            err = str(data.get('message') or data.get('error') or data)
        else:
            err = resp.text[:500]
        if not err:
            err = f'HTTP {resp.status_code}'
        logger.warning('MSG91 send failed: %s', err)
        return SendResult(success=False, error=err)
