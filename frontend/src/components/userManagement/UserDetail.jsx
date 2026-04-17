import React, { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { usersAPI, fundManagementAPI } from '../../services/api';
import { formatUserId } from '../../utils/formatters';
import { useAuth } from '../../context/AuthContext';
import {
  FaArrowLeft,
  FaUser,
  FaBuilding,
  FaPhone,
  FaEnvelope,
  FaChevronRight,
  FaSitemap,
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
} from 'react-icons/fa6';
import Button from '../common/Button';
import Card from '../common/Card';
import FeedbackModal from '../common/FeedbackModal';

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

  const [activeStatusSaving, setActiveStatusSaving] = useState(false);
  const [activeStatusMessage, setActiveStatusMessage] = useState('');
  const [accountConfirm, setAccountConfirm] = useState(null);
  const [selfBlockOpen, setSelfBlockOpen] = useState(false);

  const [userPackages, setUserPackages] = useState({ assigned: [], accessible: [] });
  const [assignablePackages, setAssignablePackages] = useState([]);
  const [packagesLoading, setPackagesLoading] = useState(false);
  const [packageAssigning, setPackageAssigning] = useState(null);
  const [packageMessage, setPackageMessage] = useState('');

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
        setError(res.message || 'User not found.');
      }
    } catch (err) {
      setError('Failed to load user details.');
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  const loadUserPackages = useCallback(async () => {
    if (!userId) return;
    setPackagesLoading(true);
    setPackageMessage('');
    try {
      const [pkgRes, assignableRes] = await Promise.all([
        fundManagementAPI.getUserPackages(userId),
        fundManagementAPI.getAssignablePackages(),
      ]);
      if (pkgRes.success && pkgRes.data) {
        setUserPackages({
          assigned: pkgRes.data.assigned_packages || [],
          accessible: pkgRes.data.accessible_packages || [],
        });
      } else {
        setPackageMessage(pkgRes.message || '');
      }
      if (assignableRes.success && assignableRes.data?.packages) {
        setAssignablePackages(assignableRes.data.packages);
      }
    } catch (err) {
      console.error('Failed to load packages:', err);
    } finally {
      setPackagesLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    if (user) {
      loadUserPackages();
    }
  }, [user, loadUserPackages]);

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

  const performActiveToggle = async (nextActive) => {
    setActiveStatusSaving(true);
    setActiveStatusMessage('');
    try {
      const res = await usersAPI.setUserActiveStatus(user.id, nextActive);
      const u = res.data?.user ?? res.data;
      if (res.success && u && u.id != null) {
        setUser(u);
        setActiveStatusMessage(res.message || (nextActive ? 'Account enabled.' : 'Account disabled.'));
      } else {
        const msg = res.message || res.errors?.[0] || 'Update failed.';
        setActiveStatusMessage(typeof msg === 'string' ? msg : 'Update failed.');
      }
    } catch {
      setActiveStatusMessage('Update failed.');
    } finally {
      setActiveStatusSaving(false);
      setAccountConfirm(null);
    }
  };

  const requestToggleAccountActive = (nextActive) => {
    if (!isAdmin || !user?.id) return;
    if (String(user.id) === String(currentUserId)) {
      setSelfBlockOpen(true);
      return;
    }
    setAccountConfirm({ nextActive });
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
            <span
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold ${
                accountIsActive(user)
                  ? 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200'
                  : 'bg-red-100 text-red-800 ring-1 ring-red-200'
              }`}
            >
              <span className={`h-2 w-2 rounded-full ${accountIsActive(user) ? 'bg-emerald-500' : 'bg-red-500'}`} />
              {accountIsActive(user) ? 'Active' : 'Disabled'}
            </span>
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
                    <p className="text-slate-900 break-all">{user.email || 'N/A'}</p>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 text-slate-500 text-xs font-semibold uppercase tracking-wide mb-2">
                      <FaPhone size={12} />
                      Phone
                    </div>
                    <p className="text-slate-900 font-mono tabular-nums">{user.phone || 'N/A'}</p>
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

            {/* Hierarchy Section */}
            {user.hierarchy_lineage && (
              <Card>
                <div className="px-6 py-4 border-b border-slate-100">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-cyan-100 flex items-center justify-center">
                      <FaSitemap className="text-cyan-600" size={18} />
                    </div>
                    <div>
                      <h2 className="text-lg font-bold text-slate-900">Hierarchy</h2>
                      <p className="text-sm text-slate-500">
                        Path: <code className="font-mono text-indigo-600">{user.hierarchy_lineage.map_path || '—'}</code>
                      </p>
                    </div>
                  </div>
                </div>
                <div className="p-6 space-y-6">
                  {/* Hierarchy Chain */}
                  <div className="flex flex-wrap items-center gap-2">
                    {(user.hierarchy_lineage.upline || []).map((node, idx) => (
                      <React.Fragment key={`${node.user_id}-${idx}`}>
                        {idx > 0 && <FaChevronRight className="text-slate-300" size={12} />}
                        <div className="inline-flex flex-col items-center rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                          <span className="font-mono text-sm font-bold text-indigo-700">{formatUserId(node.user_id)}</span>
                          <span className="text-[10px] uppercase text-slate-500 mt-0.5">{node.role}</span>
                        </div>
                      </React.Fragment>
                    ))}
                    {(user.hierarchy_lineage.upline || []).length > 0 && (
                      <FaChevronRight className="text-slate-300" size={12} />
                    )}
                    <div className="inline-flex flex-col items-center rounded-xl border-2 border-indigo-400 bg-indigo-50 px-3 py-2">
                      <span className="font-mono text-sm font-bold text-indigo-800">
                        {formatUserId(user.user_id || user.id)}
                      </span>
                      <span className="text-[10px] uppercase text-indigo-600 mt-0.5">{user.role}</span>
                    </div>
                  </div>

                  {/* Direct Parent */}
                  {(user.hierarchy_lineage.direct_parents || []).length > 0 && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">Direct Parent</p>
                      <div className="overflow-hidden rounded-xl border border-slate-200">
                        <table className="w-full text-sm">
                          <thead className="bg-slate-50">
                            <tr>
                              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-slate-500">User ID</th>
                              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-slate-500">Role</th>
                              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-slate-500">Name</th>
                              <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-slate-500">Linked</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {user.hierarchy_lineage.direct_parents.map((p) => (
                              <tr key={p.user_id} className="bg-white">
                                <td className="px-4 py-3 font-mono text-indigo-700 font-medium">{formatUserId(p.user_id)}</td>
                                <td className="px-4 py-3 text-slate-700">{p.role}</td>
                                <td className="px-4 py-3 text-slate-900">{p.name}</td>
                                <td className="px-4 py-3 text-slate-500 text-xs">
                                  {p.linked_at ? new Date(p.linked_at).toLocaleDateString() : '—'}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Direct Reports */}
                  {user.hierarchy_lineage.direct_reports_total > 0 && (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">
                        Direct Reports ({user.hierarchy_lineage.direct_reports_total})
                      </p>
                      <div className="max-h-48 overflow-y-auto rounded-xl border border-slate-200 bg-white">
                        <div className="divide-y divide-slate-100">
                          {(user.hierarchy_lineage.direct_reports || []).map((c) => (
                            <Link
                              key={c.user_id}
                              to={`/admin/users/${c.id || c.user_id}`}
                              className="flex items-center gap-4 px-4 py-3 hover:bg-slate-50 transition-colors"
                            >
                              <span className="font-mono text-sm font-semibold text-indigo-700">{formatUserId(c.user_id)}</span>
                              <span className={`text-xs font-medium px-2 py-0.5 rounded-md ${roleBadgeClass(c.role)}`}>{c.role}</span>
                              <span className="text-slate-700 text-sm">{c.name}</span>
                            </Link>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            )}

            {/* KYC Information */}
            <Card>
              <div className="px-6 py-4 border-b border-slate-100">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-xl bg-emerald-100 flex items-center justify-center">
                    <FaIdCard className="text-emerald-600" size={18} />
                  </div>
                  <h2 className="text-lg font-bold text-slate-900">KYC & Compliance</h2>
                </div>
              </div>
              <div className="p-6">
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

                {(user.kyc?.pan_number || user.kyc?.aadhaar_number) && (
                  <div className="mt-6 pt-6 border-t border-slate-100">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-4">Identity Documents</p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                      {user.kyc?.pan_number && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                          <p className="text-xs font-semibold uppercase text-slate-500 mb-1">PAN Number</p>
                          <p className="font-mono text-slate-900 font-medium">{user.kyc.pan_number}</p>
                          {user.kyc.pan_verified && (
                            <span className="inline-flex items-center gap-1 mt-2 text-xs text-emerald-700">
                              <FaCircleCheck size={10} /> Verified
                            </span>
                          )}
                        </div>
                      )}
                      {user.kyc?.aadhaar_number && (
                        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
                          <p className="text-xs font-semibold uppercase text-slate-500 mb-1">Aadhaar Number</p>
                          <p className="font-mono text-slate-900 font-medium">
                            {user.kyc.aadhaar_number.substring(0, 4)} **** {user.kyc.aadhaar_number.substring(8)}
                          </p>
                          {user.kyc.aadhaar_verified && (
                            <span className="inline-flex items-center gap-1 mt-2 text-xs text-emerald-700">
                              <FaCircleCheck size={10} /> Verified
                            </span>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
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
                    <div className="flex gap-2">
                      <Button
                        onClick={() => requestToggleAccountActive(false)}
                        disabled={activeStatusSaving || !accountIsActive(user)}
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
                        disabled={activeStatusSaving || accountIsActive(user)}
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
                        activeStatusMessage.includes('enabled') || activeStatusMessage.includes('disabled')
                          ? 'text-emerald-700'
                          : 'text-red-600'
                      }`}>
                        {activeStatusMessage}
                      </p>
                    )}
                  </div>
                </div>
              </Card>
            )}

            {/* Pay-in Packages */}
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
                              <button
                                onClick={() => handleRemovePackage(pkg.id)}
                                disabled={packageAssigning === pkg.id}
                                className="rounded-lg p-2 text-violet-600 hover:bg-violet-100 hover:text-red-600 transition-colors disabled:opacity-50"
                                title="Remove package"
                              >
                                <FaTrash size={14} />
                              </button>
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

                    {/* Assign New Package */}
                    {assignablePackages.filter((pkg) => !userPackages.assigned.find((ap) => ap.id === pkg.id)).length > 0 && (
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

      {/* Account Confirm Dialog */}
      {accountConfirm && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
          onClick={() => !activeStatusSaving && setAccountConfirm(null)}
        >
          <div
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start gap-4">
              <div
                className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${
                  accountConfirm.nextActive ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-800'
                }`}
              >
                {accountConfirm.nextActive ? <FaUserCheck size={22} /> : <FaUserSlash size={22} />}
              </div>
              <div className="flex-1">
                <h3 className="text-lg font-bold text-slate-900">
                  {accountConfirm.nextActive ? 'Enable account?' : 'Disable account?'}
                </h3>
                <p className="mt-2 text-sm text-slate-600">
                  {accountConfirm.nextActive
                    ? `${fullName} will be able to sign in and use the platform.`
                    : `${fullName} will be signed out and cannot log in until re-enabled.`}
                </p>
              </div>
            </div>
            <div className="mt-6 flex gap-3 justify-end">
              <Button
                onClick={() => setAccountConfirm(null)}
                disabled={activeStatusSaving}
                variant="outline"
                size="lg"
              >
                Cancel
              </Button>
              <Button
                onClick={() => performActiveToggle(accountConfirm.nextActive)}
                loading={activeStatusSaving}
                variant={accountConfirm.nextActive ? 'success' : 'danger'}
                size="lg"
              >
                {accountConfirm.nextActive ? 'Enable' : 'Disable'}
              </Button>
            </div>
          </div>
        </div>
      )}

      <FeedbackModal
        open={selfBlockOpen}
        onClose={() => setSelfBlockOpen(false)}
        title="Cannot modify your own account"
        description="Use another administrator account to modify your own access settings."
      />
    </div>
  );
};

export default UserDetail;
