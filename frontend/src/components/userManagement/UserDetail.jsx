import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { usersAPI, fundManagementAPI } from '../../services/api';
import { formatUserId, formatCurrency } from '../../utils/formatters';
import { validateEmail, validatePhone } from '../../utils/validators';
import { useAuth } from '../../context/AuthContext';
import {
  FaArrowLeft,
  FaUser,
  FaBuilding,
  FaPhone,
  FaEnvelope,
  FaUserCheck,
  FaUserSlash,
  FaCircleCheck,
  FaClock,
  FaBan,
  FaBox,
  FaStar,
  FaTrash,
  FaPlus,
  FaShieldHalved,
  FaIdCard,
  FaCalendar,
  FaPenToSquare,
  FaWallet,
  FaArrowsRotate,
} from 'react-icons/fa6';
import Button from '../common/Button';
import Card from '../common/Card';
import FeedbackModal from '../common/FeedbackModal';
import AccessControlConfirmModal from '../common/AccessControlConfirmModal';
import DeleteUserConfirmModal from './DeleteUserConfirmModal';
import AccessStatusBadges from './AccessStatusBadges';
import AccountAccessSummary from './AccountAccessSummary';
import { formatAdminAccessSuccessMessage } from '../../utils/accessControl';
import HierarchyCard from './HierarchyCard';
import PointOfContactCard from './PointOfContactCard';
import KycVerificationPanel from '../onboarding/KycVerificationPanel';

const ADMIN_ASSIGNABLE_ROLES = [
  'Admin',
  'Super Distributor',
  'Master Distributor',
  'Distributor',
  'Retailer',
];

const accountIsActive = (u) => u && u.is_active !== false;

const roleBadgeClass = (role) => {
  const r = role || '';
  const map = {
    Admin: 'bg-violet-100 text-violet-900 ring-1 ring-violet-200',
    'Super Distributor': 'bg-sky-100 text-sky-900 ring-1 ring-sky-200',
    'Master Distributor': 'bg-cyan-100 text-cyan-900 ring-1 ring-cyan-200',
    Distributor: 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-200',
    Retailer: 'bg-slate-100 text-slate-800 ring-1 ring-slate-200',
  };
  return map[r] || 'bg-slate-100 text-slate-800 ring-1 ring-slate-200';
};

