# Complete Postman Collection Guide

## Overview

This Postman collection covers **ALL** API endpoints in the mPayhub platform, organized into 11 comprehensive sections with complete CRUD operations and custom actions.

## Collection Structure

### 1. Authentication (8 endpoints)
- ✅ Login (auto-saves tokens)
- ✅ Verify MPIN
- ✅ Send OTP
- ✅ Verify OTP
- ✅ Reset Password
- ✅ Refresh Token (auto-updates tokens)
- ✅ Get Current User
- ✅ Logout

### 2. Users (9 endpoints)
- ✅ List Users (with role filter)
- ✅ Create User (with full profile & KYC)
- ✅ Get User Detail
- ✅ Update User
- ✅ Delete User
- ✅ Verify PAN
- ✅ Send Aadhaar OTP
- ✅ Verify Aadhaar OTP
- ✅ Get Subordinates

### 3. Wallets (3 endpoints)
- ✅ Get All Wallets
- ✅ Get Wallet by Type (main/commission/bbps)
- ✅ Get Wallet History (with pagination)

### 4. Fund Management (5 endpoints)
- ✅ Load Money
- ✅ Get Load Money List (with filters)
- ✅ Payout
- ✅ Get Payout List (with filters)
- ✅ Get Gateways

### 5. BBPS - Bill Payments (6 endpoints)
- ✅ Get Categories
- ✅ Get Billers by Category
- ✅ Fetch Bill
- ✅ Pay Bill
- ✅ Get Bill Payments List (with filters)
- ✅ Get Bill Payment Detail

### 6. Contacts (6 endpoints)
- ✅ List Contacts (with filters: name, email, phone)
- ✅ Create Contact
- ✅ Get Contact Detail
- ✅ Update Contact
- ✅ Delete Contact
- ✅ Search Contact by Phone

### 7. Bank Accounts (6 endpoints)
- ✅ List Bank Accounts (with filters)
- ✅ Validate Bank Account (charges ₹3.00)
- ✅ Create Bank Account
- ✅ Get Bank Account Detail
- ✅ Update Bank Account
- ✅ Delete Bank Account

### 8. Transactions (2 endpoints)
- ✅ List Transactions (with filters: type, status, pagination)
- ✅ Get Transaction Detail

### 9. Passbook (1 endpoint)
- ✅ Get Passbook Entries (with filters: service, date range, pagination)

### 10. Reports (4 endpoints)
- ✅ Pay In Report (with date range)
- ✅ Pay Out Report (with date range)
- ✅ BBPS Report (with date range)
- ✅ Commission Report (with date range)

### 11. Admin Panel (17 endpoints)

#### Announcements (5 endpoints)
- ✅ List Announcements
- ✅ Create Announcement
- ✅ Get Announcement Detail
- ✅ Update Announcement
- ✅ Delete Announcement

#### Payment Gateways (6 endpoints)
- ✅ List Payment Gateways
- ✅ Create Payment Gateway
- ✅ Get Payment Gateway Detail
- ✅ Update Payment Gateway
- ✅ Toggle Payment Gateway Status
- ✅ Delete Payment Gateway

#### Payout Gateways (6 endpoints)
- ✅ List Payout Gateways
- ✅ Create Payout Gateway
- ✅ Get Payout Gateway Detail
- ✅ Update Payout Gateway
- ✅ Toggle Payout Gateway Status
- ✅ Delete Payout Gateway

## Total Endpoints: 63

## Key Features

### Automatic Token Management
- Login request automatically saves `access_token`, `refresh_token`, `user_id`, and `user_role`
- Refresh Token request automatically updates tokens
- All authenticated requests use `Bearer {{access_token}}`

### Automatic ID Capture
- Create User → saves `new_user_id`
- Create Contact → saves `contact_id`
- Validate Bank Account → saves `beneficiary_name`
- Create Bank Account → saves `bank_account_id`
- Create Announcement → saves `announcement_id`
- Create Payment Gateway → saves `gateway_id`
- Create Payout Gateway → saves `payout_gateway_id`

### Complete Workflows

#### User Onboarding Flow
1. Login
2. Create User (with KYC details)
3. Verify PAN
4. Send Aadhaar OTP
5. Verify Aadhaar OTP
6. Get User Detail

#### Fund Management Flow
1. Login
2. Get Wallets (check balance)
3. Get Gateways
4. Load Money
5. Get Load Money List
6. Create Contact
7. Validate Bank Account
8. Create Bank Account
9. Payout
10. Get Payout List

#### Bill Payment Flow
1. Login
2. Get BBPS Categories
3. Get Billers by Category
4. Fetch Bill
5. Pay Bill
6. Get Bill Payments List
7. Get Bill Payment Detail

#### Admin Management Flow
1. Login (as Admin)
2. Create Announcement
3. Create Payment Gateway
4. Create Payout Gateway
5. Toggle Gateway Status
6. List Announcements

## Environment Variables

The collection uses these variables (auto-managed where possible):

- `base_url` - API base URL (default: http://localhost:8000)
- `access_token` - JWT access token (auto-set)
- `refresh_token` - JWT refresh token (auto-set)
- `user_id` - Current user ID (auto-set)
- `user_role` - Current user role (auto-set)
- `new_user_id` - Newly created user ID (auto-set)
- `contact_id` - Contact ID (auto-set)
- `bank_account_id` - Bank account ID (auto-set)
- `beneficiary_name` - Validated beneficiary name (auto-set)
- `announcement_id` - Announcement ID (auto-set)
- `gateway_id` - Payment gateway ID (auto-set)
- `payout_gateway_id` - Payout gateway ID (auto-set)

## Import Instructions

1. **Import Collection:**
   - Open Postman
   - Click "Import" button
   - Select `postman_collection.json` file
   - Collection will be imported with all 63 endpoints

2. **Import Environment:**
   - Click "Import" button again
   - Select `postman_environment.json` file
   - Select the imported environment from the dropdown

3. **Start Testing:**
   - Go to "1. Authentication > Login"
   - Use default credentials (see below)
   - Click "Send"
   - Tokens will be automatically saved

## Default Test Credentials

### Admin User
- Phone: `9876543210`
- Password: `admin123`
- MPIN: `1234`
- Role: Admin

### Master Distributor
- Phone: `9876543211`
- Password: `md123`
- MPIN: `1111`
- Role: Master Distributor

### Distributor
- Phone: `9876543212`
- Password: `d123`
- MPIN: `2222`
- Role: Distributor

### Retailer
- Phone: `9876543213`
- Password: `r123`
- MPIN: `3333`
- Role: Retailer

## Response Format

All API responses follow this standardized format:

```json
{
    "success": true/false,
    "data": { ... },
    "message": "Success message",
    "errors": []
}
```

## Testing Tips

1. **Follow the Workflows:** Use the suggested flows above for complete testing
2. **Check Auto-Saved Variables:** After creating resources, check environment variables
3. **Use Filters:** Most list endpoints support query parameters for filtering
4. **Pagination:** List endpoints support `limit` and `offset` parameters
5. **Error Handling:** All errors follow the standard format with `success: false` and `errors` array

## Complete Endpoint Coverage

✅ All authentication flows
✅ All user management operations
✅ All wallet operations
✅ All fund management operations
✅ All BBPS operations
✅ All contact operations
✅ All bank account operations
✅ All transaction operations
✅ All passbook operations
✅ All report operations
✅ All admin panel operations

**No endpoints are missing - this collection is complete!**
