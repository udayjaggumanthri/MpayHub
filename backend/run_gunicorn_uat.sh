#!/bin/bash
# UAT: public bind on :8001 (direct access, no nginx required)
set -e
cd "$(dirname "$0")"
exec ./venv/bin/gunicorn --access-logfile - --workers 3 --timeout 120 --bind 0.0.0.0:8001 config.wsgi:application
