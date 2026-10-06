"""
Bank account views for the mPayhub platform.
"""
from django.db.models import Q
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.bank_accounts.models import BankAccount
from apps.bank_accounts.pagination import BankAccountPagination
from apps.bank_accounts.serializers import (
    BankAccountLinkSerializer,
    BankAccountLookupSerializer,
    BankAccountSerializer,
    BankAccountValidationSerializer,
)
from apps.bank_accounts.services import (
    BankAccountLinkError,
    classify_saved_account,
    link_bank_account_to_contact,
    unlink_bank_account_from_contact,
    validate_bank_account,
)
from apps.contacts.models import Contact
from apps.core.exceptions import BankValidationFailed


class BankAccountViewSet(viewsets.ModelViewSet):
    """
    ViewSet for bank account management.
    """
    serializer_class = BankAccountSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = BankAccountPagination

    def get_queryset(self):
        """Filter bank accounts by authenticated user; optional ?contact=<id> scope."""
        queryset = BankAccount.objects.filter(
            user=self.request.user,
            is_deleted=False,
        ).select_related('contact')

        contact_raw = self.request.query_params.get('contact')
        if contact_raw is not None and str(contact_raw).strip() != '':
            try:
                contact_id = int(str(contact_raw).strip())
            except (TypeError, ValueError):
                return queryset.none()

            owns_contact = Contact.objects.filter(
                pk=contact_id, user=self.request.user, is_deleted=False
            ).exists()
            if not owns_contact:
                return queryset.none()
            queryset = queryset.filter(
                Q(contact_links__contact_id=contact_id, contact_links__is_deleted=False)
                | Q(contact_id=contact_id)
            ).distinct()

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

    def list(self, request, *args, **kwargs):
        """Return a stable envelope with `bank_accounts` for enterprise clients."""
        response = super().list(request, *args, **kwargs)
        if response.status_code != status.HTTP_200_OK:
            return response
        payload = response.data
        if isinstance(payload, dict) and 'results' in payload:
            return Response({
                'success': True,
                'data': {
                    'bank_accounts': payload.get('results', []),
                    'count': payload.get('count'),
                    'next': payload.get('next'),
                    'previous': payload.get('previous'),
                },
                'message': 'Bank accounts retrieved successfully',
                'errors': [],
            }, status=status.HTTP_200_OK)
        if isinstance(payload, list):
            return Response({
                'success': True,
                'data': {'bank_accounts': payload, 'count': len(payload)},
                'message': 'Bank accounts retrieved successfully',
                'errors': [],
            }, status=status.HTTP_200_OK)
        return response

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'data': None,
                'message': 'Validation error',
                'errors': serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        return Response({
            'success': True,
            'data': {'bank_account': serializer.data},
            'message': 'Bank account saved successfully',
            'errors': [],
        }, status=status.HTTP_201_CREATED)

    def perform_create(self, serializer):
        """Set user when creating bank account."""
        account = serializer.save(user=self.request.user)
        try:
            from apps.session_security.services.activity import record_bank_account_activity

            record_bank_account_activity(
                user=self.request.user, action='created', account=account
            )
        except Exception:  # noqa: BLE001
            pass
        return account

    def perform_update(self, serializer):
        account = serializer.save()
        try:
            from apps.session_security.services.activity import record_bank_account_activity

            record_bank_account_activity(
                user=self.request.user, action='updated', account=account
            )
        except Exception:  # noqa: BLE001
            pass
        return account

    def perform_destroy(self, instance):
        aid = getattr(instance, 'id', None)
        bank = getattr(instance, 'bank_name', '')
        num = str(getattr(instance, 'account_number', '') or '')
        instance.delete()
        try:
            from apps.session_security.services.activity import record_bank_account_activity

            class _Tmp:
                pass

            tmp = _Tmp()
            tmp.id = aid
            tmp.bank_name = bank
            tmp.account_number = num
            record_bank_account_activity(
                user=self.request.user, action='deleted', account=tmp
            )
        except Exception:  # noqa: BLE001
            pass

    def _owned_contact(self, contact_id):
        return Contact.objects.filter(
            pk=contact_id,
            user=self.request.user,
            is_deleted=False,
        ).first()

    @action(detail=False, methods=['post'], url_path='lookup')
    def lookup(self, request):
        """Check whether this account is already on the selected contact. No provider call."""
        serializer = BankAccountLookupSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'data': None,
                'message': 'Bank account lookup failed',
                'errors': serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)
        contact = self._owned_contact(serializer.validated_data['contact'])
        if contact is None:
            return Response({
                'success': False,
                'data': None,
                'message': 'Select a contact that belongs to you.',
                'errors': {'contact': ['Select a contact that belongs to you.']},
            }, status=status.HTTP_400_BAD_REQUEST)
        found = classify_saved_account(
            request.user,
            serializer.validated_data['account_number'],
            serializer.validated_data['ifsc'],
            contact,
        )
        account = found['bank_account']
        return Response({
            'success': True,
            'data': {
                'status': found['status'],
                'bank_account_id': getattr(account, 'id', None),
                'contacts': found['contacts'],
            },
            'message': 'Bank account lookup completed',
            'errors': [],
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='link')
    def link(self, request):
        """Add a contact link to an already verified account. No provider call and no fee."""
        serializer = BankAccountLinkSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'data': None,
                'message': 'Could not link this bank account',
                'errors': serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)
        contact = self._owned_contact(serializer.validated_data['contact'])
        account = BankAccount.objects.filter(
            pk=serializer.validated_data['bank_account'],
            user=request.user,
            is_deleted=False,
        ).first()
        if contact is None or account is None:
            return Response({
                'success': False,
                'data': None,
                'message': 'Bank account or contact was not found.',
                'errors': [],
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            link_bank_account_to_contact(account, contact)
        except BankValidationFailed as exc:
            return Response({
                'success': False,
                'data': None,
                'message': str(exc),
                'errors': [],
            }, status=status.HTTP_400_BAD_REQUEST)
        return Response({
            'success': True,
            'data': {'bank_account': BankAccountSerializer(account, context={'request': request}).data},
            'message': 'Bank account linked to this contact',
            'errors': [],
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='unlink')
    def unlink(self, request):
        """Remove one contact link. Does not delete the bank account row."""
        serializer = BankAccountLinkSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({
                'success': False,
                'data': None,
                'message': 'Could not remove this bank account from the contact',
                'errors': serializer.errors,
            }, status=status.HTTP_400_BAD_REQUEST)
        contact = self._owned_contact(serializer.validated_data['contact'])
        account = BankAccount.objects.filter(
            pk=serializer.validated_data['bank_account'],
            user=request.user,
            is_deleted=False,
        ).first()
        if contact is None or account is None:
            return Response({
                'success': False,
                'data': None,
                'message': 'Bank account or contact was not found.',
                'errors': [],
            }, status=status.HTTP_400_BAD_REQUEST)
        try:
            unlink_bank_account_from_contact(account, contact)
        except BankValidationFailed as exc:
            return Response({
                'success': False,
                'data': None,
                'message': str(exc),
                'errors': [],
            }, status=status.HTTP_400_BAD_REQUEST)
        account.refresh_from_db()
        return Response({
            'success': True,
            'data': {'bank_account': BankAccountSerializer(account, context={'request': request}).data},
            'message': 'Bank account removed from this contact',
            'errors': [],
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    @method_decorator(ratelimit(key='user', rate='5/m', method='POST'))
    def validate(self, request):
        """Validate bank account."""
        serializer = BankAccountValidationSerializer(data=request.data)
        if serializer.is_valid():
            contact = None
            contact_id = serializer.validated_data.get('contact')
            if contact_id is not None:
                contact = self._owned_contact(contact_id)
                if contact is None:
                    return Response({
                        'success': False,
                        'data': None,
                        'message': 'Select a contact that belongs to you.',
                        'errors': {'contact': ['Select a contact that belongs to you.']},
                    }, status=status.HTTP_400_BAD_REQUEST)
            try:
                result = validate_bank_account(
                    request.user,
                    serializer.validated_data['account_number'],
                    serializer.validated_data['ifsc'],
                    serializer.validated_data['mobile_number'],
                    contact=contact,
                )
                return Response({
                    'success': True,
                    'data': result,
                    'message': 'Bank account validated and saved successfully',
                    'errors': [],
                }, status=status.HTTP_200_OK)
            except BankAccountLinkError as exc:
                return Response({
                    'success': False,
                    'data': {
                        'code': exc.code,
                        'contacts': exc.contacts,
                        'bank_account_id': exc.bank_account_id,
                    },
                    'message': str(exc),
                    'errors': [],
                }, status=status.HTTP_400_BAD_REQUEST)
            except BankValidationFailed as e:
                return Response({
                    'success': False,
                    'data': None,
                    'message': str(e),
                    'errors': [],
                }, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'success': False,
            'data': None,
            'message': 'Bank account validation failed',
            'errors': serializer.errors,
        }, status=status.HTTP_400_BAD_REQUEST)
