#!/usr/bin/env bash
# Sync local Django MEDIA_ROOT into the shared S3 bucket under AWS_S3_MEDIA_PREFIX.
# Does NOT enable USE_S3 — run cutover separately after verifying objects exist.
#
# Usage (from repo root or backend/):
#   export AWS_ACCESS_KEY_ID=...
#   export AWS_SECRET_ACCESS_KEY=...
#   export AWS_STORAGE_BUCKET_NAME=mpayhub-prod-s3
#   export AWS_S3_REGION_NAME=ap-south-1
#   export AWS_S3_MEDIA_PREFIX=uat   # or prod
#   ./scripts/sync-media-to-s3.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MEDIA_DIR="${MEDIA_DIR:-$ROOT/backend/media}"
BUCKET="${AWS_STORAGE_BUCKET_NAME:?Set AWS_STORAGE_BUCKET_NAME}"
PREFIX="${AWS_S3_MEDIA_PREFIX:?Set AWS_S3_MEDIA_PREFIX (uat or prod)}"
REGION="${AWS_S3_REGION_NAME:-ap-south-1}"
PREFIX="${PREFIX#/}"
PREFIX="${PREFIX%/}"

if [[ ! -d "$MEDIA_DIR" ]]; then
  echo "MEDIA_DIR not found: $MEDIA_DIR" >&2
  exit 1
fi

echo "Syncing $MEDIA_DIR -> s3://$BUCKET/$PREFIX/ (region=$REGION)"
du -sh "$MEDIA_DIR"
aws s3 sync "$MEDIA_DIR/" "s3://$BUCKET/$PREFIX/" --region "$REGION"
echo "Done. Keep local media until USE_S3 cutover is verified."
echo "Next: set USE_S3=True in backend/.env, pm2 restart mpayhub-backend --update-env"
echo "Then: cd backend && ./venv/bin/python manage.py verify_media_storage --limit 20"
