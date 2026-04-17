import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { usersAPI, fundManagementAPI } from '../../services/api';
import { validatePhone, validateEmail } from '../../utils/validators';
import { canCreateRole } from '../../utils/rolePermissions';
import Card from '../common/Card';
import FeedbackModal from '../common/FeedbackModal';
import { FaBox, FaStar, FaTimes } from 'react-icons/fa';

/**
 * Hierarchy onboarding: basic details only. The new user completes KYC + MPIN after first login.
 */
const AddUser = ({ onCancel, onSuccess, initialRole = '' }) => {
  const { user: currentUser } = useAuth();
  const [formData, setFormData] = useState({
    firstName: '',
    lastName: '',
    phone: '',
    alternatePhone: '',
    email: '',
    role: '',
    businessName: '',
    businessAddress: '',
  });
  const [errors, setErrors] = useState({});
  const [loading, setLoading] = useState(false);
  const [successModal, setSuccessModal] = useState({
    open: false,
    title: '',
    description: '',
    tempPassword: null,
    createdUser: null,
  });

  // Package assignment state
  const [availablePackages, setAvailablePackages] = useState([]);
  const [selectedPackageIds, setSelectedPackageIds] = useState([]);
  const [packagesLoading, setPackagesLoading] = useState(false);

  const loadAssignablePackages = useCallback(async () => {
    setPackagesLoading(true);
    try {
      const result = await fundManagementAPI.getAssignablePackages();
      if (result.success && result.data?.packages) {
        setAvailablePackages(result.data.packages);
      }
    } catch (err) {
      console.error('Failed to load assignable packages:', err);
    } finally {
      setPackagesLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAssignablePackages();
  }, [loadAssignablePackages]);

  const availableRoles = useMemo(() => {
    if (!currentUser) return [];
    const roles = [];
    if (canCreateRole(currentUser.role, 'Super Distributor')) roles.push('Super Distributor');
    if (canCreateRole(currentUser.role, 'Master Distributor')) roles.push('Master Distributor');
    if (canCreateRole(currentUser.role, 'Distributor')) roles.push('Distributor');
    if (canCreateRole(currentUser.role, 'Retailer')) roles.push('Retailer');
    return roles;
  }, [currentUser]);

  useEffect(() => {
    if (!initialRole || !availableRoles.includes(initialRole)) return;
    setFormData((prev) => (prev.role === initialRole ? prev : { ...prev, role: initialRole }));
  }, [initialRole, availableRoles]);

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
    setErrors((prev) => ({ ...prev, [field]: '' }));
  };

  const togglePackage = (packageId) => {
    setSelectedPackageIds((prev) =>
      prev.includes(packageId) ? prev.filter((id) => id !== packageId) : [...prev, packageId]
    );
  };

  const validate = () => {
    const newErrors = {};
    if (!formData.firstName || formData.firstName.length < 2) {
      newErrors.firstName = 'First name must be at least 2 characters';
    }
    if (!formData.lastName || formData.lastName.length < 1) {
      newErrors.lastName = 'Last name is required';
    }
    const phoneValidation = validatePhone(formData.phone);
    if (!phoneValidation.valid) newErrors.phone = phoneValidation.message;
    if (formData.alternatePhone) {
      const alt = validatePhone(formData.alternatePhone);
      if (!alt.valid) newErrors.alternatePhone = alt.message;
      if (formData.alternatePhone === formData.phone) {
        newErrors.alternatePhone = 'Must differ from primary phone';
      }
    }
    const emailValidation = validateEmail(formData.email);
    if (!emailValidation.valid) newErrors.email = emailValidation.message;
    if (!formData.businessName || formData.businessName.length < 2) {
      newErrors.businessName = 'Business name is required';
    }
    if (!formData.businessAddress || formData.businessAddress.length < 10) {
      newErrors.businessAddress = 'Business address must be at least 10 characters';
    }
    if (!formData.role) newErrors.role = 'Please select a role';
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e?.preventDefault?.();
    if (!validate()) return;

    setLoading(true);
    try {
      const userData = {
        firstName: formData.firstName,
        lastName: formData.lastName,
        phone: formData.phone,
        email: formData.email,
        role: formData.role,
        alternatePhone: formData.alternatePhone || '',
        businessName: formData.businessName,
        businessAddress: formData.businessAddress,
        package_ids: selectedPackageIds.length > 0 ? selectedPackageIds : undefined,
      };

      const result = await usersAPI.createUser(userData);

      if (result.success && result.data?.user) {
        const newUser = result.data.user;
        const temp = result.data.temporary_password;
        const pwdLine = temp
          ? `Default login password: ${temp}\n(Share securely. Same default applies when no custom password is set.)`
          : 'Password was set as you provided.';
        const lines = [
          `User ID: ${newUser.user_id ?? '—'}`,
          `Name: ${newUser.first_name ?? ''} ${newUser.last_name ?? ''}`.trim(),
          `Role: ${newUser.role}`,
          `Login: registered mobile number + password`,
          pwdLine,
          '',
          'The user must log in and complete KYC, then set MPIN, before the account is fully active.',
        ];
        setSuccessModal({
          open: true,
          title: 'User created',
          description: lines.join('\n'),
          tempPassword: temp,
          createdUser: newUser,
        });
      } else {
        let errorMessage = result.message || 'Could not create user.';
        if (result.errors && typeof result.errors === 'object') {
          const flat = Object.entries(result.errors).flatMap(([k, v]) =>
            Array.isArray(v) ? v.map((m) => `${k}: ${m}`) : [`${k}: ${v}`]
          );
          if (flat.length) errorMessage = flat.join('\n');
        }
        setErrors({ submit: errorMessage });
      }
    } catch (err) {
      console.error(err);
      setErrors({ submit: 'Unexpected error. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Card
        title="Add New User"
        subtitle="Enter basic details only. The new user will complete KYC and MPIN after first login on their own device."
        padding="lg"
      >
        <form className="space-y-6" onSubmit={handleSubmit}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                First name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.firstName}
                onChange={(e) => handleInputChange('firstName', e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              {errors.firstName && <p className="mt-1 text-sm text-red-600">{errors.firstName}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Last name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={formData.lastName}
                onChange={(e) => handleInputChange('lastName', e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              {errors.lastName && <p className="mt-1 text-sm text-red-600">{errors.lastName}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Mobile <span className="text-red-500">*</span>
              </label>
              <input
                type="tel"
                value={formData.phone}
                onChange={(e) => handleInputChange('phone', e.target.value.replace(/\D/g, '').slice(0, 10))}
                maxLength={10}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              {errors.phone && <p className="mt-1 text-sm text-red-600">{errors.phone}</p>}
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Alternate mobile</label>
              <input
                type="tel"
                value={formData.alternatePhone}
                onChange={(e) =>
                  handleInputChange('alternatePhone', e.target.value.replace(/\D/g, '').slice(0, 10))
                }
                maxLength={10}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
              />
              {errors.alternatePhone && <p className="mt-1 text-sm text-red-600">{errors.alternatePhone}</p>}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email <span className="text-red-500">*</span>
            </label>
            <input
              type="email"
              value={formData.email}
              onChange={(e) => handleInputChange('email', e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
            {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Business name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.businessName}
              onChange={(e) => handleInputChange('businessName', e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
            {errors.businessName && <p className="mt-1 text-sm text-red-600">{errors.businessName}</p>}
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Business address <span className="text-red-500">*</span>
            </label>
            <textarea
              value={formData.businessAddress}
              onChange={(e) => handleInputChange('businessAddress', e.target.value)}
              rows={3}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 resize-none"
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
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select role</option>
              {availableRoles.map((role) => (
                <option key={role} value={role}>
                  {role}
                </option>
              ))}
            </select>
            {errors.role && <p className="mt-1 text-sm text-red-600">{errors.role}</p>}
          </div>

          {/* Package Assignment */}
          <div className="border border-gray-200 rounded-lg p-4 bg-slate-50">
            <div className="flex items-center gap-2 mb-3">
              <FaBox className="text-violet-600" />
              <label className="text-sm font-medium text-gray-700">
                Assign Pay-in Packages (optional)
              </label>
            </div>
            <p className="text-xs text-gray-500 mb-3">
              Select packages this user can access for load money. If none selected, the default package will be assigned automatically.
            </p>
            {packagesLoading ? (
              <p className="text-sm text-gray-500">Loading packages...</p>
            ) : availablePackages.length === 0 ? (
              <p className="text-sm text-gray-500">No packages available to assign.</p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {availablePackages.map((pkg) => {
                  const isSelected = selectedPackageIds.includes(pkg.id);
                  return (
                    <button
                      key={pkg.id}
                      type="button"
                      onClick={() => togglePackage(pkg.id)}
                      className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                        isSelected
                          ? 'bg-violet-600 text-white'
                          : 'bg-white border border-gray-300 text-gray-700 hover:border-violet-400 hover:bg-violet-50'
                      }`}
                    >
                      {pkg.is_default && <FaStar className="text-amber-400" size={12} />}
                      {pkg.display_name}
                      {isSelected && <FaTimes size={12} className="ml-1" />}
                    </button>
                  );
                })}
              </div>
            )}
            {selectedPackageIds.length > 0 && (
              <p className="mt-2 text-xs text-violet-600">
                {selectedPackageIds.length} package{selectedPackageIds.length > 1 ? 's' : ''} selected
              </p>
            )}
          </div>

          {errors.submit && (
            <p className="text-sm text-red-600 whitespace-pre-line">{errors.submit}</p>
          )}

          <div className="flex flex-col sm:flex-row gap-3">
            <button
              type="button"
              onClick={onCancel}
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 px-4 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Creating…' : 'Create user'}
            </button>
          </div>
        </form>
      </Card>

      <FeedbackModal
        open={successModal.open}
        onClose={() => {
          const created = successModal.createdUser;
          setSuccessModal({
            open: false,
            title: '',
            description: '',
            tempPassword: null,
            createdUser: null,
          });
          if (created) onSuccess?.(created);
          onCancel?.();
        }}
        title={successModal.title}
        description={successModal.description}
      />
    </div>
  );
};

export default AddUser;
