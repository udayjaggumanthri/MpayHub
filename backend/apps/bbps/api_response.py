"""Standard BBPS API error envelopes for operator/support traceability."""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework import status
from rest_framework.response import Response


def bbps_error_response(
    message: str,
    *,
    code: str = 'BBPS_ERROR',
    retryable: bool = False,
    errors: list[Any] | None = None,
    trace_id: str | None = None,
    http_status: int = status.HTTP_400_BAD_REQUEST,
    provider_code: str = '',
    action_hint: str = '',
) -> Response:
    """
    Consistent failure payload for BBPS user endpoints.

    - ``message``: safe for end-user display.
    - ``error.code`` / ``error.trace_id`` / ``error.retryable``: for IT/support and client UX.
    - ``error.provider_code`` / ``error.action_hint``: optional BillAvenue / recovery hints.
    - ``errors``: optional field-level list ``[{param, code, message}, ...]`` or strings.
    """
    tid = trace_id or uuid.uuid4().hex
    error_obj: dict[str, Any] = {'code': code, 'trace_id': tid, 'retryable': retryable}
    if provider_code:
        error_obj['provider_code'] = str(provider_code).strip().upper()
    if action_hint:
        error_obj['action_hint'] = str(action_hint).strip()
    return Response(
        {
            'success': False,
            'data': None,
            'message': message,
            'errors': list(errors) if errors is not None else [],
            'error': error_obj,
        },
        status=http_status,
    )
