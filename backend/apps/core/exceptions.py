"""
Custom exceptions for the mPayhub platform.
"""
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


class InsufficientBalance(Exception):
    """Raised when wallet balance is insufficient for a transaction."""

    pass


class InvalidMPIN(Exception):
    """Raised when MPIN verification fails."""

    pass


class InvalidOTP(Exception):
    """Raised when OTP verification fails."""

    pass


class InvalidCredentials(Exception):
    """Raised when authentication credentials are invalid."""

    pass


class InvalidUserRole(Exception):
    """Raised when user role is invalid for an operation."""

    pass


class TransactionFailed(Exception):
    """Raised when a transaction fails."""

    pass


class BankValidationFailed(Exception):
    """Raised when bank account validation fails."""

    pass


def _api_error_response(
    *,
    message: str,
    errors: list,
    code: str,
    http_status: int,
    retryable: bool = False,
) -> Response:
    tid = uuid.uuid4().hex
    return Response(
        {
            'success': False,
            'data': None,
            'message': message,
            'errors': errors,
            'error': {'code': code, 'trace_id': tid, 'retryable': retryable},
        },
        status=http_status,
    )


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns standardized error responses with trace_id for support.
    """
    response = exception_handler(exc, context)

    if response is None:
        if isinstance(exc, InsufficientBalance):
            return _api_error_response(
                message='Insufficient wallet balance',
                errors=[str(exc)] if str(exc).strip() else [],
                code='INSUFFICIENT_BALANCE',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(exc, InvalidMPIN):
            return _api_error_response(
                message='Invalid MPIN',
                errors=[str(exc)] if str(exc).strip() else [],
                code='INVALID_MPIN',
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        if isinstance(exc, InvalidOTP):
            return _api_error_response(
                message='Invalid or expired OTP',
                errors=[str(exc)] if str(exc).strip() else [],
                code='INVALID_OTP',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(exc, InvalidCredentials):
            return _api_error_response(
                message='Invalid credentials',
                errors=[str(exc)] if str(exc).strip() else [],
                code='INVALID_CREDENTIALS',
                http_status=status.HTTP_401_UNAUTHORIZED,
            )
        if isinstance(exc, InvalidUserRole):
            return _api_error_response(
                message='Invalid user role for this operation',
                errors=[str(exc)] if str(exc).strip() else [],
                code='INVALID_ROLE',
                http_status=status.HTTP_403_FORBIDDEN,
            )
        if isinstance(exc, TransactionFailed):
            detail = str(exc).strip()
            return _api_error_response(
                message=detail or 'This operation could not be completed.',
                errors=[detail] if detail else [],
                code='TRANSACTION_FAILED',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        if isinstance(exc, BankValidationFailed):
            return _api_error_response(
                message='Bank account validation failed',
                errors=[str(exc)] if str(exc).strip() else [],
                code='BANK_VALIDATION_FAILED',
                http_status=status.HTTP_400_BAD_REQUEST,
            )
        safe_msg = (
            str(exc).strip()
            if getattr(settings, 'DEBUG', False)
            else 'An unexpected error occurred. Please try again or contact support with your reference ID.'
        )
        return _api_error_response(
            message=safe_msg,
            errors=[str(exc)] if getattr(settings, 'DEBUG', False) and str(exc).strip() else [],
            code='INTERNAL_ERROR',
            http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            retryable=True,
        )

    custom_response_data = {
        'success': False,
        'data': None,
        'message': 'Validation error',
        'errors': [],
    }

    if hasattr(response, 'data'):
        if isinstance(response.data, dict):
            for field, errors in response.data.items():
                if isinstance(errors, list):
                    custom_response_data['errors'].extend([f'{field}: {error}' for error in errors])
                else:
                    custom_response_data['errors'].append(f'{field}: {errors}')
        elif isinstance(response.data, list):
            custom_response_data['errors'] = list(response.data)

    if custom_response_data['errors']:
        custom_response_data['message'] = str(custom_response_data['errors'][0])[:500]

    status_to_code = {
        status.HTTP_400_BAD_REQUEST: 'VALIDATION_ERROR',
        status.HTTP_401_UNAUTHORIZED: 'AUTHENTICATION_REQUIRED',
        status.HTTP_403_FORBIDDEN: 'PERMISSION_DENIED',
        status.HTTP_404_NOT_FOUND: 'NOT_FOUND',
        status.HTTP_429_TOO_MANY_REQUESTS: 'THROTTLED',
    }
    code = status_to_code.get(response.status_code, 'API_ERROR')
    tid = uuid.uuid4().hex
    custom_response_data['error'] = {
        'code': code,
        'trace_id': tid,
        'retryable': response.status_code >= 500 or response.status_code == 429,
    }
    response.data = custom_response_data
    return response
