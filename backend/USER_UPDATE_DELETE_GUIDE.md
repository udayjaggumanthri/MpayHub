# User Update and Delete Functionality

## Overview

Users can now be updated and deleted through both the Django Admin interface and the REST API.

## API Endpoints

### Update User (PUT/PATCH)

**Endpoint:** `PUT /api/users/{user_id}/` or `PATCH /api/users/{user_id}/`

**Permissions:**
- Admin can update any user
- Others can only update their subordinates (users in their hierarchy)

**Request Body (PUT - Full Update):**
```json
{
    "firstName": "John Updated",
    "lastName": "Doe Updated",
    "email": "updated@example.com",
    "alternatePhone": "9876543212",
    "businessName": "Updated Business Name",
    "businessAddress": "456 New St, City",
    "password": "newpassword123",
    "mpin": "123456",
    "is_active": true
}
```

**Request Body (PATCH - Partial Update):**
```json
{
    "firstName": "John",
    "is_active": false
}
```

**Response:**
```json
{
    "success": true,
    "data": {
        "user": {
            "id": 1,
            "user_id": "ADMIN1",
            "phone": "9876543210",
            "email": "updated@example.com",
            ...
        }
    },
    "message": "User updated successfully",
    "errors": []
}
```

### Delete User (DELETE)

**Endpoint:** `DELETE /api/users/{user_id}/`

**Permissions:**
- Only Admin can delete users
- Cannot delete your own account

**Response:**
```json
{
    "success": true,
    "data": {
        "user_id": "ADMIN1"
    },
    "message": "User deleted successfully",
    "errors": []
}
```

## Django Admin Interface

### Update User

1. Go to Django Admin: http://localhost:8000/admin/
2. Navigate to **Authentication > Users**
3. Click on a user to edit
4. Update fields:
   - Personal Information (first_name, last_name)
   - Email
   - Role
   - Active status
   - Password (change password link)
5. Click "Save"

**Note:** Phone number cannot be changed after user creation (for security).

### Delete User

1. Go to Django Admin: http://localhost:8000/admin/
2. Navigate to **Authentication > Users**
3. Select user(s) using checkboxes
4. Choose "Delete selected users" from the Action dropdown
5. Click "Go"
6. Confirm deletion

**Restrictions:**
- Only superusers can delete users
- You cannot delete your own account

## Updateable Fields

### User Model Fields
- `first_name` / `firstName`
- `last_name` / `lastName`
- `email`
- `password` (min 8 characters)
- `mpin` (6 digits)
- `is_active` (boolean)

### UserProfile Fields
- `alternate_phone` / `alternatePhone`
- `business_name` / `businessName`
- `business_address` / `businessAddress`

## Read-Only Fields

These fields cannot be updated:
- `user_id` (generated at creation)
- `phone` (cannot be changed after creation)
- `role` (use separate endpoint if needed)
- `created_at`
- `updated_at`

## Field Name Support

Both camelCase and snake_case are supported:
- `firstName` or `first_name`
- `lastName` or `last_name`
- `alternatePhone` or `alternate_phone`
- `businessName` or `business_name`
- `businessAddress` or `business_address`

## Examples

### Update User Name and Email
```json
PATCH /api/users/1/
{
    "firstName": "John",
    "lastName": "Doe",
    "email": "john.doe@example.com"
}
```

### Update Business Information
```json
PATCH /api/users/1/
{
    "businessName": "New Business Name",
    "businessAddress": "New Address"
}
```

### Deactivate User
```json
PATCH /api/users/1/
{
    "is_active": false
}
```

### Change Password
```json
PATCH /api/users/1/
{
    "password": "newsecurepassword123"
}
```

### Change MPIN
```json
PATCH /api/users/1/
{
    "mpin": "654321"
}
```

## Permissions

### Update Permissions
- **Admin**: Can update any user
- **Master Distributor**: Can update Distributors and Retailers under them
- **Distributor**: Can update Retailers under them
- **Retailer**: Cannot update other users

### Delete Permissions
- **Admin Only**: Only Admin role can delete users
- **Self-Protection**: Cannot delete your own account

## Error Responses

### Permission Denied (403)
```json
{
    "success": false,
    "data": null,
    "message": "You do not have permission to update this user",
    "errors": []
}
```

### Cannot Delete Self (400)
```json
{
    "success": false,
    "data": null,
    "message": "You cannot delete your own account",
    "errors": []
}
```

### Validation Errors (400)
```json
{
    "success": false,
    "data": null,
    "message": "User update failed",
    "errors": {
        "email": ["Email already registered."],
        "password": ["Password must be at least 8 characters."]
    }
}
```

## Testing in Postman

1. **Login** first to get access token
2. **Get User ID** from List Users or Create User response
3. **Update User** using PUT/PATCH request
4. **Delete User** using DELETE request (Admin only)

All endpoints are available in the Postman collection under "2. Users".
