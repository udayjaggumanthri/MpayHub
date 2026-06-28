#!/bin/bash
# Live server monitoring during load tests. Run on VPS:
#   ~/MpayHub/loadtest/scripts/monitor_loadtest.sh | tee /tmp/loadtest-monitor.log

set -euo pipefail

DB_NAME="${MPAYHUB_DB_NAME:-mpayhub}"

while true; do
  echo "===== $(date -Iseconds) ====="
  echo "--- Load ---"
  uptime
  echo "--- Memory ---"
  free -h | head -2
  echo "--- Gunicorn workers ---"
  pgrep -af gunicorn 2>/dev/null | wc -l || echo "0"
  echo "--- PostgreSQL connections ---"
  sudo -u postgres psql -tAc \
    "SELECT count(*) FROM pg_stat_activity WHERE datname='${DB_NAME}';" 2>/dev/null || echo "n/a"
  echo ""
  sleep 10
done
