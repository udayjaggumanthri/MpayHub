"""
Create load-test users. Run on server:

  cd ~/MpayHub/backend
  source venv/bin/activate
  python ../loadtest/scripts/seed_loadtest_users.py --count 50
"""
from __future__ import annotations

import argparse
import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, BACKEND_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django

django.setup()

from apps.authentication.models import User
from apps.core.utils import generate_user_id
from apps.users.models import KYC, UserHierarchy, UserProfile
from apps.wallets.models import Wallet

PASSWORD = "LoadTest@123"
MPIN = "654321"
ROLE = "Retailer"
EMAIL_DOMAIN = "loadtest.local"


def get_admin() -> User:
    admin = User.objects.filter(role="Admin", is_active=True).first()
    if not admin:
        raise RuntimeError("No active Admin user found.")
    return admin


def create_loadtest_user(index: int, admin: User) -> dict:
    phone = f"89{index:08d}"[-10:]
    if User.objects.filter(phone=phone).exists():
        user = User.objects.get(phone=phone)
        return {"phone": phone, "password": PASSWORD, "mpin": MPIN, "role": user.role}

    user_id = generate_user_id(ROLE)

    user = User.objects.create_user(
        phone=phone,
        email=f"loadtest{index}@{EMAIL_DOMAIN}",
        password=PASSWORD,
        role=ROLE,
        user_id=user_id,
        first_name="Load",
        last_name=f"Test{index}",
        is_active=True,
    )
    user.set_mpin(MPIN)
    user.save()

    UserProfile.objects.get_or_create(
        user=user,
        defaults={"first_name": "Load", "last_name": f"Test{index}"},
    )
    KYC.objects.get_or_create(user=user)
    UserHierarchy.objects.get_or_create(parent_user=admin, child_user=user)

    for wtype in ("main", "commission", "bbps"):
        Wallet.objects.get_or_create(user=user, wallet_type=wtype, defaults={"balance": 0})

    return {"phone": phone, "password": PASSWORD, "mpin": MPIN, "role": ROLE}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed mPayHub load-test users")
    parser.add_argument("--count", type=int, default=50, help="Number of users to create")
    args = parser.parse_args()

    admin = get_admin()
    for i in range(1, args.count + 1):
        create_loadtest_user(i, admin)
        if i % 10 == 0:
            print(f"  ... {i}/{args.count}")

    print(f"\nDone. {args.count} load-test users ready.")
    print(f"  Password: {PASSWORD}")
    print(f"  MPIN:     {MPIN}")
    print(f"  Email:    loadtestN@{EMAIL_DOMAIN}")


if __name__ == "__main__":
    main()
