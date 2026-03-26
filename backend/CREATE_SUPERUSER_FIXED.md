# Fixed: Createsuperuser Command

## Problem
The `createsuperuser` command was failing with:
```
TypeError: UserManager.create_superuser() missing 1 required positional argument: 'username'
```

## Root Cause
The User model uses `phone` as the USERNAME_FIELD instead of `username`, but the default UserManager expected `username`.

## Solution
1. **Added Custom UserManager** - Created a `UserManager` class that properly handles `phone` and `email` instead of `username`
2. **Updated User Model** - Added `objects = UserManager()` to the User model
3. **Custom Command** - Created a custom `createsuperuser` command (optional, but provides better UX)

## Usage

### Interactive Mode (Recommended)
```powershell
python manage.py createsuperuser
```
This will prompt for:
- Phone number
- Email
- Password (twice)

### Non-Interactive Mode
```powershell
python manage.py createsuperuser --phone 9876543210 --email admin@example.com --noinput
```
**Note:** You need to set the password via environment variable:
```powershell
$env:DJANGO_SUPERUSER_PASSWORD="yourpassword"
python manage.py createsuperuser --phone 9876543210 --email admin@example.com --noinput
```

### With All Options
```powershell
python manage.py createsuperuser --phone 9876543210 --email admin@example.com
```

## What Was Fixed

1. **UserManager** - Now properly handles `phone` and `email` in `create_user()` and `create_superuser()`
2. **User Model** - Uses the custom manager: `objects = UserManager()`
3. **Custom Command** - Provides better error messages and handles user_id generation

## Verification

After creating a superuser, you can verify it was created:
```powershell
python manage.py shell
>>> from apps.authentication.models import User
>>> User.objects.filter(is_superuser=True).values('phone', 'email', 'role')
```

## Next Steps

1. Create your superuser using the command above
2. Login to Django admin at http://localhost:8000/admin/
3. Use your phone number and password to login
