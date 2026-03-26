import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { bankAccountsAPI } from '../../services/api';
import { validateAccountNumber, validateIFSC } from '../../utils/validators';
import { formatAccountNumber } from '../../utils/formatters';
import { FaCircleCheck } from 'react-icons/fa6';

const AddBankAccount = ({ onCancel, onSuccess }) => {
  const { user } = useAuth();
  const [formData, setFormData] = useState({
    bankName: '',
    accountNumber: '',
    ifsc: '',
    accountHolderName: '',
  });

  // Common bank names for dropdown
  const bankNames = [
    'HDFC BANK',
    'ICICI BANK',
    'STATE BANK OF INDIA',
    'AXIS BANK',
    'KOTAK MAHINDRA BANK',
    'UNION BANK OF INDIA',
    'PUNJAB NATIONAL BANK',
    'BANK OF BARODA',
    'CANARA BANK',
    'INDIAN BANK',
  ];
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [validatedBeneficiary, setValidatedBeneficiary] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);

  const handleInputChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
    if (errors[field]) {
      setErrors({ ...errors, [field]: '' });
    }
    if (validatedBeneficiary) {
      setValidatedBeneficiary(null);
    }
  };

  const handleValidate = async () => {
    // Validate inputs
    if (!formData.bankName) {
      setErrors({ ...errors, bankName: 'Please select a bank name' });
      return;
    }

    const accountValidation = validateAccountNumber(formData.accountNumber);
    if (!accountValidation.valid) {
      setErrors({ ...errors, accountNumber: accountValidation.message });
      return;
    }

    const ifscValidation = validateIFSC(formData.ifsc);
    if (!ifscValidation.valid) {
      setErrors({ ...errors, ifsc: ifscValidation.message });
      return;
    }

    setLoading(true);
    setErrors({});

    try {
      // Validate bank account via API
      const result = await bankAccountsAPI.validateBankAccount(formData.accountNumber, formData.ifsc);
      if (result.success && result.data?.beneficiary_name) {
        setValidatedBeneficiary(result.data.beneficiary_name);
        setShowConfirmModal(true);
      } else {
        const errorMsg = result.errors?.join(', ') || result.message || 'Validation failed. Please check the details.';
        setErrors({ ...errors, accountNumber: errorMsg });
      }
    } catch (error) {
      console.error('Error validating bank account:', error);
      setErrors({ ...errors, accountNumber: 'Validation failed. Please check the details.' });
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmSave = async () => {
    setLoading(true);
    try {
      // Create bank account via API
      const accountData = {
        account_number: formData.accountNumber,
        ifsc: formData.ifsc.toUpperCase(),
        bank_name: formData.bankName,
        account_holder_name: validatedBeneficiary || formData.accountHolderName,
        beneficiary_name: validatedBeneficiary || formData.accountHolderName,
      };

      const result = await bankAccountsAPI.createBankAccount(accountData);
      
      if (result.success) {
        setShowConfirmModal(false);
        setShowSuccessNotification(true);
        
        // Hide success notification after 3 seconds
        setTimeout(() => {
          setShowSuccessNotification(false);
          if (onSuccess) {
            onSuccess(result.data?.bank_account);
          }
          if (onCancel) {
            onCancel();
          }
        }, 3000);
      } else {
        const errorMsg = result.errors?.join(', ') || result.message || 'Failed to create bank account';
        alert(errorMsg);
      }
    } catch (error) {
      console.error('Error creating bank account:', error);
      alert('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Success Notification */}
      {showSuccessNotification && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4 shadow-lg flex items-center space-x-3 min-w-[300px]">
            <FaCircleCheck className="text-green-600 flex-shrink-0" size={24} />
            <div>
              <p className="font-semibold text-green-800">Bank account verified successfully!</p>
              <p className="text-sm text-green-700 mt-1">Bank account and fund account created successfully</p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-2xl mx-auto bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Add Bank Account</h2>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Bank Name <span className="text-red-500">*</span>
          </label>
          <select
            value={formData.bankName}
            onChange={(e) => handleInputChange('bankName', e.target.value)}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-gray-900 bg-white"
          >
            <option value="">-- Select Bank --</option>
            {bankNames.map((bank) => (
              <option key={bank} value={bank}>
                {bank}
              </option>
            ))}
          </select>
          {errors.bankName && (
            <p className="mt-1 text-sm text-red-600">{errors.bankName}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Account Number <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={formData.accountNumber}
            onChange={(e) => {
              const value = e.target.value.replace(/\D/g, '');
              handleInputChange('accountNumber', value);
            }}
            placeholder="Enter account number"
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
          {errors.accountNumber && (
            <p className="mt-1 text-sm text-red-600">{errors.accountNumber}</p>
          )}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            IFSC Code <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={formData.ifsc}
            onChange={(e) => {
              const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
              handleInputChange('ifsc', value);
            }}
            placeholder="Enter IFSC code (e.g., UBI00812455)"
            maxLength={11}
            className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent uppercase"
          />
          {errors.ifsc && <p className="mt-1 text-sm text-red-600">{errors.ifsc}</p>}
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Beneficiary Name
          </label>
          <input
            type="text"
            value={validatedBeneficiary || formData.accountHolderName}
            onChange={(e) => handleInputChange('accountHolderName', e.target.value)}
            placeholder="Will be auto-filled after validation"
            disabled={!!validatedBeneficiary}
            className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
              validatedBeneficiary 
                ? 'border-green-500 bg-green-50 text-gray-900 font-semibold' 
                : 'border-gray-300'
            }`}
          />
          {validatedBeneficiary && (
            <p className="mt-1 text-sm text-green-600 flex items-center space-x-1">
              <FaCircleCheck size={14} />
              <span>Beneficiary name fetched from bank</span>
            </p>
          )}
        </div>

        <div className="flex space-x-3">
          <button
            onClick={onCancel}
            className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleValidate}
            disabled={loading || !formData.bankName || !formData.accountNumber || !formData.ifsc}
            className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Validating...' : 'Validate Account'}
          </button>
        </div>
      </div>

      {/* Confirmation Modal */}
      {showConfirmModal && validatedBeneficiary && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-900 mb-4">Confirm Beneficiary</h3>
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <p className="text-sm text-gray-600 mb-2">Beneficiary Name:</p>
              <p className="text-xl font-bold text-gray-900">{validatedBeneficiary}</p>
              <p className="text-sm text-gray-600 mt-2">
                Account: {formatAccountNumber(formData.accountNumber)}
              </p>
              <p className="text-sm text-gray-600">IFSC: {formData.ifsc}</p>
              <p className="text-sm text-gray-600">Bank: {formData.bankName}</p>
            </div>
            <div className="flex space-x-3">
              <button
                onClick={() => {
                  setShowConfirmModal(false);
                  setValidatedBeneficiary(null);
                }}
                className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmSave}
                className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                Save Account
              </button>
            </div>
          </div>
        </div>
      )}
      </div>
    </>
  );
};

export default AddBankAccount;
