# mPayHub Load Testing Guide (Locust)

Complete step-by-step guide for load testing **mPayHub** using **Locust**, tailored to your setup:

- **Production:** `partner.mpayhub.in` → nginx → Gunicorn (5 workers) → Django → PostgreSQL
- **External APIs:** Cashfree (KYC), BillAvenue (BBPS), Razorpay/PayU (pay-in) — **IP whitelisted on current server only**
- **Tool:** Locust (runs on your **local machine** or any PC — does **not** need IP whitelisting)

---

## Table of contents

1. [Goals and strategy](#1-goals-and-strategy)
2. [What you will and will not test](#2-what-you-will-and-will-not-test)
3. [Prerequisites](#3-prerequisites)
4. [Folder structure](#4-folder-structure)
5. [Step 1 — Create test users on server](#5-step-1--create-test-users-on-server)
6. [Step 2 — Export users to CSV](#6-step-2--export-users-to-csv)
7. [Step 3 — Install Locust on your local machine](#7-step-3--install-locust-on-your-local-machine)
8. [Step 4 — Create Locust files](#8-step-4--create-locust-files)
9. [Step 5 — Smoke test (5 users)](#9-step-5--smoke-test-5-users)
10. [Step 6 — Baseline load test](#10-step-6--baseline-load-test)
11. [Step 7 — Stress and soak tests](#11-step-7--stress-and-soak-tests)
12. [Step 8 — Monitor the server during tests](#12-step-8--monitor-the-server-during-tests)
13. [Step 9 — Read and report results](#13-step-9--read-and-report-results)
14. [Step 10 — Optional staging on same VPS](#14-step-10--optional-staging-on-same-vps)
15. [Troubleshooting](#15-troubleshooting)
16. [Final checklist](#16-final-checklist)

---

## 1. Goals and strategy

### What load testing answers

- How many **concurrent logged-in users** can the app handle?
- Which **API endpoints are slowest** (login, wallets, reports)?
- When do **errors** start (500, timeouts, DB exhaustion)?
- Are **5 Gunicorn workers** enough?

### Recommended strategy (given IP whitelist)

| Item | Decision |
|------|----------|
| **Where Locust runs** | Your **local laptop/PC** (or any machine with internet) |
| **Target server** | Current VPS (`https://partner.mpayhub.in`) for Phase 1 |
| **APIs to test** | **Read-only internal APIs** (auth, wallets, passbook, reports) |
| **APIs to skip** | KYC, real pay-in, BBPS bill pay (they call whitelisted external APIs) |
| **Load level on production** | Start small: **10–20 users**, off-peak, **5–10 minutes** |

**Important:** Locust only calls **your** `/api/...` URLs. Whitelist matters when **Django calls Cashfree/BBPS/Razorpay**, not when Locust calls Django.

---

## 2. What you will and will not test

### Safe to load test (internal / DB only)

| Endpoint | Method | Simulates |
|----------|--------|-----------|
| `/api/auth/login/` | POST | User login |
| `/api/auth/verify-mpin/` | POST | MPIN step |
| `/api/auth/me/` | GET | Profile load |
| `/api/wallets/` | GET | Dashboard wallets |
| `/api/passbook/` | GET | Passbook |
| `/api/reports/payin/` | GET | Pay-in report |
| `/api/reports/payout/` | GET | Payout report |
| `/api/reports/bbps/` | GET | BBPS report |
| `/api/reports/commission/` | GET | Commission report |
| `/api/users/` | GET | User list (distributors) |

### Do NOT load test on production

| Endpoint | Reason |
|----------|--------|
| `/api/auth/onboarding/kyc/*` | Calls **Cashfree** |
| `/api/fund-management/pay-in/*` (real gateway) | Calls **Razorpay/PayU** |
| `/api/bbps/*` (bill pay, fetch bill) | Calls **BillAvenue** |
| Admin gateway / BBPS config changes | Risk to live config |

### Production rate limits (will cause 429 if ignored)

| Endpoint | Limit |
|----------|-------|
| Login | **5/min per IP** |
| OTP | 3/min per IP |
| MPIN verify | per user limits |
| Many auth endpoints | 5–30/min |

**Rule:** Use **one unique test user per Locust virtual user**. Never run 50 users all logging in as the same phone number.

---

## 3. Prerequisites

### On the server (VPS)

- [ ] mPayHub is running (`curl -k https://partner.mpayhub.in/` or API root works)
- [ ] You have SSH access
- [ ] Django shell / manage.py works
- [ ] You know admin credentials (to create test users, or use shell script below)

Verify API is up:

```bash
curl -s https://partner.mpayhub.in/api/ | python3 -m json.tool
# Expected: {"service": "mpayhub-api", "status": "ok"}
```

### On your local machine (Locust runner)

- [ ] Python 3.10+ installed
- [ ] Internet access to `partner.mpayhub.in`
- [ ] ~500 MB free disk for reports

Check Python:

```bash
python3 --version
# Python 3.10.x or higher
```

---

## 4. Folder structure

Files live in the repo under `loadtest/`:

```text
MpayHub/
├── docs/
│   └── LOAD_TEST_GUIDE.md     ← this document
└── loadtest/
    ├── locustfile.py          # Main Locust test script
    ├── test_users.csv         # Test user credentials (copy from server; not committed)
    ├── .env.example           # Optional: host URL
    ├── reports/               # HTML reports (gitignored)
    └── scripts/
        ├── seed_loadtest_users.py   # Run ON SERVER — creates test users
        ├── export_users_csv.py      # Run ON SERVER — exports CSV
        └── monitor_loadtest.sh      # Run ON SERVER — live monitoring
```

---

## 5. Step 1 — Create test users on server

You need **at least as many test users as Locust virtual users**. For a 20-user test, create **20+ users**.

### Run the seed script (recommended)

SSH into your VPS:

```bash
cd ~/MpayHub/backend
source venv/bin/activate
python ../loadtest/scripts/seed_loadtest_users.py --count 50
```

Default credentials for seeded users:

| Field | Value |
|-------|-------|
| Password | `LoadTest@123` |
| MPIN | `654321` |
| Role | `Retailer` |
| Email | `loadtest{N}@loadtest.local` |

### Verify one user via API (from local machine)

```bash
curl -s -X POST https://partner.mpayhub.in/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"phone":"8900000001","password":"LoadTest@123"}' | python3 -m json.tool
```

Expect `"success": true` and `tokens.access` in the response.

---

## 6. Step 2 — Export users to CSV

On the **server**:

```bash
cd ~/MpayHub/backend
source venv/bin/activate
python ../loadtest/scripts/export_users_csv.py
```

Download to your local Locust machine:

```bash
scp ubuntu@YOUR_VPS_IP:/tmp/loadtest_users.csv ./MpayHub/loadtest/test_users.csv
```

Example `test_users.csv`:

```csv
phone,password,mpin,role
8900000001,LoadTest@123,654321,Retailer
8900000002,LoadTest@123,654321,Retailer
```

**Minimum rows:** same as max Locust users (e.g. 20 users → 20 CSV rows).

---

## 7. Step 3 — Install Locust on your local machine

### Linux / macOS

```bash
cd ~/MpayHub/loadtest
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
locust --version
```

### Windows (PowerShell)

```powershell
cd $HOME\MpayHub\loadtest
python -m venv venv
.\venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
locust --version
```

---

## 8. Step 4 — Create Locust files

The main script is `loadtest/locustfile.py` (already in the repo).

Optional environment file — copy `.env.example` to `.env`:

```bash
MPAYHUB_HOST=https://partner.mpayhub.in
```

Quick connectivity test:

```bash
curl -s -o /dev/null -w "HTTP %{http_code} in %{time_total}s\n" \
  https://partner.mpayhub.in/api/
```

---

## 9. Step 5 — Smoke test (5 users)

**Purpose:** Confirm scripts, credentials, and network work. **Duration: 2 minutes.**

### Using Locust Web UI

```bash
cd ~/MpayHub/loadtest
source venv/bin/activate
export MPAYHUB_HOST=https://partner.mpayhub.in
locust -f locustfile.py
```

Open browser: **http://localhost:8089**

| Field | Value |
|-------|-------|
| Number of users | **5** |
| Ramp up | **1** user/sec |
| Host | `https://partner.mpayhub.in` |

Click **Start swarming**. Run for **2 minutes**, then **Stop**.

### Headless smoke (alternative)

```bash
locust -f locustfile.py \
  --headless \
  -u 5 \
  -r 1 \
  -t 2m \
  --host https://partner.mpayhub.in \
  --html reports/smoke-$(date +%Y%m%d-%H%M).html
```

### Success criteria (smoke)

- [ ] Failures **< 1%**
- [ ] `POST /auth/login/` mostly **200**
- [ ] `GET /wallets/` mostly **200**
- [ ] Median response time **< 2s**

---

## 10. Step 6 — Baseline load test

**Purpose:** Normal expected load. **Run off-peak** (late night / early morning).

| Parameter | Value |
|-----------|-------|
| Users | **20** |
| Spawn rate | **2**/sec |
| Duration | **10 minutes** |
| CSV users | **≥ 20** unique phones |

```bash
mkdir -p reports

locust -f locustfile.py \
  --headless \
  -u 20 \
  -r 2 \
  -t 10m \
  --host https://partner.mpayhub.in \
  --html reports/baseline-20u-10m.html \
  2>&1 | tee reports/baseline.log
```

### Baseline success criteria (example)

| Metric | Target |
|--------|--------|
| Overall failure rate | **< 1%** |
| Login p95 | **< 1.5s** |
| Wallets / me p95 | **< 800ms** |
| Reports p95 | **< 2s** |
| 429 errors | **0** |

---

## 11. Step 7 — Stress and soak tests

Only after baseline passes. **Still read-only APIs only.**

```bash
# 50 users
locust -f locustfile.py --headless -u 50 -r 5 -t 15m \
  --host https://partner.mpayhub.in \
  --html reports/stress-50u.html

# Soak — 1 hour
locust -f locustfile.py --headless -u 30 -r 3 -t 1h \
  --host https://partner.mpayhub.in \
  --html reports/soak-30u-1h.html
```

Stop when failure rate **> 2%**, p95 **> 3s**, or CPU **> 90%** sustained.

---

## 12. Step 8 — Monitor the server during tests

On the VPS (second SSH session):

```bash
~/MpayHub/loadtest/scripts/monitor_loadtest.sh | tee /tmp/loadtest-monitor.log
```

Or manually:

```bash
htop
sudo journalctl -u mpayhub -f --no-pager
tail -f ~/MpayHub/backend/logs/django.log
sudo tail -f /var/log/nginx/access.log
```

Gunicorn runs with **5 workers** and **120s timeout** (`backend/run_gunicorn.sh`).

---

## 13. Step 9 — Read and report results

Open `reports/baseline-20u-10m.html` in a browser. Document:

| Field | Your result |
|-------|-------------|
| Date / time | |
| Target host | |
| Max users | |
| Duration | |
| Total requests | |
| Failure rate | |
| Slowest endpoint (p95) | |
| RPS at peak | |

---

## 14. Step 10 — Optional staging on same VPS

If you outgrow production smoke tests, add **staging on the same IP** (whitelist still works):

```
partner.mpayhub.in     → production DB + Gunicorn :8000
staging.mpayhub.in     → staging DB    + Gunicorn :8001
```

Locust then targets:

```bash
export MPAYHUB_HOST=https://staging.mpayhub.in
```

On staging you can additionally disable rate limits and use mock pay-in.

---

## 15. Troubleshooting

| Problem | Likely cause | Fix |
|---------|--------------|-----|
| **429 on login** | Rate limit (5/min/IP) | More unique users in CSV; lower spawn rate |
| **401 on wallets** | Login failed | Check CSV password; verify login step |
| **MPIN failed** | Wrong MPIN | Re-run seed script |
| **502 Bad Gateway** | Gunicorn crashed | `sudo systemctl restart mpayhub` |
| **Empty CSV** | Not exported | Re-run `export_users_csv.py` |

### Manual auth debug

```bash
TOKEN=$(curl -s -X POST https://partner.mpayhub.in/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"phone":"8900000001","password":"LoadTest@123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['tokens']['access'])")

curl -s -X POST https://partner.mpayhub.in/api/auth/verify-mpin/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"mpin":"654321"}'

curl -s https://partner.mpayhub.in/api/wallets/ \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool
```

---

## 16. Final checklist

### Before test

- [ ] Test users created (`seed_loadtest_users.py`)
- [ ] `test_users.csv` copied locally
- [ ] Manual curl login works
- [ ] Locust installed
- [ ] Off-peak window chosen

### After test

- [ ] Save HTML report to `loadtest/reports/`
- [ ] Optional: delete load-test users when done

```bash
# Django shell — preview cleanup
python manage.py shell -c "
from apps.authentication.models import User
qs = User.objects.filter(email__endswith='@loadtest.local')
print(f'Load-test users: {qs.count()}')
"
```

---

## Quick reference

```bash
# Seed users (server)
python ../loadtest/scripts/seed_loadtest_users.py --count 50

# Export CSV (server)
python ../loadtest/scripts/export_users_csv.py

# Smoke (local)
locust -f locustfile.py --host https://partner.mpayhub.in

# Baseline (local, headless)
locust -f locustfile.py --headless -u 20 -r 2 -t 10m \
  --host https://partner.mpayhub.in --html reports/baseline.html
```
