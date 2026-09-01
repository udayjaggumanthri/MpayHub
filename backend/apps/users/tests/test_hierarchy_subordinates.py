"""Iterative BFS subordinates (same semantics as former recursion)."""
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.users.models import UserHierarchy

User = get_user_model()


def _user(phone, email, role, user_id):
    return User.objects.create_user(
        phone=phone,
        email=email,
        password='secret123',
        role=role,
        user_id=user_id,
    )


class HierarchySubordinatesTests(TestCase):
    def test_includes_indirect_descendants_and_excludes_self(self):
        sd = _user('9110000001', 'sd-hier@test.com', 'Super Distributor', 'SDH1')
        md = _user('9110000002', 'md-hier@test.com', 'Master Distributor', 'MDH1')
        dist = _user('9110000003', 'dt-hier@test.com', 'Distributor', 'DTH1')
        ret = _user('9110000004', 'rt-hier@test.com', 'Retailer', 'RTH1')
        UserHierarchy.objects.create(parent_user=sd, child_user=md)
        UserHierarchy.objects.create(parent_user=md, child_user=dist)
        UserHierarchy.objects.create(parent_user=dist, child_user=ret)

        subs = UserHierarchy.get_subordinates(sd)
        ids = {u.pk for u in subs}
        self.assertEqual(ids, {md.pk, dist.pk, ret.pk})
        self.assertNotIn(sd.pk, ids)
        self.assertEqual({u.role for u in subs}, {'Master Distributor', 'Distributor', 'Retailer'})

    def test_cycle_does_not_recurse_forever(self):
        a = _user('9110000011', 'a-cyc@test.com', 'Distributor', 'CYA1')
        b = _user('9110000012', 'b-cyc@test.com', 'Distributor', 'CYB1')
        UserHierarchy.objects.create(parent_user=a, child_user=b)
        UserHierarchy.objects.create(parent_user=b, child_user=a)
        subs = UserHierarchy.get_subordinates(a)
        self.assertEqual({u.pk for u in subs}, {b.pk})
