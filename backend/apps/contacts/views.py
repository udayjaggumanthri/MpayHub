"""
Contact views for the mPayhub platform.
"""
import re

from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from apps.contacts.models import Contact
from apps.contacts.pagination import ContactPagination
from apps.contacts.serializers import ContactSerializer
from apps.contacts.throttles import ContactUserThrottle

SUGGEST_LIMIT = 20
# Bound filter inputs to reduce ReDoS / oversized-query risk (model max lengths).
FILTER_NAME_MAX_LEN = 200
FILTER_EMAIL_MAX_LEN = 254
FILTER_PHONE_RAW_MAX_LEN = 32


class ContactViewSet(viewsets.ModelViewSet):
    """
    ViewSet for contact management.
    Each user only sees and mutates their own contacts (queryset + perform_create).
    """

    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = ContactPagination
    throttle_classes = [ContactUserThrottle]

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
        
        # Apply filters (truncate query strings before DB use)
        name = (self.request.query_params.get('name') or '')[:FILTER_NAME_MAX_LEN].strip()
        if name:
            queryset = queryset.filter(name__icontains=name)

        email = (self.request.query_params.get('email') or '')[:FILTER_EMAIL_MAX_LEN].strip()
        if email:
            queryset = queryset.filter(email__icontains=email)

        phone = (self.request.query_params.get('phone') or '')[:FILTER_PHONE_RAW_MAX_LEN]
        if phone:
            digits = re.sub(r'\D', '', phone)[:10]
            if len(digits) == 10:
                queryset = queryset.filter(phone=digits)
            else:
                queryset = queryset.filter(phone__icontains=phone)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Set user when creating contact."""
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['get'], url_path='suggest')
    def suggest(self, request):
        """
        Typeahead: partial match on name or phone (digits). Returns up to 20 contacts.
        Query: ?q=   (minimum 2 characters after trim)
        """
        q = (request.query_params.get('q') or '').strip()[:FILTER_NAME_MAX_LEN]
        if len(q) < 2:
            return Response(
                {
                    'success': True,
                    'data': {'contacts': []},
                    'message': 'OK',
                    'errors': [],
                },
                status=status.HTTP_200_OK,
            )

        digits = re.sub(r'\D', '', q)
        cond = Q(name__icontains=q)
        if digits:
            cond |= Q(phone__icontains=digits)

        qs = (
            Contact.objects.filter(user=request.user)
            .filter(cond)
            .order_by('name', 'phone')[:SUGGEST_LIMIT]
        )
        serializer = self.get_serializer(qs, many=True)
        return Response(
            {
                'success': True,
                'data': {'contacts': serializer.data},
                'message': 'OK',
                'errors': [],
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['get'])
    def search(self, request):
        """
        Look up a single contact for pay-in / payout verification.
        - `phone`: 10-digit number → exact match (unique per user).
        - `name`: case-insensitive partial match → exactly one match required; if several match, client must use phone.
        """
        raw_phone = request.query_params.get('phone', '') or ''
        phone = re.sub(r'\D', '', raw_phone)[:10]
        name_q = (request.query_params.get('name', '') or '').strip()

        if len(phone) == 10:
            try:
                contact = Contact.objects.get(user=request.user, phone=phone)
            except Contact.DoesNotExist:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'Contact not found',
                    'errors': [],
                }, status=status.HTTP_404_NOT_FOUND)
        elif name_q:
            if len(name_q) < 2:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'Enter at least 2 characters of the contact name',
                    'errors': [],
                }, status=status.HTTP_400_BAD_REQUEST)
            qs = Contact.objects.filter(
                user=request.user,
                name__icontains=name_q,
            ).order_by('name', 'phone')
            count = qs.count()
            if count == 0:
                return Response({
                    'success': False,
                    'data': None,
                    'message': 'Contact not found',
                    'errors': [],
                }, status=status.HTTP_404_NOT_FOUND)
            if count > 1:
                return Response({
                    'success': False,
                    'data': {
                        'matches': count,
                        'hint': 'Several contacts match this name. Search using the 10-digit phone number instead.',
                    },
                    'message': 'Multiple contacts match this name. Please search by phone number.',
                    'errors': [],
                }, status=status.HTTP_400_BAD_REQUEST)
            contact = qs.first()
        else:
            return Response({
                'success': False,
                'data': None,
                'message': 'Provide a 10-digit phone number or a contact name (at least 2 characters)',
                'errors': [],
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(contact)
        return Response({
            'success': True,
            'data': {'contact': serializer.data},
            'message': 'Contact found',
            'errors': [],
        }, status=status.HTTP_200_OK)
