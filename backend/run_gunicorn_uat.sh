#!/bin/bash
# @deprecated Use run_gunicorn.sh (127.0.0.1:8000) — UAT now matches production via nginx + PM2.
# UAT: public bind on :8001 (direct access, no nginx required)
set -e
cd "$(dirname "$0")"
# Worker timeout must exceed Fingpay client timeout (default 180s) so slow
# onboarding/KYC image POSTs return a provider error instead of a hung UI.
exec ./venv/bin/gunicorn --access-logfile - --workers 3 --timeout 240 --bind 0.0.0.0:8001 config.wsgi:application
