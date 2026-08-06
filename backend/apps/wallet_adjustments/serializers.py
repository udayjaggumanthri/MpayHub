from decimal import Decimal

from rest_framework import serializers

from apps.wallet_adjustments.models import WalletAdjustment


class WalletAdjustmentCreateSerializer(serializers.Serializer):
    user_id = serializers.IntegerField(min_value=1)
    wallet_type = serializers.ChoiceField(choices=['main', 'bbps'])
    adjustment_type = serializers.ChoiceField(choices=['CREDIT', 'DEBIT'])
    amount = serializers.DecimalField(
        max_digits=18, decimal_places=4, min_value=Decimal('0.0001')
    )
    reference_number = serializers.CharField(max_length=100, trim_whitespace=True)
    reason_category = serializers.ChoiceField(
        choices=[c[0] for c in WalletAdjustment.REASON_CATEGORY_CHOICES]
    )
    remarks = serializers.CharField(min_length=5, max_length=2000, trim_whitespace=True)
