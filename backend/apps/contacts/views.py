"""
Contact views for the mPayhub platform.
"""
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.contacts.models import Contact
from apps.contacts.serializers import ContactSerializer


class ContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet for contact management.
    Each user only sees and mutates their own contacts (queryset + perform_create).
    """

    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    
    def list(self, request, *args, **kwargs):
        """Return a stable envelope with `contacts` for enterprise clients."""
        response = super().list(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return response
        payload = response.data
        if isinstance(payload, dict) and 'results' in payload:
            return Response({
                'success': True,
                'data': {
                    'contacts': payload.get('results', []),
                    'count': payload.get('count'),
                    'next': payload.get('next'),
                    'previous': payload.get('previous'),
                },
                'message': 'Contacts retrieved successfully',
                'errors': [],
            }, status=status.HTTP_200_OK)
        if isinstance(payload, list):
            return Response({
                'success': True,
                'data': {'contacts': payload, 'count': len(payload)},
                'message': 'Contacts retrieved successfully',
                'errors': [],
            }, status=status.HTTP_200_OK)
        return response

    def get_queryset(self):
        """Filter contacts by authenticated user."""
        queryset = Contact.objects.filter(user=self.request.user)
        
        # Apply filters
        name = self.request.query_params.get('name')
        if name:
            queryset = queryset.filter(name__icontains=name)
        
        email = self.request.query_params.get('email')
        if email:
            queryset = queryset.filter(email__icontains=email)
        
        phone = self.request.query_params.get('phone')
        if phone:
            queryset = queryset.filter(phone__icontains=phone)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set user when creating contact."""
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Search contacts by phone."""
        phone = request.query_params.get('phone')
        if not phone:
            return Response({
                'success': False,
                'data': None,
                'message': 'Phone parameter is required',
                'errors': []
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            contact = Contact.objects.get(user=request.user, phone=phone)
            serializer = self.get_serializer(contact)
            return Response({
                'success': True,
                'data': {'contact': serializer.data},
                'message': 'Contact found',
                'errors': []
            }, status=status.HTTP_200_OK)
        except Contact.DoesNotExist:
            return Response({
                'success': False,
                'data': None,
                'message': 'Contact not found',
                'errors': []
            }, status=status.HTTP_404_NOT_FOUND)
