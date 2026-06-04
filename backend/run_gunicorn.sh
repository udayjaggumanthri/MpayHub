#!/bin/bash
# PM2 / production: bind localhost only (nginx proxies public traffic).
# Stop systemd first: sudo systemctl stop mpayhub
set -e
cd "$(dirname "$0")"
exec ./venv/bin/gunicorn --access-logfile - --workers 5 --timeout 120 --bind 127.0.0.1:8000 config.wsgi:application
