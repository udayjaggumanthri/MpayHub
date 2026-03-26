# Fixed: User Creation API Issues

## Problems Identified

1. **Field Name Mismatch**: API expected `first_name`/`last_name` (snake_case) but received `firstName`/`lastName` (camelCase)
2. **Password Too Short**: Password must be at least 8 characters (received "1234")
3. **MPIN Required**: MPIN field was required but not provided
4. **Missing Fields**: PAN and Aadhaar fields were not in the serializer

## Solutions Implemented

### 1. CamelCase to Snake_Case Conversion
Added `to_internal_value()` method to automatically convert camelCase field names to snake_case:
- `firstName` → `first_name`
- `lastName` → `last_name`
- `alternatePhone` → `alternate_phone`
- `businessName` → `business_name`
- `businessAddress` → `business_address`

### 2. Made MPIN Optional
- Changed `mpin` field to `required=False`
- MPIN can now be set later if not provided during user creation
- Updated service to handle optional MPIN

### 3. Added PAN and Aadhaar Fields
- Added `pan` and `aadhaar` fields to the serializer (both optional)
- These are stored in the KYC model during user creation

### 4. Password Validation
- Password must be at least 8 characters (enforced by `min_length=8`)

## Correct Request Format

### Using camelCase (Now Supported)
```json
{
    "phone": "9492346026",
    "email": "udayjaggumanthri1@gmail.com",
    "password": "password123",
    "firstName": "jaggumanthri",
    "lastName": "uday",
    "role": "Distributor",
    "alternatePhone": "9652488158",
    "businessName": "uday Business",
    "businessAddress": "123 Main St, City",
    "pan": "ABCDE1234F",
    "aadhaar": "287663698750",
    "mpin": "123456"
}
```

### Using snake_case (Also Supported)
```json
{
    "phone": "9492346026",
    "email": "udayjaggumanthri1@gmail.com",
    "password": "password123",
    "first_name": "jaggumanthri",
    "last_name": "uday",
    "role": "Distributor",
    "alternate_phone": "9652488158",
    "business_name": "uday Business",
    "business_address": "123 Main St, City",
    "pan": "ABCDE1234F",
    "aadhaar": "287663698750",
    "mpin": "123456"
}
```

## Field Requirements

### Required Fields
- `phone` - 10 digits
- `email` - Valid email format
- `password` - Minimum 8 characters
- `first_name` (or `firstName`) - Max 100 characters
- `last_name` (or `lastName`) - Max 100 characters
- `role` - One of: Admin, Master Distributor, Distributor, Retailer

### Optional Fields
- `alternate_phone` (or `alternatePhone`) - 10 digits
- `business_name` (or `businessName`) - Max 200 characters
- `business_address` (or `businessAddress`) - Any text
- `pan` - 10 characters (format: 5 letters, 4 digits, 1 letter)
- `aadhaar` - 12 digits
- `mpin` - 6 digits (can be set later if not provided)

## Testing

Try the request again with:
1. ✅ Use `firstName` and `lastName` (camelCase) - will be automatically converted
2. ✅ Use password with at least 8 characters (e.g., "password123")
3. ✅ Include `mpin` as "123456" (6 digits) or omit it (optional)
4. ✅ All other fields remain the same

## Updated Postman Collection

The Postman collection has been updated to include `mpin` in the example request body.
