#!/bin/bash
exec venv/bin/gunicorn --access-logfile - --workers 5 --bind 0.0.0.0:8000 config.wsgi:application
