import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { getWallets } from '../../services/mockData';
import { formatUserId } from '../../utils/formatters';
import { formatCurrency } from '../../utils/formatters';
import { validatePhone, validateEmail, validateMPIN } from '../../utils/validators';
import { FiUser, FiMail, FiPhone, FiLock, FiKey, FiEdit2, FiSave, FiX } from 'react-icons/fi';

const ProfileSettings = () => {
  const { user } = useAuth();
  const [wallets, setWallets] = useState({ main: 0, commission: 0, bbps: 0 });
  const [activeTab, setActiveTab] = useState('profile');
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);

  // Profile form state
  const [profileData, setProfileData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    phone: user?.phone || '',
  });

  // Password change state
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  // MPIN change state
  const [mpinData, setMpinData] = useState({
    currentMPIN: '',
    newMPIN: '',
    confirmMPIN: '',
  });

  const [errors, setErrors] = useState({});
  const [successMessage, setSuccessMessage] = useState('');

  React.useEffect(() => {
    if (user) {
      const result = getWallets(user.id);
      if (result.success) {
        setWallets(result.wallets);
      }
    }
  }, [user]);

  const handleProfileChange = (field, value) => {
    setProfileData({ ...profileData, [field]: value });
    if (errors[field]) {
      setErrors({ ...errors, [field]: '' });
    }
  };

  const handleProfileSave = async () => {
    const newErrors = {};
    
    const emailValidation = validateEmail(profileData.email);
    if (!emailValidation.valid) {
      newErrors.email = emailValidation.message;
    }

    const phoneValidation = validatePhone(profileData.phone);
    if (!phoneValidation.valid) {
      newErrors.phone = phoneValidation.message;
    }

    if (!profileData.name || profileData.name.length < 3) {
      newErrors.name = 'Name must be at least 3 characters';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setSuccessMessage('Profile updated successfully!');
      setIsEditing(false);
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (error) {
      setErrors({ general: 'Failed to update profile. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  const handlePasswordChange = async () => {
    const newErrors = {};

    if (!passwordData.currentPassword) {
      newErrors.currentPassword = 'Current password is required';
    }

    if (!passwordData.newPassword || passwordData.newPassword.length < 6) {
      newErrors.newPassword = 'New password must be at least 6 characters';
    }

    if (passwordData.newPassword !== passwordData.confirmPassword) {
      newErrors.confirmPassword = 'Passwords do not match';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setSuccessMessage('Password changed successfully!');
      setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (error) {
      setErrors({ general: 'Failed to change password. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  const handleMPINChange = async () => {
    const newErrors = {};

    if (!mpinData.currentMPIN) {
      newErrors.currentMPIN = 'Current MPIN is required';
    }

    const mpinValidation = validateMPIN(mpinData.newMPIN);
    if (!mpinValidation.valid) {
      newErrors.newMPIN = mpinValidation.message;
    }

    if (mpinData.newMPIN !== mpinData.confirmMPIN) {
      newErrors.confirmMPIN = 'MPINs do not match';
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setLoading(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      setSuccessMessage('MPIN changed successfully!');
      setMpinData({ currentMPIN: '', newMPIN: '', confirmMPIN: '' });
      setTimeout(() => setSuccessMessage(''), 3000);
    } catch (error) {
      setErrors({ general: 'Failed to change MPIN. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'profile', name: 'Profile', icon: FiUser },
    { id: 'password', name: 'Change Password', icon: FiLock },
    { id: 'mpin', name: 'Change MPIN', icon: FiKey },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Success Message */}
      {successMessage && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
          {successMessage}
        </div>
      )}

      {/* Error Message */}
      {errors.general && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {errors.general}
        </div>
      )}

      {/* Profile Overview Card */}
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <div className="flex items-center space-x-4 mb-6">
          <div className="w-20 h-20 bg-blue-600 rounded-full flex items-center justify-center text-white text-3xl font-bold">
            {user?.name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{user?.name}</h2>
            <p className="text-gray-600">User ID: {formatUserId(user?.userId)}</p>
            <p className="text-sm text-gray-500">{user?.role}</p>
          </div>
        </div>

        {/* Wallet Summary */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-6 border-t border-gray-200">
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">Main Wallet</p>
            <p className="text-xl font-bold text-blue-600">{formatCurrency(wallets.main)}</p>
          </div>
          {user?.role !== 'Retailer' && (
            <div className="text-center p-4 bg-green-50 rounded-lg">
              <p className="text-sm text-gray-600 mb-1">Commission Wallet</p>
              <p className="text-xl font-bold text-green-600">{formatCurrency(wallets.commission)}</p>
            </div>
          )}
          <div className="text-center p-4 bg-yellow-50 rounded-lg">
            <p className="text-sm text-gray-600 mb-1">BBPS Wallet</p>
            <p className="text-xl font-bold text-yellow-600">{formatCurrency(wallets.bbps)}</p>
          </div>
        </div>
      </div>

      {/* Settings Tabs */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        {/* Tab Navigation */}
        <div className="border-b border-gray-200">
          <nav className="flex -mb-px px-6">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    setActiveTab(tab.id);
                    setErrors({});
                    setSuccessMessage('');
                  }}
                  className={`flex items-center space-x-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors ${
                    activeTab === tab.id
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon />
                  <span>{tab.name}</span>
                </button>
              );
            })}
          </nav>
        </div>

        {/* Tab Content */}
        <div className="p-6">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-bold text-gray-900">Profile Information</h3>
                {!isEditing ? (
                  <button
                    onClick={() => setIsEditing(true)}
                    className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    <FiEdit2 />
                    <span>Edit Profile</span>
                  </button>
                ) : (
                  <div className="flex space-x-2">
                    <button
                      onClick={() => {
                        setIsEditing(false);
                        setProfileData({
                          name: user?.name || '',
                          email: user?.email || '',
                          phone: user?.phone || '',
                        });
                        setErrors({});
                      }}
                      className="flex items-center space-x-2 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <FiX />
                      <span>Cancel</span>
                    </button>
                    <button
                      onClick={handleProfileSave}
                      disabled={loading}
                      className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
                    >
                      <FiSave />
                      <span>{loading ? 'Saving...' : 'Save Changes'}</span>
                    </button>
                  </div>
                )}
              </div>

              <div className="space-y-4">
                {/* User ID - Read Only */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    User ID
                  </label>
                  <div className="px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg">
                    <p className="text-gray-900 font-semibold">{formatUserId(user?.userId)}</p>
                  </div>
                </div>

                {/* Role - Read Only */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Role
                  </label>
                  <div className="px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg">
                    <p className="text-gray-900 font-semibold">{user?.role}</p>
                  </div>
                </div>

                {/* Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <FiUser className="inline mr-2" />
                    Full Name
                  </label>
                  {isEditing ? (
                    <>
                      <input
                        type="text"
                        value={profileData.name}
                        onChange={(e) => handleProfileChange('name', e.target.value)}
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      {errors.name && <p className="mt-1 text-sm text-red-600">{errors.name}</p>}
                    </>
                  ) : (
                    <div className="px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg">
                      <p className="text-gray-900">{profileData.name}</p>
                    </div>
                  )}
                </div>

                {/* Email */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <FiMail className="inline mr-2" />
                    Email Address
                  </label>
                  {isEditing ? (
                    <>
                      <input
                        type="email"
                        value={profileData.email}
                        onChange={(e) => handleProfileChange('email', e.target.value)}
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      {errors.email && <p className="mt-1 text-sm text-red-600">{errors.email}</p>}
                    </>
                  ) : (
                    <div className="px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg">
                      <p className="text-gray-900">{profileData.email}</p>
                    </div>
                  )}
                </div>

                {/* Phone */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    <FiPhone className="inline mr-2" />
                    Phone Number
                  </label>
                  {isEditing ? (
                    <>
                      <input
                        type="tel"
                        value={profileData.phone}
                        onChange={(e) => {
                          const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                          handleProfileChange('phone', value);
                        }}
                        maxLength={10}
                        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      />
                      {errors.phone && <p className="mt-1 text-sm text-red-600">{errors.phone}</p>}
                    </>
                  ) : (
                    <div className="px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg">
                      <p className="text-gray-900">{profileData.phone}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Change Password Tab */}
          {activeTab === 'password' && (
            <div className="space-y-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">Change Password</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Current Password
                  </label>
                  <input
                    type="password"
                    value={passwordData.currentPassword}
                    onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  {errors.currentPassword && (
                    <p className="mt-1 text-sm text-red-600">{errors.currentPassword}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    New Password
                  </label>
                  <input
                    type="password"
                    value={passwordData.newPassword}
                    onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Minimum 6 characters"
                  />
                  {errors.newPassword && (
                    <p className="mt-1 text-sm text-red-600">{errors.newPassword}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Confirm New Password
                  </label>
                  <input
                    type="password"
                    value={passwordData.confirmPassword}
                    onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  {errors.confirmPassword && (
                    <p className="mt-1 text-sm text-red-600">{errors.confirmPassword}</p>
                  )}
                </div>

                <button
                  onClick={handlePasswordChange}
                  disabled={loading}
                  className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Changing Password...' : 'Change Password'}
                </button>
              </div>
            </div>
          )}

          {/* Change MPIN Tab */}
          {activeTab === 'mpin' && (
            <div className="space-y-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">Change MPIN</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Current MPIN
                  </label>
                  <input
                    type="password"
                    inputMode="numeric"
                    value={mpinData.currentMPIN}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                      setMpinData({ ...mpinData, currentMPIN: value });
                    }}
                    maxLength={6}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center text-2xl font-bold tracking-widest"
                    placeholder="000000"
                  />
                  {errors.currentMPIN && (
                    <p className="mt-1 text-sm text-red-600">{errors.currentMPIN}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    New MPIN (6 digits)
                  </label>
                  <input
                    type="password"
                    inputMode="numeric"
                    value={mpinData.newMPIN}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                      setMpinData({ ...mpinData, newMPIN: value });
                    }}
                    maxLength={6}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center text-2xl font-bold tracking-widest"
                    placeholder="000000"
                  />
                  {errors.newMPIN && (
                    <p className="mt-1 text-sm text-red-600">{errors.newMPIN}</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Confirm New MPIN
                  </label>
                  <input
                    type="password"
                    inputMode="numeric"
                    value={mpinData.confirmMPIN}
                    onChange={(e) => {
                      const value = e.target.value.replace(/\D/g, '').slice(0, 6);
                      setMpinData({ ...mpinData, confirmMPIN: value });
                    }}
                    maxLength={6}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-center text-2xl font-bold tracking-widest"
                    placeholder="000000"
                  />
                  {errors.confirmMPIN && (
                    <p className="mt-1 text-sm text-red-600">{errors.confirmMPIN}</p>
                  )}
                </div>

                <button
                  onClick={handleMPINChange}
                  disabled={loading}
                  className="w-full px-6 py-3 bg-blue-600 text-white rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {loading ? 'Changing MPIN...' : 'Change MPIN'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProfileSettings;
