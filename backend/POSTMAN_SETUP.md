# Postman Collection Setup Guide

## Import Instructions

1. **Import Collection:**
   - Open Postman
   - Click "Import" button
   - Select `postman_collection.json` file
   - Collection will be imported with all API endpoints

2. **Import Environment:**
   - Click "Import" button again
   - Select `postman_environment.json` file
   - Select the imported environment from the dropdown

3. **Set Base URL:**
   - The default base URL is `http://localhost:8000`
   - Update it in the environment if your server runs on a different port

## Quick Start Testing

### Step 1: Login
1. Go to **Authentication > Login**
2. Use the default credentials:
   - Phone: `9876543210`
   - Password: `admin123`
3. Click "Send"
4. The access token will be automatically saved to the environment

### Step 2: Test Other Endpoints
- All other endpoints will automatically use the saved access token
- The token is set in the "Authorization" header as `Bearer {{access_token}}`

## Test Credentials

### Admin User
- Phone: `9876543210`
- Password: `admin123`
- MPIN: `123456`
- Role: Admin

### Master Distributor
- Phone: `9876543211`
- Password: `md123`
- MPIN: `111111`
- Role: Master Distributor

### Distributor
- Phone: `9876543212`
- Password: `d123`
- MPIN: `222222`
- Role: Distributor

### Retailer
- Phone: `9876543213`
- Password: `r123`
- MPIN: `333333`
- Role: Retailer

## Collection Structure

### Authentication
- Login (auto-saves tokens)
- Verify MPIN
- Send OTP
- Verify OTP
- Reset Password
- Refresh Token
- Logout
- Get Current User

### Users
- List Users
- Create User
- Get User Details
- Verify PAN
- Send Aadhaar OTP
- Verify Aadhaar OTP
- Get Subordinates

### Wallets
- Get All Wallets
- Get Main Wallet
- Get Commission Wallet
- Get BBPS Wallet
- Get Wallet History

### Fund Management
- Get Available Gateways
- Load Money
- List Load Money Transactions
- Payout
- List Payout Transactions

### BBPS
- Get Bill Categories
- Get Billers by Category
- Fetch Bill
- Pay Bill
- List Bill Payments
- Get Bill Payment Details

### Contacts
- List Contacts
- Create Contact
- Get Contact
- Update Contact
- Delete Contact
- Search Contact by Phone

### Bank Accounts
- List Bank Accounts
- Validate Bank Account
- Add Bank Account
- Delete Bank Account

### Transactions
- List Transactions
- Get Transaction Details

### Passbook
- Get Passbook Entries

### Reports
- Pay In Report
- Pay Out Report
- BBPS Report
- Commission Report

### Admin Panel
- Announcements (List, Create, Update)
- Payment Gateways (List, Create, Update, Toggle Status)
- Payout Gateways (List, Create, Toggle Status)

## Environment Variables

The collection uses the following environment variables:

- `base_url` - API base URL (default: http://localhost:8000)
- `access_token` - JWT access token (auto-set after login)
- `refresh_token` - JWT refresh token (auto-set after login)
- `user_id` - Current user ID (auto-set after login)

## Tips

1. **Auto Token Refresh:** The Login request automatically saves tokens to the environment
2. **Update Variables:** After creating resources, update `user_id` or other IDs in the environment
3. **Test Flow:** Follow the order: Login → Get Wallets → Create Contact → Add Bank Account → Load Money → Payout/Bill Payment
4. **Error Handling:** Check the response format - all responses follow the standardized format with `success`, `data`, `message`, and `errors` fields

## Common Request Bodies

### Create User
```json
{
    "first_name": "John",
    "last_name": "Doe",
    "phone": "9876543214",
    "email": "john.doe@example.com",
    "role": "Retailer",
    "password": "password123",
    "mpin": "123456"
}
```

### Load Money
```json
{
    "amount": 10000.00,
    "gateway": "razorpay"
}
```

### Payout
```json
{
    "bank_account_id": 1,
    "amount": 5000.00
}
```

### Pay Bill
```json
{
    "biller": "Federal Bank Credit Card",
    "bill_type": "credit-card",
    "amount": 46082.34,
    "customer_details": {
        "card_last4": "3998",
        "mobile": "9703013997"
    }
}
```

## Troubleshooting

1. **401 Unauthorized:** Make sure you've logged in and the token is set
2. **404 Not Found:** Check if the server is running on the correct port
3. **400 Bad Request:** Verify the request body matches the expected format
4. **403 Forbidden:** Check if your user role has permission for the endpoint
