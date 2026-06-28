"""
mPayHub load test — read-only API flows (safe for production smoke/baseline).

Usage:
  locust -f locustfile.py
  locust -f locustfile.py --headless -u 20 -r 2 -t 10m --host https://partner.mpayhub.in
"""
from __future__ import annotations

import csv
import itertools
import os
from pathlib import Path

from locust import HttpUser, between, events, task

HOST = os.getenv("MPAYHUB_HOST", "https://partner.mpayhub.in")
API = "/api"
USERS_CSV = Path(__file__).parent / "test_users.csv"

USERS: list[dict] = []
if USERS_CSV.exists():
    with USERS_CSV.open(newline="", encoding="utf-8") as f:
        USERS = list(csv.DictReader(f))

user_cycle = itertools.cycle(USERS) if USERS else None


@events.init.add_listener
def on_locust_init(environment, **_kwargs):
    if not USERS:
        print("ERROR: test_users.csv missing or empty. Run seed + export scripts first.")
    else:
        print(f"Loaded {len(USERS)} test users from {USERS_CSV}")


class MpayHubRetailerUser(HttpUser):
    """Simulates a Retailer: login → MPIN → dashboard reads."""

    host = HOST
    wait_time = between(1, 3)

    def on_start(self):
        if not user_cycle:
            raise RuntimeError("No test users in test_users.csv")

        creds = next(user_cycle)
        self.phone = creds["phone"].strip()
        self.password = creds["password"].strip()
        self.mpin = creds["mpin"].strip()
        self.token: str | None = None

        if self._login():
            self._verify_mpin()

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _login(self) -> bool:
        with self.client.post(
            f"{API}/auth/login/",
            json={"phone": self.phone, "password": self.password},
            name="POST /auth/login/",
            catch_response=True,
        ) as resp:
            if resp.status_code == 429:
                resp.failure("Rate limited (429) — use more unique users or off-peak")
                return False
            if resp.status_code != 200:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:300]}")
                return False
            try:
                body = resp.json()
            except Exception:
                resp.failure("Invalid JSON")
                return False
            if not body.get("success"):
                resp.failure(body.get("message") or "login failed")
                return False
            self.token = body["data"]["tokens"]["access"]
            resp.success()
            return True

    def _verify_mpin(self) -> bool:
        if not self.token:
            return False
        with self.client.post(
            f"{API}/auth/verify-mpin/",
            json={"mpin": self.mpin},
            headers=self._headers(),
            name="POST /auth/verify-mpin/",
            catch_response=True,
        ) as resp:
            if resp.status_code != 200:
                resp.failure(f"MPIN HTTP {resp.status_code}")
                return False
            if not resp.json().get("success"):
                resp.failure("MPIN verification failed")
                return False
            resp.success()
            return True

    @task(5)
    def get_wallets(self):
        if not self.token:
            return
        self.client.get(
            f"{API}/wallets/",
            headers=self._headers(),
            name="GET /wallets/",
        )

    @task(3)
    def get_me(self):
        if not self.token:
            return
        self.client.get(
            f"{API}/auth/me/",
            headers=self._headers(),
            name="GET /auth/me/",
        )

    @task(3)
    def get_passbook(self):
        if not self.token:
            return
        self.client.get(
            f"{API}/passbook/",
            headers=self._headers(),
            name="GET /passbook/",
            params={"page": 1},
        )

    @task(2)
    def get_payin_report(self):
        if not self.token:
            return
        self.client.get(
            f"{API}/reports/payin/",
            headers=self._headers(),
            name="GET /reports/payin/",
            params={"scope": "self", "page": 1},
        )

    @task(1)
    def get_commission_report(self):
        if not self.token:
            return
        self.client.get(
            f"{API}/reports/commission/",
            headers=self._headers(),
            name="GET /reports/commission/",
            params={"scope": "self", "page": 1},
        )


class MpayHubDistributorUser(MpayHubRetailerUser):
    """Distributor-style team reports + user list."""

    wait_time = between(2, 5)

    @task(2)
    def team_payin_report(self):
        if not self.token:
            return
        self.client.get(
            f"{API}/reports/payin/",
            headers=self._headers(),
            name="GET /reports/payin/?scope=team",
            params={"scope": "team", "page": 1},
        )

    @task(1)
    def list_users(self):
        if not self.token:
            return
        self.client.get(
            f"{API}/users/",
            headers=self._headers(),
            name="GET /users/",
            params={"page": 1},
        )


class HealthCheckUser(HttpUser):
    """Lightweight API root check — connectivity smoke only."""

    host = HOST
    wait_time = between(5, 10)

    @task
    def api_root(self):
        self.client.get("/", name="GET / (api root)")
