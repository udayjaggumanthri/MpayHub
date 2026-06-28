import React, { useState } from 'react';
import { bankAccountsAPI } from '../../services/api';
import { validateAccountNumber, validateIFSC, validatePhone } from '../../utils/validators';
import { FaCircleCheck } from 'react-icons/fa6';

const AddBankAccount = ({ onCancel, onSuccess }) => {
  const [formData, setFormData] = useState({
    accountNumber: '',
    ifsc: '',
    mobileNumber: '',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [validationData, setValidationData] = useState(null);
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);

  const validatedBeneficiary = validationData?.beneficiary_name || null;
  const resolvedBankName =
    validationData?.bank_name ||
    validationData?.verification_details?.bank_name ||
    validationData?.verification_details?.ifsc_details?.bank ||
    '';

  const handleInputChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
    if (errors[field]) {
      setErrors({ ...errors, [field]: '' });
    }
    if (validationData) {
      setValidationData(null);
    }
  };

  const handleValidate = async () => {
    const accountValidation = validateAccountNumber(formData.accountNumber);
    if (!accountValidation.valid) {
      setErrors({ accountNumber: accountValidation.message });
      return;
    }

    const ifscValidation = validateIFSC(formData.ifsc);
    if (!ifscValidation.valid) {
      setErrors({ ifsc: ifscValidation.message });
      return;
    }

    const phoneValidation = validatePhone(formData.mobileNumber);
    if (!phoneValidation.valid) {
      setErrors({ mobileNumber: phoneValidation.message });
      return;
    }

    setLoading(true);
    setErrors({});

    try {
      const result = await bankAccountsAPI.validateBankAccount(
        formData.accountNumber,
        formData.ifsc.toUpperCase(),
        formData.mobileNumber
      );
      if (result.success && result.data?.beneficiary_name) {
        setValidationData(result.data);
        setShowConfirmModal(true);
      } else {
        const errorMsg =
          result.errors?.join(', ') || result.message || 'Validation failed. Please check the details.';
        setErrors({ accountNumber: errorMsg });
      }
    } catch (error) {
      console.error('Error validating bank account:', error);
      setErrors({ accountNumber: 'Validation failed. Please check the details.' });
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmSave = async () => {
    if (validationData?.bank_account) {
      setShowConfirmModal(false);
      setShowSuccessNotification(true);
      setTimeout(() => {
        setShowSuccessNotification(false);
        if (onSuccess) {
          onSuccess(validationData.bank_account);
        }
        if (onCancel) {
          onCancel();
        }
      }, 1500);
      return;
    }

    setLoading(true);
    try {
      const accountData = {
        account_number: formData.accountNumber,
        ifsc: (validationData?.ifsc || formData.ifsc).toUpperCase(),
        bank_name: resolvedBankName || 'UNKNOWN',
        account_holder_name: validatedBeneficiary,
        beneficiary_name: validatedBeneficiary,
        mobile_number: formData.mobileNumber,
        validation_token: validationData?.validation_token,
      };

      const result = await bankAccountsAPI.createBankAccount(accountData);

      if (result.success) {
        setShowConfirmModal(false);
        setShowSuccessNotification(true);
        setTimeout(() => {
          setShowSuccessNotification(false);
          if (onSuccess) {
            onSuccess(result.data?.bank_account || result.data);
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

  const canValidate =
    formData.accountNumber &&
    formData.ifsc.length === 11 &&
    formData.mobileNumber.length === 10;

  return (
    <>
      {showSuccessNotification && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4 shadow-lg flex items-center space-x-3 min-w-[300px]">
            <FaCircleCheck className="text-green-600 flex-shrink-0" size={24} />
            <div>
              <p className="font-semibold text-green-800">Bank account verified successfully!</p>
              <p className="text-sm text-green-700 mt-1">Bank account saved to your profile</p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-2xl mx-auto bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Add Bank Account</h2>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Mobile Number <span className="text-red-500">*</span>
            </label>
            <input
              type="tel"
              value={formData.mobileNumber}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                handleInputChange('mobileNumber', value);
              }}
              placeholder="Enter 10-digit mobile number"
              maxLength={10}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {errors.mobileNumber && (
              <p className="mt-1 text-sm text-red-600">{errors.mobileNumber}</p>
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
                const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 11);
                handleInputChange('ifsc', value);
              }}
              placeholder="Enter IFSC code (e.g., SBIN0018704)"
              maxLength={11}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent uppercase"
            />
            {errors.ifsc && <p className="mt-1 text-sm text-red-600">{errors.ifsc}</p>}
            <p className="mt-1 text-xs text-gray-500">
              Bank name and beneficiary details are fetched automatically after validation.
            </p>
          </div>

          {validatedBeneficiary && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Beneficiary Name</label>
              <input
                type="text"
                value={validatedBeneficiary}
                disabled
                className="w-full px-4 py-3 border border-green-500 bg-green-50 text-gray-900 font-semibold rounded-lg"
              />
              <p className="mt-1 text-sm text-green-600 flex items-center space-x-1">
                <FaCircleCheck size={14} />
                <span>Beneficiary name fetched from bank</span>
              </p>
            </div>
          )}

          <div className="flex space-x-3">
            <button
              onClick={onCancel}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleValidate}
              disabled={loading || !canValidate}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Validating...' : 'Validate Account'}
            </button>
          </div>
          <p className="text-xs text-gray-500 text-center">
            ₹3 verification fee (deducted only on successful validation)
          </p>
        </div>

        {showConfirmModal && validatedBeneficiary && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
            <div className="bg-white rounded-2xl shadow-2xl max-w-md w-full p-6">
              <h3 className="text-xl font-bold text-gray-900 mb-4">Confirm Beneficiary</h3>
              <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <p className="text-sm text-gray-600 mb-2">Beneficiary Name:</p>
                <p className="text-xl font-bold text-gray-900">{validatedBeneficiary}</p>
                <p className="text-sm text-gray-600 mt-2">Mobile: {formData.mobileNumber}</p>
                <p className="text-sm text-gray-600 mt-2">Account: {formData.accountNumber}</p>
                <p className="text-sm text-gray-600">
                  IFSC: {(validationData?.ifsc || formData.ifsc).toUpperCase()}
                </p>
                {resolvedBankName && (
                  <p className="text-sm text-gray-600">Bank: {resolvedBankName}</p>
                )}
              </div>
              <div className="flex space-x-3">
                <button
                  onClick={() => {
                    setShowConfirmModal(false);
                    setValidationData(null);
                  }}
                  className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmSave}
                  disabled={loading}
                  className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {loading ? 'Saving...' : 'Save Account'}
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
