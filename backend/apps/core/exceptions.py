"""
Custom exceptions for the mPayhub platform.
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


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


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns standardized error responses.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If response is None, it means DRF couldn't handle the exception
    # We'll create a custom response
    if response is None:
        if isinstance(exc, InsufficientBalance):
            response_data = {
                'success': False,
                'data': None,
                'message': 'Insufficient wallet balance',
                'errors': [str(exc)]
            }
            response = Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        elif isinstance(exc, InvalidMPIN):
            response_data = {
                'success': False,
                'data': None,
                'message': 'Invalid MPIN',
                'errors': [str(exc)]
            }
            response = Response(response_data, status=status.HTTP_401_UNAUTHORIZED)
        elif isinstance(exc, InvalidOTP):
            response_data = {
                'success': False,
                'data': None,
                'message': 'Invalid or expired OTP',
                'errors': [str(exc)]
            }
            response = Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        elif isinstance(exc, InvalidCredentials):
            response_data = {
                'success': False,
                'data': None,
                'message': 'Invalid credentials',
                'errors': [str(exc)]
            }
            response = Response(response_data, status=status.HTTP_401_UNAUTHORIZED)
        elif isinstance(exc, InvalidUserRole):
            response_data = {
                'success': False,
                'data': None,
                'message': 'Invalid user role for this operation',
                'errors': [str(exc)]
            }
            response = Response(response_data, status=status.HTTP_403_FORBIDDEN)
        elif isinstance(exc, TransactionFailed):
            response_data = {
                'success': False,
                'data': None,
                'message': 'Transaction failed',
                'errors': [str(exc)]
            }
            response = Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        elif isinstance(exc, BankValidationFailed):
            response_data = {
                'success': False,
                'data': None,
                'message': 'Bank account validation failed',
                'errors': [str(exc)]
            }
            response = Response(response_data, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Generic error response
            response_data = {
                'success': False,
                'data': None,
                'message': 'An error occurred',
                'errors': [str(exc)]
            }
            response = Response(response_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        # Customize the response format for DRF exceptions
        custom_response_data = {
            'success': False,
            'data': None,
            'message': 'Validation error',
            'errors': []
        }
        
        if hasattr(response, 'data'):
            if isinstance(response.data, dict):
                for field, errors in response.data.items():
                    if isinstance(errors, list):
                        custom_response_data['errors'].extend([f"{field}: {error}" for error in errors])
                    else:
                        custom_response_data['errors'].append(f"{field}: {errors}")
            elif isinstance(response.data, list):
                custom_response_data['errors'] = response.data
        
        response.data = custom_response_data
    
    return response
