"""
Base abstract class for all external integrations.
"""
from abc import ABC, abstractmethod
from django.conf import settings


class BaseIntegration(ABC):
    """
    Abstract base class for all external API integrations.
    """
    
    def __init__(self):
        self.api_key = None
        self.api_url = None
        self._load_config()
    
    def _load_config(self):
        """Load configuration from settings."""
        pass
    
    @abstractmethod
    def is_available(self):
        """Check if the integration is available."""
        pass
    
    @abstractmethod
    def handle_error(self, error):
        """Handle integration errors."""
        pass
