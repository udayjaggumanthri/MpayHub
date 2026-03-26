"""
Bank account views for the mPayhub platform.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.bank_accounts.models import BankAccount
from apps.bank_accounts.serializers import BankAccountSerializer, BankAccountValidationSerializer
from apps.bank_accounts.services import validate_bank_account
from apps.core.exceptions import BankValidationFailed


class BankAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for bank account management.
    """
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter bank accounts by authenticated user."""
        queryset = BankAccount.objects.filter(user=self.request.user)
        
        # Apply filters
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(account_holder_name__icontains=name)
        
        bank_name = self.request.query_params.get('bank_name')
        if bank_name:
            queryset = queryset.filter(bank_name__icontains=bank_name)
        
        account_number = self.request.query_params.get('account_number')
        if account_number:
            queryset = queryset.filter(account_number__icontains=account_number)
        
        ifsc = self.request.query_params.get('ifsc')
        if ifsc:
            queryset = queryset.filter(ifsc__icontains=ifsc)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set user when creating bank account."""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['post'])
    def validate(self, request):
        """Validate bank account."""
        serializer = BankAccountValidationSerializer(data=request.data)
        if serializer.is_valid():
            try:
                result = validate_bank_account(
                    request.user,
                    serializer.validated_data['account_number'],
                    serializer.validated_data['ifsc']
                )
                return Response({
                    'success': True,
                    'data': result,
                    'message': 'Bank account validated successfully',
                    'errors': []
                }, status=status.HTTP_200_OK)
            except BankValidationFailed as e:
                return Response({
                    'success': False,
                    'data': None,
                    'message': str(e),
                    'errors': []
                }, status=status.HTTP_400_BAD_REQUEST)
        
        return Response({
            'success': False,
            'data': None,
            'message': 'Bank account validation failed',
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)
