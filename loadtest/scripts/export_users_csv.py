"""
Export load-test users to CSV. Run on server:

  cd ~/MpayHub/backend
  source venv/bin/activate
  python ../loadtest/scripts/export_users_csv.py

Then copy to your Locust machine:
  scp ubuntu@VPS:/tmp/loadtest_users.csv ./loadtest/test_users.csv
"""
from __future__ import annotations

import csv
import os
import sys

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
sys.path.insert(0, BACKEND_ROOT)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")

import django

django.setup()

from apps.authentication.models import User

OUTPUT = "/tmp/loadtest_users.csv"
PASSWORD = "LoadTest@123"
MPIN = "654321"


def main() -> None:
    users = User.objects.filter(email__endswith="@loadtest.local", is_active=True).order_by("phone")

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["phone", "password", "mpin", "role"])
        for user in users:
            writer.writerow([user.phone, PASSWORD, MPIN, user.role])

    print(f"Exported {users.count()} users to {OUTPUT}")


if __name__ == "__main__":
    main()
