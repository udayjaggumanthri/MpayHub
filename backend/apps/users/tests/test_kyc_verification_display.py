from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from apps.users.kyc_display import (
    build_kyc_verification_payload,
    extract_aadhaar_fields_from_raw,
    extract_pan_fields_from_raw,
    persist_pan_verified_identity,
    viewer_may_see_full_kyc_verification,
)
from apps.users.models import KYC, UserProfile
from apps.users.serializers import UserDetailSerializer

User = get_user_model()


class KycVerificationDisplayTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            phone='9555555601',
            email='admin@test.com',
            password='secret123',
            role='Admin',
            user_id='ADM01',
            first_name='Admin',
            last_name='User',
        )
        self.retailer = User.objects.create_user(
            phone='9555555602',
            email='retailer@test.com',
            password='secret123',
            role='Retailer',
            user_id='R01',
            first_name='Uday',
            last_name='J',
        )
        self.sd = User.objects.create_user(
            phone='9555555603',
            email='sd@test.com',
            password='secret123',
            role='Super Distributor',
            user_id='SD01',
            first_name='Super',
            last_name='Dist',
        )
        UserProfile.objects.create(user=self.retailer, first_name='Uday', last_name='J')
        self.kyc = KYC.objects.create(
            user=self.retailer,
            pan='ABCPV1234D',
            pan_verified=True,
            aadhaar='XXXX5647',
            aadhaar_verified=True,
            verification_status='verified',
        )
        persist_pan_verified_identity(
            self.kyc,
            pan='ABCPV1234D',
            name='JOHN DOE',
            dob='1993-06-30',
            pan_type='Individual',
            provider_code='cashfree_pan',
            profile_updated=True,
        )
        self.factory = RequestFactory()

    def test_viewer_permissions(self):
        self.assertTrue(viewer_may_see_full_kyc_verification(self.admin, self.retailer))
        self.assertTrue(viewer_may_see_full_kyc_verification(self.retailer, self.retailer))
        self.assertFalse(viewer_may_see_full_kyc_verification(self.sd, self.retailer))

    def test_build_payload_includes_pan_details(self):
        payload = build_kyc_verification_payload(self.kyc)
        self.assertEqual(payload['pan']['name'], 'JOHN DOE')
        self.assertTrue(payload['profile_synced_from_kyc'])

    def test_build_payload_enriches_missing_name_from_profile(self):
        self.kyc.verified_identity = {
            'pan': {'pan': 'ABCPV1234D', 'name': '', 'date_of_birth': ''},
        }
        self.kyc.save(update_fields=['verified_identity', 'updated_at'])
        payload = build_kyc_verification_payload(self.kyc)
        self.assertEqual(payload['pan']['name'], 'Uday J')

    def test_build_payload_includes_all_pan_field_keys(self):
        payload = build_kyc_verification_payload(self.kyc)
        for key in (
            'pan',
            'name',
            'date_of_birth',
            'pan_type',
            'reference_id',
            'provider_code',
            'verified_at',
            'name_match_score',
            'name_match_result',
            'aadhaar_seeding_status',
            'aadhaar_seeding_status_desc',
            'father_name',
            'message',
            'pan_status',
            'last_updated_at',
            'name_provided',
            'masked_aadhaar_number',
        ):
            self.assertIn(key, payload['pan'])

    def test_extract_pan_fields_from_cashfree_sync_payload(self):
        extras = extract_pan_fields_from_raw({
            'valid': True,
            'pan_status': 'VALID',
            'father_name': 'NARASIMHA MURTHI',
            'name_match_score': 100,
            'name_match_result': 'DIRECT_MATCH',
            'aadhaar_seeding_status': 'Y',
            'aadhaar_seeding_status_desc': 'Aadhaar is linked to PAN',
            'message': 'PAN verified successfully',
            'last_updated_at': '01/01/2019',
            'name_provided': 'CHANDRA SEKHRARAO',
        })
        self.assertEqual(extras['father_name'], 'NARASIMHA MURTHI')
        self.assertEqual(extras['aadhaar_seeding_status'], 'Y')
        self.assertEqual(extras['aadhaar_seeding_status_desc'], 'Aadhaar is linked to PAN')
        self.assertEqual(extras['name_match_score'], '100')
        self.assertEqual(extras['name_match_result'], 'DIRECT_MATCH')
        self.assertEqual(extras['pan_status'], 'VALID')

    def test_extract_aadhaar_fields_from_nested_address(self):
        extras = extract_aadhaar_fields_from_raw({
            'care_of': 'S/O Jaggumanthri Narasimha Murthi',
            'year_of_birth': 1962,
            'message': 'Aadhaar Card Exists',
            'address': {
                'house': '001',
                'street': 'Ravikamtham',
                'district': 'Anakapalli',
                'state': 'Andhra Pradesh',
                'pincode': '531025',
                'country': 'India',
            },
        })
        self.assertEqual(extras['district'], 'Anakapalli')
        self.assertEqual(extras['pincode'], '531025')
        self.assertIn('Ravikamtham', extras['address'])
        self.assertEqual(extras['country'], 'India')
        self.assertEqual(extras['year_of_birth'], '1962')

    def test_extract_aadhaar_fields_from_split_pc_alias(self):
        extras = extract_aadhaar_fields_from_raw({
            'split_address': {
                'house': '12',
                'dist': 'Haveri',
                'pc': '581112',
                'state': 'Karnataka',
                'country': 'India',
            },
        })
        self.assertEqual(extras['pincode'], '581112')
        self.assertEqual(extras['district'], 'Haveri')

    def test_admin_sees_full_kyc_verification_on_user_detail(self):
        request = self.factory.get('/')
        request.user = self.admin
        data = UserDetailSerializer(
            self.retailer, context={'request': request}
        ).data
        self.assertEqual(data['kyc_verification']['pan']['name'], 'JOHN DOE')

    def test_hierarchy_viewer_sees_status_only(self):
        request = self.factory.get('/')
        request.user = self.sd
        data = UserDetailSerializer(
            self.retailer, context={'request': request}
        ).data
        self.assertTrue(data['kyc_verification']['pan_verified'])
        self.assertNotIn('pan', data['kyc_verification'])

    def test_self_sees_full_kyc_verification_on_user_detail(self):
        request = self.factory.get('/')
        request.user = self.retailer
        data = UserDetailSerializer(
            self.retailer, context={'request': request}
        ).data
        self.assertEqual(data['kyc_verification']['pan']['pan'], 'ABCPV1234D')
