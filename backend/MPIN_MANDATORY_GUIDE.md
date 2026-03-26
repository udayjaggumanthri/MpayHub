# MPIN is Now Mandatory for All User Creation

## Overview

MPIN (Mobile PIN) is now a **mandatory field** for all user creation, including:
- Superuser creation via `createsuperuser` command
- User creation via Django Admin
- User creation via API (`POST /api/users/`)

## Changes Made

### 1. Createsuperuser Command
- Now prompts for MPIN during interactive creation
- Validates MPIN (must be 6 digits)
- Requires MPIN confirmation
- Sets MPIN automatically after user creation

### 2. User Creation Serializer
- `mpin` field is now `required=True`
- Validation ensures MPIN is exactly 6 digits
- Cannot create user without MPIN

### 3. Django Admin
- MPIN field is required for new users
- MPIN field is optional for existing users (can update or leave blank)
- Form validation enforces MPIN requirement

### 4. User Service
- `create_user` function now requires MPIN
- Raises error if MPIN is missing or invalid

## Usage

### Creating Superuser (Interactive)

```powershell
python manage.py createsuperuser
```

You will be prompted for:
1. **Phone:** 10-digit phone number
2. **Email:** Email address
3. **Password:** Password (hidden)
4. **Password (again):** Confirm password
5. **MPIN:** 6-digit MPIN (NEW - REQUIRED)
6. **MPIN (again):** Confirm MPIN (NEW - REQUIRED)

**Example:**
```
Phone: 9876543210
Email: admin@example.com
Password: ********
Password (again): ********
MPIN (6 digits): ******
MPIN (again): ******
Superuser created successfully with phone: 9876543210
MPIN has been set for the superuser.
```

### Creating Superuser (Non-Interactive)

```powershell
$env:DJANGO_SUPERUSER_PASSWORD="YourPassword123"
$env:DJANGO_SUPERUSER_MPIN="123456"
python manage.py createsuperuser --phone 9876543210 --email admin@example.com --noinput
```

**Note:** Both `DJANGO_SUPERUSER_PASSWORD` and `DJANGO_SUPERUSER_MPIN` environment variables are required.

### Creating User via API

**Request:**
```json
POST /api/users/
{
    "phone": "9876543211",
    "email": "user@example.com",
    "password": "password123",
    "firstName": "John",
    "lastName": "Doe",
    "role": "Retailer",
    "mpin": "123456"  // REQUIRED - 6 digits
}
```

**Response (if MPIN missing):**
```json
{
    "success": false,
    "message": "Validation failed",
    "errors": {
        "mpin": ["MPIN is required and cannot be blank."]
    }
}
```

### Creating User via Django Admin

1. Navigate to **Authentication > Users**
2. Click **Add User**
3. Fill in all required fields including:
   - Phone
   - Email
   - Password
   - **MPIN** (required - 6 digits)
   - First Name
   - Last Name
   - Role
4. Click **Save**

**Note:** The form will not allow saving without a valid MPIN.

## Validation Rules

1. **MPIN Length:** Must be exactly 6 digits
2. **MPIN Format:** Must contain only numbers (0-9)
3. **MPIN Required:** Cannot be blank or null for new users
4. **MPIN Optional:** For existing users, MPIN can be updated or left blank (keeps current MPIN)

## Error Messages

### Missing MPIN
```
MPIN is required and cannot be blank.
```

### Invalid MPIN Format
```
MPIN must be exactly 6 digits.
```

### MPIN Mismatch (createsuperuser)
```
MPINs do not match.
```

## Security Notes

1. **MPIN Encryption:** MPINs are encrypted using Fernet symmetric encryption
2. **MPIN Storage:** Stored as `mpin_hash` in the database (encrypted)
3. **MPIN Verification:** Uses `user.check_mpin(mpin)` method
4. **Two-Step Verification:** Users must provide both password and MPIN for login

## Updating Existing Users

For existing users without MPIN:
1. Go to Django Admin
2. Edit the user
3. The MPIN field will show as **required** (red indicator)
4. Enter a 6-digit MPIN
5. Save

## Testing

### Test Superuser Creation
```powershell
python manage.py createsuperuser
# Follow prompts and ensure MPIN is required
```

### Test API User Creation
```bash
curl -X POST http://localhost:8000/api/users/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "9876543212",
    "email": "test@example.com",
    "password": "password123",
    "firstName": "Test",
    "lastName": "User",
    "role": "Retailer",
    "mpin": "123456"
  }'
```

### Test Without MPIN (Should Fail)
```bash
curl -X POST http://localhost:8000/api/users/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "phone": "9876543213",
    "email": "test2@example.com",
    "password": "password123",
    "firstName": "Test",
    "lastName": "User",
    "role": "Retailer"
  }'
# Should return error: MPIN is required
```

## Migration Notes

If you have existing users without MPIN:
1. They will need to set MPIN before they can use the application
2. Admin can set MPIN via Django Admin
3. Users can set MPIN via API: `POST /api/users/{id}/` with `mpin` field

## Summary

✅ **MPIN is now mandatory for all new user creation**
✅ **Superuser creation requires MPIN**
✅ **API user creation requires MPIN**
✅ **Django Admin requires MPIN for new users**
✅ **MPIN validation ensures 6-digit format**
✅ **MPIN is encrypted before storage**
