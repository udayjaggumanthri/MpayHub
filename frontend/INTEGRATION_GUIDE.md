# Frontend-Backend Integration Guide

## Overview

This guide documents the complete integration of the frontend React application with the Django REST Framework backend APIs.

## ✅ Completed Integrations

### 1. API Service Layer (`src/services/api.js`)
- ✅ Complete API service with all endpoints
- ✅ Automatic token management (access & refresh)
- ✅ Request/Response interceptors
- ✅ Error handling
- ✅ Support for all modules: Auth, Users, Wallets, Fund Management, BBPS, Contacts, Bank Accounts, Transactions, Reports, Admin

### 2. Authentication Context (`src/context/AuthContext.jsx`)
- ✅ Integrated with real backend APIs
- ✅ Token-based authentication
- ✅ Session persistence
- ✅ MPIN verification
- ✅ Auto token refresh

### 3. Wallet Context (`src/context/WalletContext.jsx`)
- ✅ Integrated with wallets API
- ✅ Real-time wallet balance fetching
- ✅ Error handling

### 4. Dashboard Component
- ✅ Updated to use WalletContext
- ✅ Displays real wallet balances

## 🔄 Components That Need Integration

### Priority 1: Critical User Flows

#### Authentication Components
- [x] `src/components/auth/Login.jsx` - ✅ Uses AuthContext (already integrated)
- [x] `src/components/auth/MPINVerification.jsx` - ✅ Uses AuthContext (already integrated)
- [ ] `src/components/auth/ForgotPassword.jsx` - Needs API integration

#### User Management
- [ ] `src/components/userManagement/AddUser.jsx` - Replace mock with `usersAPI.createUser()`
- [ ] `src/components/userManagement/UserList.jsx` - Replace mock with `usersAPI.listUsers()`
- [ ] `src/components/userManagement/UserManagement.jsx` - Update to use real APIs

#### Fund Management
- [ ] `src/components/fundManagement/LoadMoney.jsx` - Use `fundManagementAPI.loadMoney()`
- [ ] `src/components/fundManagement/Payout.jsx` - Use `fundManagementAPI.payout()`
- [ ] `src/components/fundManagement/BeneficiarySelector.jsx` - Use `bankAccountsAPI.listBankAccounts()`

#### BBPS (Bill Payments)
- [ ] `src/components/bbps/BillCategorySelector.jsx` - Use `bbpsAPI.getCategories()`
- [ ] `src/components/bbps/CreditCardBill.jsx` - Use `bbpsAPI.fetchBill()`, `bbpsAPI.payBill()`
- [ ] `src/components/bbps/MyBills.jsx` - Use `bbpsAPI.getBillPayments()`

#### Contacts
- [ ] `src/components/contacts/Contacts.jsx` - Use `contactsAPI.listContacts()`, `contactsAPI.createContact()`, `contactsAPI.updateContact()`, `contactsAPI.deleteContact()`

#### Bank Accounts
- [ ] `src/components/bankManagement/BankAccounts.jsx` - Use `bankAccountsAPI.listBankAccounts()`, `bankAccountsAPI.deleteBankAccount()`
- [ ] `src/components/bankManagement/AddBankAccount.jsx` - Use `bankAccountsAPI.validateBankAccount()`, `bankAccountsAPI.createBankAccount()`

#### Reports & Transactions
- [ ] `src/components/reports/Passbook.jsx` - Use `passbookAPI.getPassbookEntries()`
- [ ] `src/components/reports/TransactionReport.jsx` - Use `transactionsAPI.listTransactions()`
- [ ] `src/components/reports/CommissionReport.jsx` - Use `reportsAPI.getCommissionReport()`
- [ ] `src/components/reports/Reports.jsx` - Update to use real APIs

#### Admin Panel
- [ ] `src/components/admin/AnnouncementManagement.jsx` - Use `adminAPI.listAnnouncements()`, `adminAPI.createAnnouncement()`, etc.
- [ ] `src/components/admin/GatewayManagement.jsx` - Use `adminAPI.listPaymentGateways()`, etc.

