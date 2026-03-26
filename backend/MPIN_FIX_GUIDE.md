# MPIN Fix Guide

## Issues Fixed

### 1. MPIN Encryption/Decryption Bug
**Problem:** The `encrypt_mpin` and `decrypt_mpin` functions were generating a new encryption key each time using `Fernet.generate_key()`, which meant encrypted MPINs could never be decrypted.

**Solution:** Fixed to use a consistent key derived from Django's `SECRET_KEY` using SHA256 hashing.

### 2. MPIN Field Not Visible in Django Admin
**Problem:** MPIN field was not visible in the Django admin interface, making it impossible to set or view MPIN status.

**Solution:** 
- Added `mpin_status` readonly field showing if MPIN is set
- Added `mpin` field in the form for setting/updating MPIN
- MPIN is now visible in the Authentication section of the user edit form

### 3. MPIN Verification Failing
**Problem:** MPIN verification was failing because of the encryption bug.

**Solution:** With the encryption fix, MPIN verification should now work correctly.

## How to Use

### Setting MPIN via Django Admin

1. Go to Django Admin: http://localhost:8000/admin/
2. Navigate to **Authentication > Users**
3. Click on a user to edit
4. In the **Authentication** section, you'll see:
   - **MPIN Status**: Shows "✓ MPIN Set" (green) or "✗ MPIN Not Set" (red)
   - **MPIN**: Password field to enter new MPIN (6 digits)
5. Enter a 6-digit MPIN and click **Save**

### Setting MPIN via API

**During User Creation:**
```json
POST /api/users/
{
    "phone": "9876543210",
    "email": "user@example.com",
    "password": "password123",
    "firstName": "John",
    "lastName": "Doe",
    "role": "Retailer",
    "mpin": "123456"
}
```

**Updating MPIN:**
```json
PATCH /api/users/{user_id}/
{
    "mpin": "654321"
}
```

### Verifying MPIN via API

```json
POST /api/auth/verify-mpin/
Headers: {
    "Authorization": "Bearer {access_token}"
}
Body: {
    "mpin": "123456"
}
```

## Testing

1. **Create a user with MPIN:**
   ```bash
   POST /api/users/
   {
       "phone": "9876543210",
       "email": "test@example.com",
       "password": "password123",
       "firstName": "Test",
       "lastName": "User",
       "role": "Retailer",
       "mpin": "123456"
   }
   ```

2. **Login to get access token:**
   ```bash
   POST /api/auth/login/
   {
       "phone": "9876543210",
       "password": "password123"
   }
   ```

3. **Verify MPIN:**
   ```bash
   POST /api/auth/verify-mpin/
   Headers: Authorization: Bearer {access_token}
   {
       "mpin": "123456"
   }
   ```

## Important Notes

- MPIN must be exactly 6 digits
- MPIN is encrypted using Fernet symmetric encryption
- The encryption key is derived from Django's `SECRET_KEY`
- MPIN cannot be viewed once set (only status is visible)
- To change MPIN, enter a new 6-digit value

## Troubleshooting

### MPIN Verification Still Failing

1. **Check if MPIN was set:**
   - Go to Django Admin > Users > Select user
   - Check "MPIN Status" field
   - If "MPIN Not Set", set it first

2. **Verify MPIN was set correctly:**
   - Check database: `SELECT mpin_hash FROM users WHERE phone='9876543210';`
   - Should not be NULL

3. **Check encryption key:**
   - Ensure `SECRET_KEY` in settings is consistent
   - If `SECRET_KEY` changes, all encrypted MPINs will be invalid

4. **Test encryption/decryption:**
   ```python
   from apps.core.utils import encrypt_mpin, decrypt_mpin
   encrypted = encrypt_mpin("123456")
   decrypted = decrypt_mpin(encrypted)
   assert decrypted == "123456"  # Should be True
   ```
