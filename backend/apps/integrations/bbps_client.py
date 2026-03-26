"""
BBPS API client integration.
"""
import requests
from django.conf import settings
from apps.integrations.base import BaseIntegration


class BBPSClient(BaseIntegration):
    """
    BBPS API client for bill fetching and payment processing.
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'BBPS_API_KEY', None)
        self.api_url = getattr(settings, 'BBPS_API_URL', None)
        super().__init__()
    
    def _load_config(self):
        """Load BBPS configuration."""
        pass
    
    def is_available(self):
        """Check if BBPS service is available."""
        if settings.DEBUG:
            return True  # Always available in debug mode (mock)
        return self.api_key and self.api_url is not None
    
    def handle_error(self, error):
        """Handle BBPS service errors."""
        print(f"BBPS Service Error: {error}")
    
    def fetch_bill(self, biller_id, category, **kwargs):
        """
        Fetch bill details from BBPS.
        
        Args:
            biller_id: Biller ID
            category: Bill category
            **kwargs: Category-specific parameters
        
        Returns:
            dict with bill details
        """
        if not self.is_available():
            # Return mock data in development
            return {
                'amount': 1000.00,
                'due_date': None,
                'customer_details': kwargs
            }
        
        # In production, make actual API call
        try:
            # This is a placeholder - implement actual BBPS API call
            # response = requests.post(
            #     f"{self.api_url}/fetch-bill",
            #     headers={'Authorization': f'Bearer {self.api_key}'},
            #     json={'biller_id': biller_id, 'category': category, **kwargs}
            # )
            # return response.json()
            pass
        except Exception as e:
            self.handle_error(e)
            # Return mock data on error
            return {
                'amount': 1000.00,
                'due_date': None,
                'customer_details': kwargs
            }
    
    def process_payment(self, service_id, request_id, amount, bill_data):
        """
        Process bill payment via BBPS.
        
        Args:
            service_id: Service ID
            request_id: Request ID
            amount: Payment amount
            bill_data: Bill data
        
        Returns:
            dict with payment result
        """
        if not self.is_available():
            # Return mock success in development
            return {
                'status': 'SUCCESS',
                'message': 'Payment processed successfully',
                'transaction_id': service_id
            }
        
        # In production, make actual API call
        try:
            # This is a placeholder - implement actual BBPS API call
            # response = requests.post(
            #     f"{self.api_url}/process-payment",
            #     headers={'Authorization': f'Bearer {self.api_key}'},
            #     json={
            #         'service_id': service_id,
            #         'request_id': request_id,
            #         'amount': amount,
            #         'bill_data': bill_data
            #     }
            # )
            # return response.json()
            return {
                'status': 'SUCCESS',
                'message': 'Payment processed successfully',
                'transaction_id': service_id
            }
        except Exception as e:
            self.handle_error(e)
            return {
                'status': 'FAILED',
                'message': str(e)
            }
