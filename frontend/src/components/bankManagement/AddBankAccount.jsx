import React, { useState, useEffect, useCallback } from 'react';
import { bankAccountsAPI, contactsAPI } from '../../services/api';
import { contactsFromListResult } from '../../utils/contactsHelpers';
import { validateAccountNumber, validateIFSC, validatePhone } from '../../utils/validators';
import { FaCircleCheck } from 'react-icons/fa6';

const AddBankAccount = ({ onCancel, onSuccess, presetContact = null }) => {
  const [contacts, setContacts] = useState([]);
  const [contactsLoading, setContactsLoading] = useState(false);
  const [contactId, setContactId] = useState(
    presetContact?.id != null ? String(presetContact.id) : ''
  );
  const [formData, setFormData] = useState({
    accountNumber: '',
    ifsc: '',
    mobileNumber: presetContact?.phone
      ? String(presetContact.phone).replace(/\D/g, '').slice(0, 10)
      : '',
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

  const selectedContact =
    presetContact ||
    contacts.find((c) => String(c.id) === String(contactId)) ||
    null;

  const loadContacts = useCallback(async () => {
    if (presetContact) return;
    setContactsLoading(true);
    try {
      const result = await contactsAPI.listContacts({ page_size: 200 });
      const { contacts: rows } = contactsFromListResult(result);
      setContacts(result.success ? rows : []);
    } catch {
      setContacts([]);
    } finally {
      setContactsLoading(false);
    }
  }, [presetContact]);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  const handleContactChange = (value) => {
    setContactId(value);
    setErrors((prev) => ({ ...prev, contact: '' }));
    const c = contacts.find((row) => String(row.id) === String(value));
    if (c?.phone) {
      setFormData((prev) => ({
        ...prev,
        mobileNumber: String(c.phone).replace(/\D/g, '').slice(0, 10),
      }));
    }
    if (validationData) setValidationData(null);
  };

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
    if (!contactId && !presetContact?.id) {
      setErrors({ contact: 'Select a contact to link this bank account.' });
      return;
    }

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

  const resolveContactId = () =>
    Number(presetContact?.id || contactId || 0) || null;

  const handleConfirmSave = async () => {
    const cid = resolveContactId();
    if (!cid) {
      setErrors({ contact: 'Select a contact to link this bank account.' });
      setShowConfirmModal(false);
      return;
    }

    if (validationData?.bank_account) {
      // Ensure link if validate already created/returned an account
      setLoading(true);
      try {
        const linkResult = await bankAccountsAPI.updateBankAccount(validationData.bank_account.id, {
          contact: cid,
        });
        if (!linkResult.success) {
          const errorMsg =
            linkResult.errors?.join?.(', ') ||
            linkResult.message ||
            'Could not link bank account to contact.';
          alert(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
          return;
        }
      } catch {
        alert('Could not link bank account to contact. Please try again.');
        return;
      } finally {
        setLoading(false);
      }
      setShowConfirmModal(false);
      setShowSuccessNotification(true);
      setTimeout(() => {
        setShowSuccessNotification(false);
        if (onSuccess) onSuccess({ ...validationData.bank_account, contact: cid });
        if (onCancel) onCancel();
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
        contact: cid,
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
        }, 2000);
      } else {
        const errorMsg = result.errors?.join(', ') || result.message || 'Failed to create bank account';
        alert(typeof errorMsg === 'string' ? errorMsg : JSON.stringify(errorMsg));
      }
    } catch (error) {
      console.error('Error creating bank account:', error);
      alert('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const canValidate =
    (presetContact?.id || contactId) &&
    formData.accountNumber &&
    formData.ifsc.length === 11 &&
    formData.mobileNumber.length === 10;

  return (
    <>
      {showSuccessNotification && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-green-50 dark:bg-green-950/40 border-2 border-green-200 dark:border-green-800 rounded-lg p-4 shadow-lg flex items-center space-x-3 min-w-[300px]">
            <FaCircleCheck className="text-green-600 dark:text-green-400 flex-shrink-0" size={24} />
            <div>
              <p className="font-semibold text-green-800 dark:text-green-300">Bank account verified successfully!</p>
              <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                Linked to {selectedContact?.name || 'contact'}
              </p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-2xl mx-auto bg-white dark:bg-slate-900 rounded-xl shadow-sm p-6 border border-gray-200 dark:border-slate-700">
        <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100 mb-2">Add Bank Account</h2>
        <p className="text-sm text-gray-500 dark:text-slate-400 mb-6">
          Every bank account must be linked to a contact (one contact → many accounts).
        </p>

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
              Contact <span className="text-red-500">*</span>
            </label>
            {presetContact ? (
              <div className="rounded-lg border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950/40 px-4 py-3">
                <p className="font-semibold text-gray-900 dark:text-slate-100">{presetContact.name}</p>
                <p className="text-sm text-gray-600 dark:text-slate-400 mt-0.5">
                  {presetContact.phone}
                  {presetContact.email ? ` · ${presetContact.email}` : ''}
                </p>
              </div>
            ) : (
              <select
                value={contactId}
                onChange={(e) => handleContactChange(e.target.value)}
                disabled={contactsLoading}
                className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-slate-900"
              >
                <option value="">
                  {contactsLoading ? 'Loading contacts…' : 'Select contact'}
                </option>
                {contacts.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} · {c.phone}
                  </option>
                ))}
              </select>
            )}
            {errors.contact && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.contact}</p>
            )}
            {!presetContact && contacts.length === 0 && !contactsLoading && (
              <p className="mt-1 text-xs text-amber-700 dark:text-amber-300">
                No contacts yet. Add a contact under User Management → Contacts first.
              </p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
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
              className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {errors.mobileNumber && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.mobileNumber}</p>
            )}
            <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">
              Prefills from the selected contact; used for bank verification.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
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
              className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {errors.accountNumber && (
              <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.accountNumber}</p>
            )}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
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
              className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent uppercase"
            />
            {errors.ifsc && <p className="mt-1 text-sm text-red-600 dark:text-red-400">{errors.ifsc}</p>}
            <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">
              Bank name and beneficiary details are fetched automatically after validation.
            </p>
          </div>

          {validatedBeneficiary && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">Beneficiary Name</label>
              <input
                type="text"
                value={validatedBeneficiary}
                disabled
                className="w-full px-4 py-3 border border-green-500 bg-green-50 dark:bg-green-950/40 text-gray-900 dark:text-slate-100 font-semibold rounded-lg"
              />
              <p className="mt-1 text-sm text-green-600 dark:text-green-400 flex items-center space-x-1">
                <FaCircleCheck size={14} />
                <span>Beneficiary name fetched from bank</span>
              </p>
            </div>
          )}

          <div className="flex space-x-3">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleValidate}
              disabled={loading || !canValidate}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Validating...' : 'Validate Account'}
            </button>
          </div>
          <p className="text-xs text-gray-500 dark:text-slate-400 text-center">
            ₹3 verification fee (deducted only on successful validation)
          </p>
        </div>

        {showConfirmModal && validatedBeneficiary && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
            <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-md w-full p-6">
              <h3 className="text-xl font-bold text-gray-900 dark:text-slate-100 mb-4">Confirm Beneficiary</h3>
              <div className="mb-6 p-4 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg">
                <p className="text-sm text-gray-600 dark:text-slate-400 mb-1">Linked contact:</p>
                <p className="font-semibold text-gray-900 dark:text-slate-100 mb-3">
                  {selectedContact?.name || '—'} ({selectedContact?.phone || '—'})
                </p>
                <p className="text-sm text-gray-600 dark:text-slate-400 mb-2">Beneficiary Name:</p>
                <p className="text-xl font-bold text-gray-900 dark:text-slate-100">{validatedBeneficiary}</p>
                <p className="text-sm text-gray-600 dark:text-slate-400 mt-2">Mobile: {formData.mobileNumber}</p>
                <p className="text-sm text-gray-600 dark:text-slate-400 mt-2">Account: {formData.accountNumber}</p>
                <p className="text-sm text-gray-600 dark:text-slate-400">
                  IFSC: {(validationData?.ifsc || formData.ifsc).toUpperCase()}
                </p>
                {resolvedBankName && (
                  <p className="text-sm text-gray-600 dark:text-slate-400">Bank: {resolvedBankName}</p>
                )}
              </div>
              <div className="flex space-x-3">
                <button
                  type="button"
                  onClick={() => {
                    setShowConfirmModal(false);
                    setValidationData(null);
                  }}
                  className="flex-1 px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg text-gray-700 dark:text-slate-300 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="button"
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