const UserDetail = () => {
  const { userId } = useParams();
  const navigate = useNavigate();
  const { user: currentUser } = useAuth();
  const isAdmin = currentUser?.role === 'Admin';
  const currentUserId = currentUser?.id;

  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [roleDraft, setRoleDraft] = useState('');
  const [roleSaving, setRoleSaving] = useState(false);
  const [roleMessage, setRoleMessage] = useState('');

  const [contactEditing, setContactEditing] = useState(false);
  const [contactDraft, setContactDraft] = useState({ email: '', phone: '' });
  const [contactErrors, setContactErrors] = useState({});
  const [contactSaving, setContactSaving] = useState(false);
  const [contactMessage, setContactMessage] = useState('');

  const [activeStatusSaving, setActiveStatusSaving] = useState(false);
  const [activeStatusMessage, setActiveStatusMessage] = useState('');
  const [accessControlsSaving, setAccessControlsSaving] = useState(false);
  const [accessControlsMessage, setAccessControlsMessage] = useState('');
  const [accessConfirm, setAccessConfirm] = useState(null);
  const [allowPayInWhenDisabled, setAllowPayInWhenDisabled] = useState(false);
  const [selfBlockOpen, setSelfBlockOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [deleteSaving, setDeleteSaving] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  const [userPackages, setUserPackages] = useState({ assigned: [], accessible: [] });
  const [assignablePackages, setAssignablePackages] = useState([]);
  const [packagesLoading, setPackagesLoading] = useState(false);
  const [packageAssigning, setPackageAssigning] = useState(null);
  const [packageMessage, setPackageMessage] = useState('');

  const [userWallets, setUserWallets] = useState({ main: 0, commission: 0, bbps: 0, profit: 0 });
  const [walletsLoading, setWalletsLoading] = useState(false);
  const [walletsError, setWalletsError] = useState('');

  const loadUser = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await usersAPI.getUserDetail(userId);
      const u = res.data?.user ?? res.data;
      if (res.success && u && u.id != null) {
        setUser(u);
        setRoleDraft(u.role || '');
      } else {
        const notFound =
          res.status === 404 ||
          /not found/i.test(res.message || '');
        setError(
          notFound
            ? 'This profile is not available. You can view your team members and their points of contact only.'
            : res.message || 'User not found.',
        );
      }
    } catch (err) {
      setError('Failed to load user details.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  const loadUserWallets = useCallback(async () => {
    if (!userId || !isAdmin) return;
    setWalletsLoading(true);
    setWalletsError('');
    try {
      const res = await usersAPI.getUserWallets(userId);
      if (res.success && res.data?.wallets) {
        const w = res.data.wallets;
        setUserWallets({
          main: parseFloat(w.main?.balance || w.main || 0) || 0,
          commission: parseFloat(w.commission?.balance || w.commission || 0) || 0,
          bbps: parseFloat(w.bbps?.balance || w.bbps || 0) || 0,
          profit: parseFloat(w.profit?.balance || w.profit || 0) || 0,
        });
      } else {
        setWalletsError(res.message || 'Failed to load wallet balances.');
      }
    } catch (err) {
      setWalletsError('Failed to load wallet balances.');
      console.error(err);
    } finally {
      setWalletsLoading(false);
    }
  }, [userId, isAdmin]);

  const loadUserPackages = useCallback(async () => {
    if (!userId || !isAdmin) return;
    setPackagesLoading(true);
    setPackageMessage('');
    try {
      const pkgRes = await fundManagementAPI.getUserPackages(userId);
      if (pkgRes.success && pkgRes.data) {
        setUserPackages({
          assigned: pkgRes.data.assigned_packages || [],
          accessible: pkgRes.data.accessible_packages || [],
        });
      } else {
        setPackageMessage(pkgRes.message || '');
      }
      if (isAdmin) {
        const assignableRes = await fundManagementAPI.getAssignablePackages();
        if (assignableRes.success && assignableRes.data?.packages) {
          setAssignablePackages(assignableRes.data.packages);
        } else {
          setAssignablePackages([]);
        }
      } else {
        setAssignablePackages([]);
      }
    } catch (err) {
      console.error('Failed to load packages:', err);
    } finally {
      setPackagesLoading(false);
    }
  }, [userId, isAdmin]);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    if (user && isAdmin) {
      loadUserPackages();
    }
  }, [user, loadUserPackages, isAdmin]);

  useEffect(() => {
    if (isAdmin && userId) {
      loadUserWallets();
    }
  }, [isAdmin, userId, loadUserWallets]);

  const handleAssignPackage = async (packageId) => {
    setPackageAssigning(packageId);
    setPackageMessage('');
    try {
      const res = await fundManagementAPI.assignPackageToUser(userId, packageId);
      if (res.success) {
        setPackageMessage(res.message || 'Package assigned successfully.');
        await loadUserPackages();
      } else {
        setPackageMessage(res.message || 'Failed to assign package.');
      }
    } catch {
      setPackageMessage('Failed to assign package.');
    } finally {
      setPackageAssigning(null);
    }
  };

  const handleRemovePackage = async (packageId) => {
    setPackageAssigning(packageId);
    setPackageMessage('');
    try {
      const res = await fundManagementAPI.removePackageAssignment(userId, packageId);
      if (res.success) {
        setPackageMessage(res.message || 'Package removed successfully.');
        await loadUserPackages();
      } else {
        setPackageMessage(res.message || 'Failed to remove package.');
      }
    } catch {
      setPackageMessage('Failed to remove package.');
    } finally {
      setPackageAssigning(null);
    }
  };

  const handleSaveRole = async () => {
    if (!user?.id || !roleDraft) return;
    setRoleSaving(true);
    setRoleMessage('');
    try {
      const res = await usersAPI.updateUserRole(user.id, roleDraft);
      const u = res.data?.user ?? res.data;
      if (res.success && u && u.id != null) {
        setUser(u);
        setRoleDraft(u.role || '');
        setRoleMessage('Role updated successfully.');
      } else {
        setRoleMessage(res.message || 'Role update failed.');
      }
    } catch {
      setRoleMessage('Role update failed.');
    } finally {
      setRoleSaving(false);
    }
  };

  const startContactEdit = () => {
    setContactDraft({ email: user.email || '', phone: user.phone || '' });
    setContactErrors({});
    setContactMessage('');
    setContactEditing(true);
  };

  const cancelContactEdit = () => {
    setContactDraft({ email: user.email || '', phone: user.phone || '' });
    setContactErrors({});
    setContactMessage('');
    setContactEditing(false);
  };

  const handleSaveContact = async () => {
    if (!user?.id) return;
    const errors = {};
    const emailValidation = validateEmail(contactDraft.email);
    if (!emailValidation.valid) {
      errors.email = emailValidation.message;
    }
    const phoneValidation = validatePhone(contactDraft.phone);
    if (!phoneValidation.valid) {
      errors.phone = phoneValidation.message;
    }
    if (Object.keys(errors).length > 0) {
      setContactErrors(errors);
      return;
    }
    setContactSaving(true);
    setContactErrors({});
    setContactMessage('');
    try {
      const res = await usersAPI.updateUserContact(user.id, {
        email: contactDraft.email.trim(),
        phone: contactDraft.phone.trim(),
      });
      const u = res.data?.user ?? res.data;
      if (res.success && u && u.id != null) {
        setUser(u);
        setContactDraft({ email: u.email || '', phone: u.phone || '' });
        setContactMessage('Contact details updated successfully.');
        setContactEditing(false);
      } else {
        setContactMessage(res.message || 'Failed to update contact details.');
        if (res.errors && typeof res.errors === 'object') {
          const apiErrors = {};
          Object.entries(res.errors).forEach(([key, val]) => {
            apiErrors[key] = Array.isArray(val) ? val[0] : String(val);
          });
          setContactErrors(apiErrors);
        }
      }
    } catch {
      setContactMessage('Failed to update contact details.');
    } finally {
      setContactSaving(false);
    }
  };

  const performActiveToggle = async (nextActive) => {
    setActiveStatusSaving(true);
    setActiveStatusMessage('');
    try {
      const res = await usersAPI.setUserAccessControls(user.id, {
        is_active: nextActive,
        ...(nextActive
          ? {}
          : { pay_in_allowed_when_disabled: Boolean(allowPayInWhenDisabled) }),
      });
      const u = res.data?.user ?? res.data;
      if (res.success && u && u.id != null) {
        setUser(u);
        setActiveStatusMessage(formatAdminAccessSuccessMessage(res.message));
      } else {
        const msg = res.message || res.errors?.[0] || 'Update failed.';
        setActiveStatusMessage(typeof msg === 'string' ? msg : 'Update failed.');
      }
    } catch {
      setActiveStatusMessage('Update failed. Please try again.');
    } finally {
      setActiveStatusSaving(false);
      setAccessConfirm(null);
      setAllowPayInWhenDisabled(false);
    }
  };

  const applyAccessFlag = async (patch) => {
    if (!user?.id) return;
    setAccessControlsSaving(true);
    setAccessControlsMessage('');
    try {
      const res = await usersAPI.setUserAccessControls(user.id, patch);
      const u = res.data?.user ?? res.data;
      if (res.success && u?.id != null) {
        setUser(u);
        setAccessControlsMessage(formatAdminAccessSuccessMessage(res.message));
      } else {
        setAccessControlsMessage(res.message || res.accessError?.message || 'Update failed.');
      }
    } catch {
      setAccessControlsMessage('Update failed. Please try again.');
    } finally {
      setAccessControlsSaving(false);
      setAccessConfirm(null);
    }
  };

  const requestAccessChange = (actionKey, patch) => {
    if (!isAdmin || !user?.id) return;
    if (String(user.id) === String(currentUserId)) {
      setSelfBlockOpen(true);
      return;
    }
    setAccessConfirm({ actionKey, patch });
  };

  const requestToggleAccountActive = (nextActive) => {
    requestAccessChange(nextActive ? 'enable_account' : 'disable_account', {
      is_active: nextActive,
      ...(nextActive ? {} : { pay_in_allowed_when_disabled: Boolean(allowPayInWhenDisabled) }),
    });
  };

  const handleAccessConfirm = () => {
    if (!accessConfirm) return;
    const { actionKey, patch } = accessConfirm;
    if (actionKey === 'disable_account' || actionKey === 'enable_account') {
      performActiveToggle(Boolean(patch.is_active));
      return;
    }
    applyAccessFlag(patch);
  };

  const requestDeleteUser = () => {
    if (!isAdmin || !user?.id) return;
    if (String(user.id) === String(currentUserId)) {
      setSelfBlockOpen(true);
      return;
    }
    setDeleteError('');
    setDeleteConfirmOpen(true);
  };

  const performDeleteUser = async () => {
    if (!user?.id) return;
    setDeleteSaving(true);
    setDeleteError('');
    try {
      const res = await usersAPI.deleteUser(user.id);
      if (res.success) {
        navigate('/user-management/users', {
          replace: true,
          state: { deleteSuccess: res.message || 'User deleted permanently.' },
        });
      } else {
        setDeleteError(res.message || 'Could not delete this user.');
      }
    } catch {
      setDeleteError('Could not delete this user. Please try again.');
    } finally {
      setDeleteSaving(false);
    }
  };

  const requestRestrictToggle = (checked) => {
    if (!checked) {
      applyAccessFlag({ is_restricted: false });
      return;
    }
    requestAccessChange('restrict_on', { is_restricted: true });
  };

  const requestPaymentsLockToggle = (checked) => {
    if (!checked) {
      applyAccessFlag({ payments_locked: false });
      return;
    }
    requestAccessChange('payments_lock_on', { payments_locked: true });
  };

  if (loading) {
    return (
      <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 via-white to-slate-50/80 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-12 w-12 animate-spin rounded-full border-2 border-indigo-600 border-t-transparent" />
          <p className="text-sm font-medium text-slate-600">Loading user details...</p>
        </div>
      </div>
    );
  }

  if (error || !user) {
    return (
      <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 via-white to-slate-50/80">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <Card className="text-center py-16">
            <FaUser className="mx-auto text-slate-300 mb-4" size={48} />
            <h2 className="text-xl font-bold text-slate-900 mb-2">User Not Found</h2>
            <p className="text-slate-600 mb-6">{error || 'The requested user could not be found.'}</p>
            <Button onClick={() => navigate(-1)} variant="outline" icon={FaArrowLeft} iconPosition="left">
              Go Back
            </Button>
          </Card>
        </div>
      </div>
    );
  }

  const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'N/A';
  const kycStatus = user.kyc?.verification_status || 'pending';
  const kycOk = kycStatus === 'verified';
  const kycRejected = kycStatus === 'rejected';
  const mpinOk = user.mpin_configured === true;
  const isSelf = String(user.id) === String(currentUserId);
  const showCommissionWallet = user.role && user.role !== 'Retailer';
  const showProfitWallet = user.role === 'Admin';

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 via-white to-slate-50/80">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate(-1)}
              className="flex items-center justify-center h-10 w-10 rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition-colors hover:bg-slate-50 hover:text-slate-900"
            >
              <FaArrowLeft size={16} />
            </button>
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-indigo-600">User Profile</p>
              <h1 className="text-2xl font-bold text-slate-900 tracking-tight">{fullName}</h1>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold ${roleBadgeClass(user.role)}`}>
              {user.role}
            </span>
            <AccessStatusBadges user={user} className="justify-end" />
          </div>
        </div>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column - User Info */}
          <div className="lg:col-span-2 space-y-6">
            {/* Identity Card */}
            <Card className="overflow-hidden">
              <div className="bg-gradient-to-br from-indigo-500 to-violet-600 px-6 py-8 text-white">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-indigo-200 text-sm font-medium mb-1">User ID</p>
                    <p className="font-mono text-2xl font-bold tracking-wider">
                      {formatUserId(user.user_id || user.id)}
                    </p>
                  </div>
                  <div className="h-16 w-16 rounded-2xl bg-white/20 backdrop-blur-sm flex items-center justify-center">
                    <FaUser className="text-white/90" size={28} />
                  </div>
                </div>
              </div>
              <div className="p-6">
                {isAdmin && !isSelf && (
                  <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-indigo-100 bg-indigo-50/50 px-4 py-3">
                    <p className="text-sm text-indigo-900">
                      {contactEditing
                        ? 'Updating mobile changes how this user signs in. They will use the new number with their existing password or MPIN.'
                        : 'Administrators can update this user\'s email and mobile number.'}
                    </p>
                    {!contactEditing ? (
                      <Button variant="outline" size="sm" onClick={startContactEdit} icon={FaPenToSquare} iconPosition="left">
                        Edit contact
                      </Button>
                    ) : (
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={cancelContactEdit} disabled={contactSaving}>
                          Cancel
                        </Button>
                        <Button variant="primary" size="sm" onClick={handleSaveContact} disabled={contactSaving}>
                          {contactSaving ? 'Saving...' : 'Save'}
                        </Button>
                      </div>
                    )}
                  </div>
                )}
                {contactMessage && (
                  <p className={`mb-4 text-sm ${contactMessage.includes('success') ? 'text-emerald-700' : 'text-red-600'}`}>
                    {contactMessage}
                  </p>
                )}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div>
                    <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wide mb-2">
                      <FaUser size={12} />
                      Full Name
                    </div>
                    <p className="text-lg font-semibold text-slate-900 capitalize">{fullName}</p>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wide mb-2">
                      <FaEnvelope size={12} />
                      Email
                    </div>
                    {contactEditing && isAdmin && !isSelf ? (
                      <div>
                        <input
                          type="email"
                          value={contactDraft.email}
                          onChange={(e) => {
                            setContactDraft((d) => ({ ...d, email: e.target.value }));
                            setContactErrors((err) => ({ ...err, email: undefined }));
                          }}
                          className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm focus:border-indigo-300 focus:ring-2 focus:ring-indigo-500/20"
                          autoComplete="off"
                        />
                        {contactErrors.email && (
                          <p className="mt-1 text-xs text-red-600">{contactErrors.email}</p>
                        )}
                      </div>
                    ) : (
                      <p className="text-slate-900 break-all">{user.email || 'N/A'}</p>
                    )}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wide mb-2">
                      <FaPhone size={12} />
                      Phone
                    </div>
                    {contactEditing && isAdmin && !isSelf ? (
                      <div>
                        <input
                          type="tel"
                          inputMode="numeric"
                          maxLength={10}
                          value={contactDraft.phone}
                          onChange={(e) => {
                            setContactDraft((d) => ({ ...d, phone: e.target.value.replace(/\D/g, '').slice(0, 10) }));
                            setContactErrors((err) => ({ ...err, phone: undefined }));
                          }}
                          className="w-full rounded-xl border border-slate-200 px-3 py-2 font-mono text-sm tabular-nums focus:border-indigo-300 focus:ring-2 focus:ring-indigo-500/20"
                          autoComplete="off"
                        />
                        {contactErrors.phone && (
                          <p className="mt-1 text-xs text-red-600">{contactErrors.phone}</p>
                        )}
                      </div>
                    ) : (
                      <p className="text-slate-900 font-mono tabular-nums">{user.phone || 'N/A'}</p>
                    )}
                  </div>
                  {user.profile?.alternate_phone && (
                    <div>
                      <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wide mb-2">
                        <FaPhone size={12} />
                        Alternate Phone
                      </div>
                      <p className="text-slate-900 font-mono tabular-nums">{user.profile.alternate_phone}</p>
                    </div>
                  )}
                </div>
              </div>
            </Card>

            {isAdmin && (
              <Card>
                <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                      <FaWallet className="text-emerald-600" size={18} />
                    </div>
                    <h2 className="text-lg font-bold text-slate-900">Wallet Balances</h2>
                  </div>
                  <button
                    type="button"
                    onClick={loadUserWallets}
                    disabled={walletsLoading}
                    className="flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:text-indigo-800 disabled:opacity-50"
                  >
                    <FaArrowsRotate className={walletsLoading ? 'animate-spin' : ''} size={14} />
                    Refresh
                  </button>
                </div>
                <div className="p-6">
                  {walletsError && (
                    <p className="mb-4 text-sm text-red-600">{walletsError}</p>
                  )}
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    <div className="rounded-xl border border-blue-100 bg-blue-50/80 p-4 text-center">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-1">Main Wallet</p>
                      <p className="text-xl font-bold text-blue-700 tabular-nums">
                        {walletsLoading ? '...' : formatCurrency(userWallets.main)}
                      </p>
                    </div>
                    {showCommissionWallet && (
                      <div className="rounded-xl border border-emerald-100 bg-emerald-50/80 p-4 text-center">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-1">Commission Wallet</p>
                        <p className="text-xl font-bold text-emerald-700 tabular-nums">
                          {walletsLoading ? '...' : formatCurrency(userWallets.commission)}
                        </p>
                      </div>
                    )}
                    <div className="rounded-xl border border-amber-100 bg-amber-50/80 p-4 text-center">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-1">BBPS Wallet</p>
                      <p className="text-xl font-bold text-amber-700 tabular-nums">
                        {walletsLoading ? '...' : formatCurrency(userWallets.bbps)}
                      </p>
                    </div>
                    {showProfitWallet && (
                      <div className="rounded-xl border border-violet-100 bg-violet-50/80 p-4 text-center">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-1">Profit Wallet</p>
                        <p className="text-xl font-bold text-violet-700 tabular-nums">
                          {walletsLoading ? '...' : formatCurrency(userWallets.profit)}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            )}

            {/* Business Information */}
            <Card>
              <div className="px-6 py-4 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-amber-100 flex items-center justify-center">
                    <FaBuilding className="text-amber-600" size={18} />
                  </div>
                  <h2 className="text-lg font-bold text-slate-900">Business Information</h2>
                </div>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-1 gap-4">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Business Name</p>
                    <p className="text-slate-900 font-medium">{user.profile?.business_name || 'N/A'}</p>
                  </div>
                  {user.profile?.business_address && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Business Address</p>
                      <p className="text-slate-700">{user.profile.business_address}</p>
                    </div>
                  )}
                </div>
              </div>
            </Card>

            {isAdmin && user.hierarchy_lineage && (
              <HierarchyCard lineage={user.hierarchy_lineage} user={user} />
            )}
            {!isAdmin && user.point_of_contact != null && (
              <PointOfContactCard pointOfContact={user.point_of_contact} />
            )}

            {/* KYC Information */}
            <Card>
              <div className="px-6 py-4 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                    <FaIdCard className="text-emerald-600" size={18} />
                  </div>
                  <h2 id="kyc-compliance-heading" className="text-lg font-bold text-slate-900">KYC & Compliance</h2>
                </div>
              </div>
              <section className="p-6" aria-labelledby="kyc-compliance-heading">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                  <div className="flex items-start gap-3">
                    <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${
                      kycOk ? 'bg-emerald-100' : kycRejected ? 'bg-red-100' : 'bg-amber-100'
                    }`}>
                      {kycOk ? (
                        <FaCircleCheck className="text-emerald-600" size={18} />
                      ) : kycRejected ? (
                        <FaBan className="text-red-600" size={18} />
                      ) : (
                        <FaClock className="text-amber-600" size={18} />
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">KYC Status</p>
                      <p className={`text-lg font-semibold capitalize ${
                        kycOk ? 'text-emerald-700' : kycRejected ? 'text-red-700' : 'text-amber-700'
                      }`}>
                        {kycStatus}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className={`h-10 w-10 rounded-xl flex items-center justify-center ${
                      mpinOk ? 'bg-emerald-100' : 'bg-amber-100'
                    }`}>
                      {mpinOk ? (
                        <FaShieldHalved className="text-emerald-600" size={18} />
                      ) : (
                        <FaClock className="text-amber-600" size={18} />
                      )}
                    </div>
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">MPIN</p>
                      <p className={`text-lg font-semibold ${mpinOk ? 'text-emerald-700' : 'text-amber-700'}`}>
                        {mpinOk ? 'Configured' : 'Not Set'}
                      </p>
                    </div>
                  </div>
                </div>

                {(user.kyc_verification?.pan || user.kyc_verification?.aadhaar) ? (
                  <div className="mt-6 pt-6 border-t border-slate-100">
                    <KycVerificationPanel
                      verification={user.kyc_verification}
                      title={
                        isAdmin && currentUserId !== user.id
                          ? 'Verified identity records'
                          : 'Your verified KYC records'
                      }
                      showTechnicalDetails={isAdmin}
                    />
                    {isAdmin && Array.isArray(user.profile_sync_audits) && user.profile_sync_audits.length > 0 ? (
                      <div className="mt-6">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">
                          Profile sync audit
                        </p>
                        <div className="space-y-2 max-h-48 overflow-y-auto">
                          {user.profile_sync_audits.map((row) => (
                            <div key={row.id} className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
                              <span className="font-semibold capitalize">{row.status}</span>
                              {' · '}
                              <span>{row.source}</span>
                              {' · '}
                              <span>
                                {row.before?.first_name} {row.before?.last_name}
                                {row.before?.date_of_birth ? ` (${row.before.date_of_birth})` : ''}
                              </span>
                              {' → '}
                              <span>
                                {row.after?.first_name || row.verified?.full_name} {row.after?.last_name || ''}
                                {row.after?.date_of_birth ? ` (${row.after.date_of_birth})` : ''}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </div>
                ) : (
                  <div className="mt-6 pt-6 border-t border-slate-100">
                    <p className="text-sm text-slate-600 bg-slate-50 rounded-xl px-4 py-3 border border-slate-200">
                      {kycOk
                        ? 'KYC is marked complete but detailed provider records are not on file.'
                        : 'User has not completed KYC onboarding yet.'}
                    </p>
                  </div>
                )}
              </section>
            </Card>
          </div>

          {/* Right Column - Actions & Packages */}
          <div className="space-y-6">
            {/* Account Actions (Admin only) */}
            {isAdmin && !isSelf && (
              <Card>
                <div className="px-6 py-4 border-b border-slate-100">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-indigo-100 flex items-center justify-center">
                      <FaPenToSquare className="text-indigo-600" size={18} />
                    </div>
                    <h2 className="text-lg font-bold text-slate-900">Account Actions</h2>
                  </div>
                </div>
                <div className="p-6 space-y-6">
                  {/* Role Change */}
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-2">Change Role</p>
                    <div className="flex gap-2">
                      <select
                        value={roleDraft}
                        onChange={(e) => {
                          setRoleDraft(e.target.value);
                          setRoleMessage('');
                        }}
                        className="flex-1 rounded-xl border border-slate-200 px-3 py-2.5 text-sm focus:border-indigo-300 focus:ring-2 focus:ring-indigo-500/20"
                      >
                        {ADMIN_ASSIGNABLE_ROLES.map((r) => (
                          <option key={r} value={r}>{r}</option>
                        ))}
                      </select>
                      <Button
                        onClick={handleSaveRole}
                        disabled={roleSaving || !roleDraft || roleDraft === user.role}
                        variant="primary"
                        size="md"
                      >
                        {roleSaving ? 'Saving...' : 'Apply'}
                      </Button>
                    </div>
                    {roleMessage && (
                      <p className={`mt-2 text-sm ${roleMessage.includes('success') ? 'text-emerald-700' : 'text-red-600'}`}>
                        {roleMessage}
                      </p>
                    )}
                  </div>

                  {/* Account Status */}
                  <div className="pt-4 border-t border-slate-100">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">Account Access</p>
                    <AccessStatusBadges user={user} className="mb-3" />
                    <AccountAccessSummary user={user} />
                    <div className="mt-4 flex gap-2">
                      <Button
                        onClick={() => requestToggleAccountActive(false)}
                        disabled={activeStatusSaving || accessControlsSaving || !accountIsActive(user)}
                        variant="outline"
                        size="md"
                        icon={FaUserSlash}
                        iconPosition="left"
                        className="flex-1 border-amber-200 text-amber-800 hover:bg-amber-50"
                      >
                        Disable
                      </Button>
                      <Button
                        onClick={() => requestToggleAccountActive(true)}
                        disabled={activeStatusSaving || accessControlsSaving || accountIsActive(user)}
                        variant="success"
                        size="md"
                        icon={FaUserCheck}
                        iconPosition="left"
                        className="flex-1"
                      >
                        Enable
                      </Button>
                    </div>
                    {activeStatusMessage && (
                      <p className={`mt-2 text-sm ${
                        activeStatusMessage.includes('success') || activeStatusMessage.includes('enabled') || activeStatusMessage.includes('disabled')
                          ? 'text-emerald-700'
                          : 'text-red-600'
                      }`}>
                        {activeStatusMessage}
                      </p>
                    )}
                  </div>

                  <div className="pt-4 border-t border-slate-100 space-y-3">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">Access restrictions</p>
                    <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        checked={Boolean(user.is_restricted)}
                        disabled={accessControlsSaving || activeStatusSaving}
                        onChange={(e) => requestRestrictToggle(e.target.checked)}
                      />
                      <span>
                        <span className="font-medium text-slate-900">Restrict user</span>
                        <span className="block text-xs text-slate-500 mt-0.5">
                          Read-only portal: reports and profile only; no pay-in or payments.
                        </span>
                      </span>
                    </label>
                    <label className="flex items-start gap-3 rounded-xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm text-slate-700 cursor-pointer">
                      <input
                        type="checkbox"
                        className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                        checked={Boolean(user.payments_locked)}
                        disabled={accessControlsSaving || activeStatusSaving || !accountIsActive(user)}
                        onChange={(e) => requestPaymentsLockToggle(e.target.checked)}
                      />
                      <span>
                        <span className="font-medium text-slate-900">Lock payments</span>
                        <span className="block text-xs text-slate-500 mt-0.5">
                          Blocks BBPS, payout, and transfers; pay-in still allowed unless restricted.
                        </span>
                      </span>
                    </label>
                    {accessControlsMessage && (
                      <p className={`text-sm ${accessControlsMessage.includes('updated') ? 'text-emerald-700' : 'text-red-600'}`}>
                        {accessControlsMessage}
                      </p>
                    )}
                  </div>

                  {!isSelf ? (
                    <div className="pt-4 border-t border-red-100">
                      <p className="text-xs font-semibold uppercase tracking-wide text-red-700 mb-2">Danger zone</p>
                      <p className="text-sm text-slate-600 mb-3">
                        Permanently delete this user and all related account data. This cannot be undone.
                      </p>
                      <Button
                        type="button"
                        variant="danger"
                        size="md"
                        icon={FaTrash}
                        iconPosition="left"
                        onClick={requestDeleteUser}
                        disabled={deleteSaving || activeStatusSaving || accessControlsSaving}
                      >
                        Delete user permanently
                      </Button>
                      {deleteError ? (
                        <p role="alert" className="mt-2 text-sm text-red-600">{deleteError}</p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </Card>
            )}

            {isAdmin && (
            <Card>
              <div className="px-6 py-4 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-violet-100 flex items-center justify-center">
                    <FaBox className="text-violet-600" size={18} />
                  </div>
                  <h2 className="text-lg font-bold text-slate-900">Pay-in Packages</h2>
                </div>
              </div>
              <div className="p-6 space-y-5">
                {packagesLoading ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-600 border-t-transparent" />
                  </div>
                ) : (
                  <>
                    {/* Assigned Packages */}
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">
                        Assigned Packages
                      </p>
                      {userPackages.assigned.length === 0 ? (
                        <p className="text-sm text-slate-500 bg-slate-50 rounded-xl px-4 py-3">
                          No packages explicitly assigned. Using default package (if configured).
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {userPackages.assigned.map((pkg) => (
                            <div
                              key={pkg.id}
                              className="flex items-center justify-between rounded-xl border border-violet-200 bg-violet-50 px-4 py-3"
                            >
                              <div className="flex items-center gap-2">
                                {pkg.is_default && <FaStar className="text-amber-500" size={14} />}
                                <span className="font-medium text-violet-900">{pkg.display_name}</span>
                              </div>
                              {isAdmin ? (
                                <button
                                  onClick={() => handleRemovePackage(pkg.id)}
                                  disabled={packageAssigning === pkg.id}
                                  className="rounded-lg p-2 text-violet-600 hover:bg-violet-100 hover:text-red-600 transition-colors disabled:opacity-50"
                                  title="Remove package"
                                >
                                  <FaTrash size={14} />
                                </button>
                              ) : null}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Effective Access */}
                    <div className="pt-4 border-t border-slate-100">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">
                        Effective Access
                      </p>
                      {userPackages.accessible.length === 0 ? (
                        <p className="text-sm text-slate-500 bg-slate-50 rounded-xl px-4 py-3">
                          No packages accessible.
                        </p>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          {userPackages.accessible.map((pkg) => (
                            <span
                              key={pkg.id}
                              className="inline-flex items-center gap-1.5 rounded-lg bg-slate-100 px-3 py-1.5 text-sm font-medium text-slate-700"
                            >
                              {pkg.is_default && <FaStar className="text-amber-500" size={10} />}
                              {pkg.display_name}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>

                    {/* Assign New Package (Admin only) */}
                    {isAdmin &&
                      assignablePackages.filter((pkg) => !userPackages.assigned.find((ap) => ap.id === pkg.id)).length >
                        0 && (
                      <div className="pt-4 border-t border-slate-100">
                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">
                          Assign Package
                        </p>
                        <div className="space-y-2">
                          {assignablePackages
                            .filter((pkg) => !userPackages.assigned.find((ap) => ap.id === pkg.id))
                            .map((pkg) => (
                              <button
                                key={pkg.id}
                                onClick={() => handleAssignPackage(pkg.id)}
                                disabled={packageAssigning === pkg.id}
                                className="w-full flex items-center justify-between rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-medium text-slate-700 transition-colors hover:border-violet-300 hover:bg-violet-50 disabled:opacity-50"
                              >
                                <span className="flex items-center gap-2">
                                  {pkg.is_default && <FaStar className="text-amber-500" size={12} />}
                                  {pkg.display_name}
                                </span>
                                <FaPlus size={12} className="text-violet-600" />
                              </button>
                            ))}
                        </div>
                      </div>
                    )}

                    {packageMessage && (
                      <p className={`text-sm ${packageMessage.includes('Failed') || packageMessage.includes('error') ? 'text-red-600' : 'text-emerald-700'}`}>
                        {packageMessage}
                      </p>
                    )}
                  </>
                )}
              </div>
            </Card>
            )}

            {/* Account Info */}
            <Card>
              <div className="px-6 py-4 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-slate-100 flex items-center justify-center">
                    <FaCalendar className="text-slate-600" size={18} />
                  </div>
                  <h2 className="text-lg font-bold text-slate-900">Account Info</h2>
                </div>
              </div>
              <div className="p-6">
                <div className="space-y-4 text-sm">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Created</p>
                    <p className="text-slate-900">{user.created_at ? new Date(user.created_at).toLocaleString() : 'N/A'}</p>
                  </div>
                  {user.updated_at && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Last Updated</p>
                      <p className="text-slate-900">{new Date(user.updated_at).toLocaleString()}</p>
                    </div>
                  )}
                </div>
              </div>
            </Card>
          </div>
        </div>
      </div>

      {accessConfirm ? (
        <AccessControlConfirmModal
          actionKey={accessConfirm.actionKey}
          userName={fullName}
          loading={activeStatusSaving || accessControlsSaving}
          allowPayInWhenDisabled={allowPayInWhenDisabled}
          onAllowPayInChange={
            accessConfirm.actionKey === 'disable_account' ? setAllowPayInWhenDisabled : undefined
          }
          onConfirm={handleAccessConfirm}
          onCancel={() => {
            if (!activeStatusSaving && !accessControlsSaving) {
              setAccessConfirm(null);
              setAllowPayInWhenDisabled(false);
            }
          }}
        />
      ) : null}

      <FeedbackModal
        open={selfBlockOpen}
        onClose={() => setSelfBlockOpen(false)}
        title="Cannot modify your own account"
        description="Use another administrator account to modify your own access settings."
      />

      <DeleteUserConfirmModal
        open={deleteConfirmOpen}
        user={user}
        loading={deleteSaving}
        onConfirm={performDeleteUser}
        onCancel={() => !deleteSaving && setDeleteConfirmOpen(false)}
      />
    </div>
  );
};

export default UserDetail;