## 📋 Integration Checklist for Each Component

For each component that needs integration:

1. **Import API functions**
   ```javascript
   import { usersAPI } from '../../services/api';
   ```

2. **Replace mock data calls**
   - Find all `mockData.js` imports
   - Replace with appropriate API calls
   - Update function signatures to be async

3. **Update state management**
   - Add loading states
   - Add error states
   - Handle API response format: `{ success, data, message, errors }`

4. **Error handling**
   - Display user-friendly error messages
   - Handle network errors
   - Handle validation errors

5. **Loading states**
   - Show loading indicators during API calls
   - Disable forms during submission

6. **Success handling**
   - Show success notifications
   - Refresh data after mutations
   - Navigate appropriately

## 🔧 API Response Format

All backend APIs return:
```json
{
  "success": true/false,
  "data": { ... },
  "message": "Success message",
  "errors": []
}
```

## 🔑 Authentication

- Tokens are automatically managed by the API service
- Access token stored in `localStorage`
- Refresh token stored in `localStorage`
- User data stored in `sessionStorage`
- Token refresh happens automatically on 401 errors

## 📝 Example Integration

### Before (Mock Data):
```javascript
import { getWallets } from '../../services/mockData';

const result = getWallets(user.id);
if (result.success) {
  setWallets(result.wallets);
}
```

### After (Real API):
```javascript
import { walletsAPI } from '../../services/api';

const result = await walletsAPI.getAllWallets();
if (result.success && result.data?.wallets) {
  const walletMap = {};
  result.data.wallets.forEach((wallet) => {
    walletMap[wallet.wallet_type] = parseFloat(wallet.balance) || 0;
  });
  setWallets({
    main: walletMap.main || 0,
    commission: walletMap.commission || 0,
    bbps: walletMap.bbps || 0,
  });
}
```

## 🧪 Testing Checklist

After integration, test:

1. **Authentication Flow**
   - [ ] Login with valid credentials
   - [ ] Login with invalid credentials
   - [ ] MPIN verification
   - [ ] Token refresh
   - [ ] Logout

2. **User Management**
   - [ ] List users
   - [ ] Create user
   - [ ] Update user
   - [ ] Delete user
   - [ ] PAN verification
   - [ ] Aadhaar OTP flow

3. **Wallet Operations**
   - [ ] View wallet balances
   - [ ] Load money
   - [ ] Payout
   - [ ] View wallet history

4. **BBPS**
   - [ ] View categories
   - [ ] View billers
   - [ ] Fetch bill
   - [ ] Pay bill
   - [ ] View payment history

5. **Contacts**
   - [ ] List contacts
   - [ ] Create contact
   - [ ] Update contact
   - [ ] Delete contact
   - [ ] Search contact

6. **Bank Accounts**
   - [ ] List bank accounts
   - [ ] Validate account
   - [ ] Add account
   - [ ] Delete account

7. **Reports**
   - [ ] View passbook
   - [ ] View transaction reports
   - [ ] View commission reports

## 🚀 Environment Configuration

Create `.env` file in frontend directory:
```
REACT_APP_API_BASE_URL=http://localhost:8000/api
```

## 📚 API Documentation

- Swagger UI: http://localhost:8000/api/docs/
- Postman Collection: `backend/postman_collection.json`

## ⚠️ Important Notes

1. **Data Transformation**: Backend returns snake_case, frontend may expect camelCase. Transform as needed.

2. **Error Handling**: Always check `result.success` before accessing `result.data`

3. **Loading States**: Always show loading indicators during API calls

4. **Token Management**: Don't manually manage tokens - the API service handles it

5. **Session Persistence**: User data is stored in sessionStorage, tokens in localStorage

6. **MPIN**: MPIN verification is required after login for sensitive operations

## 🔄 Next Steps

1. Continue integrating remaining components following the checklist
2. Test each integration thoroughly
3. Update error messages to be user-friendly
4. Add proper loading states
5. Test complete user flows end-to-end
