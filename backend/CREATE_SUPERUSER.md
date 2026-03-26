# Creating Superuser

## Quick Method

Since the cache backend warnings are expected in development, use the `--skip-checks` flag:

```powershell
python manage.py createsuperuser --skip-checks
```

## Interactive Method

The `manage.py` file has been updated to automatically add `--skip-checks` for all commands (except `check`), so you can simply run:

```powershell
python manage.py createsuperuser
```

## Non-Interactive Method (for automation)

```powershell
python manage.py createsuperuser --skip-checks --phone 9876543210 --email admin@example.com --noinput
```

Then set the password separately using Django shell or admin interface.

## Note

The cache backend warnings (`django_ratelimit.E003`) are expected in development because:
- Rate limiting is disabled in development (`RATELIMIT_ENABLE = False`)
- We're using `locmem` cache which doesn't support atomic operations
- These warnings don't affect functionality

For production, you'll use Redis or Memcached which fully support rate limiting.
