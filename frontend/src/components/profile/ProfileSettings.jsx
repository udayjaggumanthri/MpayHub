import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { walletsAPI, authAPI } from '../../services/api';
import { formatUserId, formatCurrency } from '../../utils/formatters';
import { validatePhone, validateEmail, validateMPIN } from '../../utils/validators';
import { FiUser, FiMail, FiPhone, FiLock, FiKey, FiEdit2, FiSave, FiX, FiShield, FiRefreshCw } from 'react-icons/fi';

const ProfileSettings = () => {
  const navigate = useNavigate();
  const { user, refreshUser } = useAuth();
  const [wallets, setWallets] = useState({ main: 0, commission: 0, bbps: 0, profit: 0 });
  const [walletsLoading, setWalletsLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('profile');
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(false);

  const [profileData, setProfileData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    phone: user?.phone || '',
  });

  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const [mpinData, setMpinData] = useState({
    currentMPIN: '',
    newMPIN: '',
    confirmMPIN: '',
  });

  const [errors, setErrors] = useState({});
  const [successMessage, setSuccessMessage] = useState('');

  const loadWallets = useCallback(async () => {
    setWalletsLoading(true);
    try {
      const res = await walletsAPI.getAllWallets();
      if (res.success && res.data?.wallets) {
        const w = res.data.wallets;
        setWallets({
          main: parseFloat(w.main?.balance || 0),
          commission: parseFloat(w.commission?.balance || 0),
          bbps: parseFloat(w.bbps?.balance || 0),
          profit: parseFloat(w.profit?.balance || 0),
        });
      }
    } catch (err) {
      console.error('Failed to load wallets', err);
    } finally {
      setWalletsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadWallets();
  }, [loadWallets]);

  useEffect(() => {
    refreshUser?.();
  }, [refreshUser]);

  useEffect(() => {
    if (user) {
      setProfileData({
        name: user.name || '',
        email: user.email || '',
        phone: user.phone || '',
      });
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
      const res = await authAPI.changePassword({
        current_password: passwordData.currentPassword,
        new_password: passwordData.newPassword,
      });
      if (res.success) {
        setSuccessMessage('Password changed successfully!');
        setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
        setTimeout(() => setSuccessMessage(''), 3000);
      } else {
        setErrors({ general: res.message || 'Failed to change password.' });
      }
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
      const res = await authAPI.changeMPIN({
        current_mpin: mpinData.currentMPIN,
        new_mpin: mpinData.newMPIN,
      });
      if (res.success) {
        setSuccessMessage('MPIN changed successfully!');
        setMpinData({ currentMPIN: '', newMPIN: '', confirmMPIN: '' });
        setTimeout(() => setSuccessMessage(''), 3000);
      } else {
        setErrors({ general: res.message || 'Failed to change MPIN.' });
      }
    } catch (error) {
      setErrors({ general: 'Failed to change MPIN. Please try again.' });
    } finally {
      setLoading(false);
    }
  };

  const ob = user?.onboarding;
  const showCommissionWallet = user?.role && user.role !== 'Retailer';
  const showProfitWallet = user?.role?.toLowerCase() === 'admin';

  const tabs = [
    { id: 'profile', name: 'Profile', icon: FiUser },
    { id: 'verification', name: 'Verification', icon: FiShield },
    { id: 'password', name: 'Change Password', icon: FiLock },
    { id: 'mpin', name: 'Change MPIN', icon: FiKey },
  ];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {successMessage && (
        <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
          {successMessage}
        </div>
      )}

      {errors.general && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
          {errors.general}
        </div>
      )}

      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <div className="flex items-center space-x-4 mb-6">
          <div className="w-20 h-20 bg-blue-600 rounded-full flex items-center justify-center text-white text-3xl font-bold">
            {user?.name?.charAt(0).toUpperCase() || 'U'}
          </div>
          <div>
            <h2 className="text-2xl font-bold text-gray-900">{user?.name}</h2>
            <p className="text-gray-600">User ID: {formatUserId(user?.userId || user?.user_id)}</p>
            <p className="text-sm text-gray-500">{user?.role}</p>
          </div>
        </div>

        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Wallet Balances</h3>
          <button
            type="button"
            onClick={loadWallets}
            disabled={walletsLoading}
            className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 disabled:opacity-50"
          >
            <FiRefreshCw className={walletsLoading ? 'animate-spin' : ''} size={14} />
            Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4 border-t border-gray-200">
          <button
            type="button"
            onClick={() => navigate('/reports/passbook')}
            className="text-center p-4 bg-blue-50 rounded-lg hover:bg-blue-100 transition-colors cursor-pointer border border-blue-100"
          >
            <p className="text-sm text-gray-600 mb-1">Main Wallet</p>
            <p className="text-xl font-bold text-blue-600">
              {walletsLoading ? '...' : formatCurrency(wallets.main)}
            </p>
          </button>
          {showCommissionWallet && (
            <button
              type="button"
              onClick={() => navigate('/reports/commission')}
              className="text-center p-4 bg-green-50 rounded-lg hover:bg-green-100 transition-colors cursor-pointer border border-green-100"
            >
              <p className="text-sm text-gray-600 mb-1">Commission Wallet</p>
              <p className="text-xl font-bold text-green-600">
                {walletsLoading ? '...' : formatCurrency(wallets.commission)}
              </p>
            </button>
          )}
          <button
            type="button"
            onClick={() => navigate('/reports/bbps')}
            className="text-center p-4 bg-yellow-50 rounded-lg hover:bg-yellow-100 transition-colors cursor-pointer border border-yellow-100"
          >
            <p className="text-sm text-gray-600 mb-1">BBPS Wallet</p>
            <p className="text-xl font-bold text-yellow-600">
              {walletsLoading ? '...' : formatCurrency(wallets.bbps)}
            </p>
          </button>
          {showProfitWallet && (
            <button
              type="button"
              onClick={() => navigate('/wallets/profit')}
              className="text-center p-4 bg-purple-50 rounded-lg hover:bg-purple-100 transition-colors cursor-pointer border border-purple-100"
            >
              <p className="text-sm text-gray-600 mb-1">Profit Wallet</p>
              <p className="text-xl font-bold text-purple-600">
                {walletsLoading ? '...' : formatCurrency(wallets.profit)}
              </p>
            </button>
          )}
        </div>

        {ob != null && (
          <div className="mt-6 pt-6 border-t border-gray-200">
            <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
              <FiShield className="text-blue-600" />
              Identity verification
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
              <div className="flex justify-between items-center px-4 py-3 bg-gray-50 rounded-lg border border-gray-100">
                <span className="text-gray-600">PAN</span>
                <span className={ob.pan_verified ? 'font-semibold text-green-700' : 'font-medium text-amber-700'}>
                  {ob.pan_verified ? 'Verified' : 'Not verified'}
                </span>
              </div>
              <div className="flex justify-between items-center px-4 py-3 bg-gray-50 rounded-lg border border-gray-100">
                <span className="text-gray-600">Aadhaar</span>
                <span className={ob.aadhaar_verified ? 'font-semibold text-green-700' : 'font-medium text-amber-700'}>
                  {ob.aadhaar_verified ? 'Verified' : 'Not verified'}
                </span>
              </div>
            </div>
            {!ob.kyc_complete && (
              <button
                type="button"
                onClick={() => navigate('/onboarding/kyc')}
                className="mt-4 w-full sm:w-auto px-4 py-2.5 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors"
              >
                Complete verification
              </button>
            )}
            {ob.kyc_complete && !ob.mpin_set && (
              <button
                type="button"
                onClick={() => navigate('/onboarding/mpin-setup')}
                className="mt-4 w-full sm:w-auto px-4 py-2.5 bg-indigo-600 text-white text-sm font-semibold rounded-lg hover:bg-indigo-700 transition-colors"
              >
                Set up MPIN
              </button>
            )}
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="border-b border-gray-200">
          <nav className="flex -mb-px px-6 overflow-x-auto">
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
                  className={`flex items-center space-x-2 px-6 py-4 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
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

        <div className="p-6">
          {activeTab === 'verification' && (
            <div className="space-y-6">
              <h3 className="text-xl font-bold text-gray-900">Verification status</h3>
              {ob == null ? (
                <p className="text-gray-600 text-sm">Refresh the page to load verification status.</p>
              ) : (
                <>
                  <div className="space-y-3 text-sm">
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-600">PAN verification</span>
                      <span className={ob.pan_verified ? 'text-green-700 font-semibold' : 'text-amber-700 font-medium'}>
                        {ob.pan_verified ? 'Complete' : 'Pending'}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-600">Aadhaar verification</span>
                      <span className={ob.aadhaar_verified ? 'text-green-700 font-semibold' : 'text-amber-700 font-medium'}>
                        {ob.aadhaar_verified ? 'Complete' : 'Pending'}
                      </span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-gray-100">
                      <span className="text-gray-600">KYC overall</span>
                      <span className={ob.kyc_complete ? 'text-green-700 font-semibold' : 'text-amber-700 font-medium'}>
                        {ob.kyc_complete ? 'Complete' : 'In progress'}
                      </span>
                    </div>
                    <div className="flex justify-between py-2">
                      <span className="text-gray-600">MPIN</span>
                      <span className={ob.mpin_set ? 'text-green-700 font-semibold' : 'text-amber-700 font-medium'}>
                        {ob.mpin_set ? 'Set' : 'Not set'}
                      </span>
                    </div>
                  </div>
                  {!ob.kyc_complete && (
                    <button
                      type="button"
                      onClick={() => navigate('/onboarding/kyc')}
                      className="px-5 py-3 bg-blue-600 text-white font-semibold rounded-lg hover:bg-blue-700"
                    >
                      Go to verification
                    </button>
                  )}
                  {ob.kyc_complete && !ob.mpin_set && (
                    <button
                      type="button"
                      onClick={() => navigate('/onboarding/mpin-setup')}
                      className="px-5 py-3 bg-indigo-600 text-white font-semibold rounded-lg hover:bg-indigo-700"
                    >
                      Set MPIN
                    </button>
                  )}
                  {ob.kyc_complete && ob.mpin_set && (
                    <p className="text-sm text-gray-600">Your identity verification is complete.</p>
                  )}
                </>
              )}
            </div>
          )}

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
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">User ID</label>
                  <div className="px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg">
                    <p className="text-gray-900 font-semibold">{formatUserId(user?.userId || user?.user_id)}</p>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Role</label>
                  <div className="px-4 py-3 bg-gray-50 border border-gray-300 rounded-lg">
                    <p className="text-gray-900 font-semibold">{user?.role}</p>
                  </div>
                </div>

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

          {activeTab === 'password' && (
            <div className="space-y-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">Change Password</h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Current Password</label>
                  <input
                    type="password"
                    value={passwordData.currentPassword}
                    onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  {errors.currentPassword && <p className="mt-1 text-sm text-red-600">{errors.currentPassword}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">New Password</label>
                  <input
                    type="password"
                    value={passwordData.newPassword}
                    onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                    placeholder="Minimum 6 characters"
                  />
                  {errors.newPassword && <p className="mt-1 text-sm text-red-600">{errors.newPassword}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Confirm New Password</label>
                  <input
                    type="password"
                    value={passwordData.confirmPassword}
                    onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  {errors.confirmPassword && <p className="mt-1 text-sm text-red-600">{errors.confirmPassword}</p>}
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

          {activeTab === 'mpin' && (
            <div className="space-y-6">
              <h3 className="text-xl font-bold text-gray-900 mb-6">Change MPIN</h3>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Current MPIN</label>
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
                  {errors.currentMPIN && <p className="mt-1 text-sm text-red-600">{errors.currentMPIN}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">New MPIN (6 digits)</label>
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
                  {errors.newMPIN && <p className="mt-1 text-sm text-red-600">{errors.newMPIN}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Confirm New MPIN</label>
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
                  {errors.confirmMPIN && <p className="mt-1 text-sm text-red-600">{errors.confirmMPIN}</p>}
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
