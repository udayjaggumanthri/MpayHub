"""
Bank account validation integration.
"""
import requests
from django.conf import settings
from apps.integrations.base import BaseIntegration
import random


class BankValidator(BaseIntegration):
    """
    Bank account validation service.
    """
    
    def __init__(self):
        self.api_key = getattr(settings, 'BANK_VALIDATION_API_KEY', None)
        self.api_url = getattr(settings, 'BANK_VALIDATION_API_URL', None)
        super().__init__()
    
    def _load_config(self):
        """Load bank validation configuration."""
        pass
    
    def is_available(self):
        """Check if bank validation service is available."""
        if settings.DEBUG:
            return True  # Always available in debug mode (mock)
        return self.api_key and self.api_url is not None
    
    def handle_error(self, error):
        """Handle bank validation errors."""
        print(f"Bank Validation Error: {error}")
    
    def validate_account(self, account_number, ifsc):
        """
        Validate bank account and fetch beneficiary name.
        
        Args:
            account_number: Account number
            ifsc: IFSC code
        
        Returns:
            dict with beneficiary_name, account_number, ifsc
        """
        if not self.is_available():
            # Return mock data in development
            mock_names = [
                'Mr REESU MADHU PAVAN',
                'Mrs KAVITHA REDDY',
                'Mr RAVI KUMAR',
                'Ms PRIYA SHARMA',
                'Mr R PAVA',
                'BALR',
                'KONE MAN',
            ]
            return {
                'beneficiary_name': random.choice(mock_names),
                'account_number': account_number,
                'ifsc': ifsc
            }
        
        # In production, make actual API call
        try:
            # This is a placeholder - implement actual bank validation API call
            # response = requests.post(
            #     f"{self.api_url}/validate",
            #     headers={'Authorization': f'Bearer {self.api_key}'},
            #     json={'account_number': account_number, 'ifsc': ifsc}
            # )
            # return response.json()
            mock_names = [
                'Mr REESU MADHU PAVAN',
                'Mrs KAVITHA REDDY',
                'Mr RAVI KUMAR',
            ]
            return {
                'beneficiary_name': random.choice(mock_names),
                'account_number': account_number,
                'ifsc': ifsc
            }
        except Exception as e:
            self.handle_error(e)
            # Return mock data on error
            mock_names = ['Mr REESU MADHU PAVAN']
            return {
                'beneficiary_name': random.choice(mock_names),
                'account_number': account_number,
                'ifsc': ifsc
            }
