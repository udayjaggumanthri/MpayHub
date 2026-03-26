import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { usersAPI } from '../../services/api';
import { validatePhone, validateEmail, validatePAN, validateAadhaar, validateMPIN } from '../../utils/validators';
import { canCreateRole } from '../../utils/rolePermissions';
import Card from '../common/Card';
import { FaCircleCheck } from 'react-icons/fa6';

const AddUser = ({ onCancel, onSuccess }) => {
  const { user: currentUser } = useAuth();
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    phone: '',
    alternatePhone: '',
    email: '',
    role: '',
    businessName: '',
    businessAddress: '',
    aadhaar: '',
    aadhaarOTP: '',
    pan: '',
    panVerified: false,
    mpin: '',
    confirmMPIN: '',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);

  // Get available roles based on current user's role
  const availableRoles = React.useMemo(() => {
    if (!currentUser) return [];
    const roles = [];
    if (canCreateRole(currentUser.role, 'Master Distributor')) roles.push('Master Distributor');
    if (canCreateRole(currentUser.role, 'Distributor')) roles.push('Distributor');
    if (canCreateRole(currentUser.role, 'Retailer')) roles.push('Retailer');
    return roles;
  }, [currentUser]);

  const handleInputChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
    if (errors[field]) {
      setErrors({ ...errors, [field]: '' });
    }
  };

  const validateStep1 = () => {
    const newErrors = {};
    
    if (!formData.firstName || formData.firstName.length < 2) {
      newErrors.firstName = 'First Name must be at least 2 characters (as per PAN card)';
    }

    if (!formData.lastName || formData.lastName.length < 1) {
      newErrors.lastName = 'Last Name is required';
    }

    const phoneValidation = validatePhone(formData.phone);
    if (!phoneValidation.valid) newErrors.phone = phoneValidation.message;

    if (formData.alternatePhone && formData.alternatePhone.length > 0) {
      const altPhoneValidation = validatePhone(formData.alternatePhone);
      if (!altPhoneValidation.valid) {
        newErrors.alternatePhone = altPhoneValidation.message;
      }
      if (formData.alternatePhone === formData.phone) {
        newErrors.alternatePhone = 'Alternate phone must be different from primary phone';
      }
    }

    const emailValidation = validateEmail(formData.email);
    if (!emailValidation.valid) newErrors.email = emailValidation.message;

    if (!formData.businessName || formData.businessName.length < 2) {
      newErrors.businessName = 'Business Name is required';
    }

    if (!formData.businessAddress || formData.businessAddress.length < 10) {
      newErrors.businessAddress = 'Business Address must be at least 10 characters';
    }

    if (!formData.role) {
      newErrors.role = 'Please select a role';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const validateStep2 = () => {
    const newErrors = {};
    const aadhaarValidation = validateAadhaar(formData.aadhaar);
    if (!aadhaarValidation.valid) newErrors.aadhaar = aadhaarValidation.message;

    if (!formData.aadhaarOTP || formData.aadhaarOTP.length !== 6) {
      newErrors.aadhaarOTP = 'Please enter 6-digit OTP';
    } else if (formData.aadhaarOTP !== '123456') {
      // Mock OTP validation - in real app, this would verify against Aadhaar system
      newErrors.aadhaarOTP = 'Invalid OTP. Please enter correct OTP (Mock: 123456)';
    }

    const panValidation = validatePAN(formData.pan);
    if (!panValidation.valid) {
      newErrors.pan = panValidation.message;
    } else if (!formData.panVerified) {
      newErrors.pan = 'Please verify PAN';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleVerifyPAN = async () => {
    const panValidation = validatePAN(formData.pan);
    if (!panValidation.valid) {
      setErrors({ ...errors, pan: panValidation.message });
      return;
    }

    setLoading(true);
    try {
      // Mock verification for onboarding flow:
      // Accept any PAN that matches valid format.
      // Real integration should verify against PAN service API.
      await new Promise((resolve) => setTimeout(resolve, 2000));

      setFormData({ ...formData, panVerified: true });
      setErrors({ ...errors, pan: '' });
      alert('PAN verified successfully! (Mock mode)');
    } catch (error) {
      setErrors({ ...errors, pan: 'Error verifying PAN. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  const validateStep3 = () => {
    const newErrors = {};
    const mpinValidation = validateMPIN(formData.mpin);
    if (!mpinValidation.valid) {
      newErrors.mpin = mpinValidation.message;
    }

    if (formData.mpin !== formData.confirmMPIN) {
      newErrors.confirmMPIN = 'MPINs do not match';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleStep1Next = () => {
    if (validateStep1()) {
      setStep(2);
    }
  };

  const handleStep2Next = () => {
    if (validateStep2()) {
      setStep(3);
    }
  };

  const handleStep2VerifyOTP = async () => {
    if (!formData.aadhaar || formData.aadhaar.length !== 12) {
      setErrors({ ...errors, aadhaar: 'Please enter valid 12-digit Aadhaar number' });
      return;
    }

    setLoading(true);
    try {
      // Note: Aadhaar OTP sending requires userId, so we'll do a mock for now
      // In production, this would be done after user creation
      await new Promise((resolve) => setTimeout(resolve, 2000));
      alert(`OTP sent to registered mobile number linked with Aadhaar.\n\nMock OTP: 123456`);
    } catch (error) {
      setErrors({ ...errors, aadhaar: 'Error sending OTP. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!validateStep3()) return;

    setLoading(true);
    try {
      // Prepare user data for API (using camelCase as API accepts both)
      const userData = {
        firstName: formData.firstName,
        lastName: formData.lastName,
        phone: formData.phone,
        email: formData.email,
        role: formData.role,
        password: 'default123', // Default password - user should change on first login
        mpin: formData.mpin,
        alternatePhone: formData.alternatePhone || '',
        businessName: formData.businessName,
        businessAddress: formData.businessAddress,
        pan: formData.pan ? formData.pan.toUpperCase() : '',
        aadhaar: formData.aadhaar || '',
      };

      // Create user via API
      const result = await usersAPI.createUser(userData);

      if (result.success && result.data?.user) {
        const newUser = result.data.user;
        
        // Show success notification with all details
        const successMessage = `User created successfully!

User ID: ${newUser.user_id || 'N/A'}
Name: ${newUser.first_name || ''} ${newUser.last_name || ''}
Role: ${newUser.role}
Business: ${formData.businessName}
Email: ${newUser.email}
Phone: ${newUser.phone}

Default Password: default123
Please share these credentials with the user securely.`;
        
        alert(successMessage);
        if (onSuccess) {
          onSuccess(newUser);
        }
        if (onCancel) {
          onCancel();
        }
      } else {
        // Handle API errors
        let errorMessage = result.message || 'Error creating user. Please try again.';

        if (Array.isArray(result.errors) && result.errors.length > 0) {
          errorMessage = result.errors.join(', ');
        } else if (result.errors && typeof result.errors === 'object') {
          // DRF serializer errors usually come as an object: { field: ["msg"] }
          const flattened = Object.entries(result.errors)
            .flatMap(([field, messages]) => {
              if (Array.isArray(messages)) {
                return messages.map((msg) => `${field}: ${msg}`);
              }
              return [`${field}: ${messages}`];
            });
          if (flattened.length > 0) {
            errorMessage = flattened.join(', ');
          }
        } else if (typeof result.errors === 'string' && result.errors.trim()) {
          errorMessage = result.errors;
        }

        alert(errorMessage);
        setErrors({ submit: errorMessage });
      }
    } catch (error) {
      console.error('Error creating user:', error);
      alert('Error creating user. Please try again.');
      setErrors({ submit: 'An unexpected error occurred. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Card
        title="Add New User"
        subtitle="Onboard a new user to the distribution network"
        padding="lg"
      >

      {/* Progress Steps */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {[1, 2, 3].map((s) => (
            <React.Fragment key={s}>
              <div className="flex flex-col items-center flex-1">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                    step >= s
                      ? 'bg-blue-600 text-white'
                      : 'bg-gray-200 text-gray-600'
                  }`}
                >
                  {s}
                </div>
                <p className="mt-2 text-xs text-gray-600">
                  {s === 1 ? 'Basic Details' : s === 2 ? 'KYC Verification' : 'MPIN Setup'}
                </p>
              </div>
              {s < 3 && (
                <div
                  className={`flex-1 h-1 mx-2 ${step > s ? 'bg-blue-600' : 'bg-gray-200'}`}
                ></div>
              )}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Step 1: Basic Details */}
      {step === 1 && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                First Name (as per PAN) <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.firstName}
                onChange={(e) => handleInputChange('firstName', e.target.value)}
                placeholder="Enter first name as per PAN card"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              {errors.firstName && <p className="mt-1 text-sm text-red-600">{errors.firstName}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Last Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.lastName}
                onChange={(e) => handleInputChange('lastName', e.target.value)}
                placeholder="Enter last name"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              {errors.lastName && <p className="mt-1 text-sm text-red-600">{errors.lastName}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Primary Mobile Number <span className="text-red-500">*</span>
              </label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  handleInputChange('phone', value);
                }}
                placeholder="Enter 10-digit phone number"
                maxLength={10}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              {errors.phone && <p className="mt-1 text-sm text-red-600">{errors.phone}</p>}
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Alternate Mobile Number
              </label>
              <input
                type="tel"
                value={formData.alternatePhone}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  handleInputChange('alternatePhone', value);
                }}
                placeholder="Enter alternate phone (optional)"
                maxLength={10}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              {errors.alternatePhone && <p className="mt-1 text-sm text-red-600">{errors.alternatePhone}</p>}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email Address <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => handleInputChange('email', e.target.value)}
              placeholder="Enter email address"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Business Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.businessName}
              onChange={(e) => handleInputChange('businessName', e.target.value)}
              placeholder="Enter business/company name"
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {errors.businessName && <p className="mt-1 text-sm text-red-600">{errors.businessName}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Business Address <span className="text-red-500">*</span>
            </label>
            <textarea
              value={formData.businessAddress}
              onChange={(e) => handleInputChange('businessAddress', e.target.value)}
              placeholder="Enter complete business address"
              rows={3}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
            {errors.businessAddress && <p className="mt-1 text-sm text-red-600">{errors.businessAddress}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Role <span className="text-red-500">*</span>
            </label>
            <select
              value={formData.role}
              onChange={(e) => handleInputChange('role', e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            >
              <option value="">Select Role</option>
              {availableRoles.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
            {errors.role && <p className="mt-1 text-sm text-red-600">{errors.role}</p>}
          </div>

          <div className="flex space-x-3">
            <button
              onClick={onCancel}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleStep1Next}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Step 2: KYC Verification */}
      {step === 2 && (
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Aadhaar Number <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.aadhaar}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 12);
                handleInputChange('aadhaar', value);
              }}
              placeholder="Enter 12-digit Aadhaar number"
              maxLength={12}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            {errors.aadhaar && <p className="mt-1 text-sm text-red-600">{errors.aadhaar}</p>}
            <button
              onClick={handleStep2VerifyOTP}
              disabled={loading || formData.aadhaar.length !== 12}
              className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors text-sm"
            >
              {loading ? 'Sending OTP...' : 'Send Aadhaar OTP'}
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Aadhaar OTP <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.aadhaarOTP}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                handleInputChange('aadhaarOTP', value);
              }}
              placeholder="Enter 6-digit OTP"
              maxLength={6}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center text-2xl font-bold tracking-widest"
            />
            {errors.aadhaarOTP && <p className="mt-1 text-sm text-red-600">{errors.aadhaarOTP}</p>}
            <p className="mt-1 text-sm text-gray-500">Mock OTP: 123456</p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              PAN Number <span className="text-red-500">*</span>
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                value={formData.pan}
                onChange={(e) => {
                  const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 10);
                  handleInputChange('pan', value);
                  if (formData.panVerified) {
                    setFormData({ ...formData, pan: value, panVerified: false });
                  }
                }}
                placeholder="Enter PAN (e.g., ABCDE1234F)"
                maxLength={10}
                className={`flex-1 px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent uppercase ${
                  formData.panVerified ? 'border-green-500 bg-green-50' : 'border-gray-300'
                }`}
              />
              <button
                type="button"
                onClick={handleVerifyPAN}
                disabled={loading || !formData.pan || formData.pan.length !== 10 || formData.panVerified}
                className="px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors whitespace-nowrap"
              >
                {loading ? 'Verifying...' : formData.panVerified ? 'Verified ✓' : 'Verify PAN'}
              </button>
            </div>
            {errors.pan && <p className="mt-1 text-sm text-red-600">{errors.pan}</p>}
            {formData.panVerified && (
              <p className="mt-1 text-sm text-green-600 flex items-center space-x-1">
                <FaCircleCheck size={16} />
                <span>PAN verified successfully</span>
              </p>
            )}
            <p className="mt-1 text-xs text-gray-500">
              PAN will be verified against official database. Name must match as per PAN card.
            </p>
          </div>

          <div className="flex space-x-3">
            <button
              onClick={() => setStep(1)}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Back
            </button>
            <button
              onClick={handleStep2Next}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}

      {/* Step 3: MPIN Setup */}
      {step === 3 && (
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Enter 6-digit MPIN <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              value={formData.mpin}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                handleInputChange('mpin', value);
              }}
              placeholder="Enter 6-digit MPIN"
              maxLength={6}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center text-2xl font-bold tracking-widest"
            />
            {errors.mpin && <p className="mt-1 text-sm text-red-600">{errors.mpin}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Confirm MPIN <span className="text-red-500">*</span>
            </label>
            <input
              type="password"
              value={formData.confirmMPIN}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                handleInputChange('confirmMPIN', value);
              }}
              placeholder="Re-enter 6-digit MPIN"
              maxLength={6}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center text-2xl font-bold tracking-widest"
            />
            {errors.confirmMPIN && <p className="mt-1 text-sm text-red-600">{errors.confirmMPIN}</p>}
          </div>

          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-gray-700 mb-2">
              User ID will be automatically generated by the system based on the selected role.
            </p>
            <p className="text-xs text-gray-600">
              Default password will be set to: <span className="font-semibold">default123</span>
            </p>
          </div>

          <div className="flex space-x-3">
            <button
              onClick={() => setStep(2)}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Back
            </button>
            <button
              onClick={handleSubmit}
              disabled={loading}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {loading ? 'Creating User...' : 'Create User'}
            </button>
          </div>
        </div>
      )}
      </Card>
    </div>
  );
};

export default AddUser;
