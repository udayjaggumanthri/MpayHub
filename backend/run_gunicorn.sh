#!/bin/bash
# PM2 / production: bind localhost only — nginx is the public entry (80/443).
# Stop systemd first: sudo systemctl stop mpayhub
set -e
cd "$(dirname "$0")"
./venv/bin/python manage.py warmup_bbps_catalog || true
exec ./venv/bin/gunicorn --access-logfile - --workers 5 --timeout 120 --bind 127.0.0.1:8002 config.wsgi:application
