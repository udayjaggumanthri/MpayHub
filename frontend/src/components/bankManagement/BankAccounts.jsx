import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { bankAccountsAPI } from '../../services/api';
import { formatPhone } from '../../utils/formatters';
import Card from '../common/Card';
import Button from '../common/Button';
import FeedbackModal from '../common/FeedbackModal';
import {
  FaPlus,
  FaMagnifyingGlass,
  FaTrash,
  FaBuilding,
  FaEye,
  FaXmark,
  FaTriangleExclamation,
} from 'react-icons/fa6';
import AddBankAccount from './AddBankAccount';

const formatDetailValue = (value) => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value, null, 2);
  return String(value);
};

const BankAccountViewModal = ({ account, onClose }) => {
  if (!account) return null;

  const details = account.verification_details || {};
  const ifscDetails = details.ifsc_details || {};

  const rows = [
    ['Beneficiary Name', account.beneficiary_name || account.account_holder_name],
    ['Mobile Number', account.mobile_number ? formatPhone(account.mobile_number) : '—'],
    ['Account Number', account.account_number],
    ['IFSC', account.ifsc],
    ['Bank Name', account.bank_name],
    ['Branch', account.branch || details.branch],
    ['City', account.city || details.city],
    ['Reference ID', account.verification_reference_id || details.reference_id],
    ['Account Status', details.account_status],
    ['Status Code', details.account_status_code],
    ['Name Match Score', account.name_match_score || details.name_match_score],
    ['Name Match Result', account.name_match_result || details.name_match_result],
    ['UTR', details.utr],
    ['MICR', details.micr],
    ['Verified At', account.verified_at ? new Date(account.verified_at).toLocaleString() : '—'],
    ['Provider', account.provider_code],
  ];

  const ifscRows = Object.entries(ifscDetails).map(([key, value]) => [
    key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
    formatDetailValue(value),
  ]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
      <Card className="max-w-2xl w-full border-2 border-blue-200 dark:border-blue-800 my-auto" padding="lg" shadow="xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-slate-100">Bank Account Details</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors"
          >
            <FaXmark size={22} />
          </button>
        </div>

        <div className="space-y-6 max-h-[70vh] overflow-y-auto pr-1">
          <div>
            <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-3 uppercase tracking-wide">Account Summary</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {rows.map(([label, value]) => (
                <div key={label} className="rounded-lg border border-gray-200 dark:border-slate-700 p-3 bg-gray-50 dark:bg-slate-800/50">
                  <p className="text-xs text-gray-500 dark:text-slate-400">{label}</p>
                  <p className="text-sm font-medium text-gray-900 dark:text-slate-100 mt-1 break-words">{formatDetailValue(value)}</p>
                </div>
              ))}
            </div>
          </div>

          {ifscRows.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-3 uppercase tracking-wide">IFSC Details</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {ifscRows.map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-gray-200 dark:border-slate-700 p-3 bg-gray-50 dark:bg-slate-800/50">
                    <p className="text-xs text-gray-500 dark:text-slate-400">{label}</p>
                    <p className="text-sm font-medium text-gray-900 dark:text-slate-100 mt-1 break-words whitespace-pre-wrap">{value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="mt-6">
          <Button onClick={onClose} variant="primary" fullWidth>
            Close
          </Button>
        </div>
      </Card>
    </div>
  );
};

const BankAccountDeleteModal = ({ account, loading, onCancel, onConfirm }) => {
  if (!account) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-bank-account-title"
      onClick={() => !loading && onCancel()}
    >
      <div
        className="w-full max-w-md rounded-2xl bg-white dark:bg-slate-900 p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-red-50 dark:bg-red-950/40 text-red-700 dark:text-red-300">
            <FaTriangleExclamation size={22} aria-hidden />
          </div>
          <div className="min-w-0 flex-1">
            <h3 id="delete-bank-account-title" className="text-lg font-bold text-slate-900 dark:text-slate-100">
              Delete bank account?
            </h3>
            <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
              This action cannot be undone. The account will be removed from your profile.
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50 dark:bg-slate-800/50 px-4 py-3 text-sm text-slate-700 dark:text-slate-300 space-y-1">
          <p>
            <span className="font-medium">Account holder:</span>{' '}
            {account.account_holder_name || account.beneficiary_name || '—'}
          </p>
          <p>
            <span className="font-medium">Account number:</span> {account.account_number || '—'}
          </p>
          <p>
            <span className="font-medium">IFSC:</span> {account.ifsc || '—'}
          </p>
          {account.mobile_number ? (
            <p>
              <span className="font-medium">Mobile:</span> {formatPhone(account.mobile_number)}
            </p>
          ) : null}
        </div>

        <div className="mt-6 flex gap-3 justify-end">
          <Button onClick={onCancel} disabled={loading} variant="outline" size="lg">
            Cancel
          </Button>
          <Button onClick={onConfirm} loading={loading} variant="danger" size="lg" icon={FaTrash} iconPosition="left">
            Delete Account
          </Button>
        </div>
      </div>
    </div>
  );
};

const BankAccounts = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [viewAccount, setViewAccount] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState({ open: false, message: '' });
  const [filters, setFilters] = useState({
    name: '',
    bankName: '',
    accountNumber: '',
    ifsc: '',
  });

  const loadAccounts = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    try {
      const result = await bankAccountsAPI.listBankAccounts();
      if (result.success) {
        const payload = result.data || {};
        let filtered = payload.bank_accounts || payload.results || (Array.isArray(payload) ? payload : []);

        if (filters.name) {
          filtered = filtered.filter((acc) =>
            (acc.account_holder_name?.toLowerCase().includes(filters.name.toLowerCase())) ||
            (acc.beneficiary_name?.toLowerCase().includes(filters.name.toLowerCase()))
          );
        }

        if (filters.bankName) {
          filtered = filtered.filter((acc) =>
            acc.bank_name?.toLowerCase().includes(filters.bankName.toLowerCase())
          );
        }

        if (filters.accountNumber) {
          filtered = filtered.filter((acc) =>
            acc.account_number?.includes(filters.accountNumber)
          );
        }

        if (filters.ifsc) {
          filtered = filtered.filter((acc) =>
            acc.ifsc?.toUpperCase().includes(filters.ifsc.toUpperCase())
          );
        }

        setAccounts(filtered);
      } else {
        setAccounts([]);
      }
    } catch (error) {
      console.error('Error loading bank accounts:', error);
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  }, [user, filters]);

  useEffect(() => {
    loadAccounts();
  }, [loadAccounts]);

  const handleAccountAdded = () => {
    loadAccounts();
    setShowAddForm(false);
  };

  const handleDelete = (account) => {
    setDeleteTarget(account);
  };

  const confirmDelete = async () => {
    if (!deleteTarget?.id) return;
    setDeleting(true);
    try {
      const result = await bankAccountsAPI.deleteBankAccount(deleteTarget.id);
      if (result.success) {
        setDeleteTarget(null);
        loadAccounts();
      } else {
        const errorMsg = result.errors?.join(', ') || result.message || 'Failed to delete bank account';
        setDeleteTarget(null);
        setDeleteError({ open: true, message: errorMsg });
      }
    } catch (error) {
      console.error('Error deleting bank account:', error);
      setDeleteTarget(null);
      setDeleteError({ open: true, message: 'An error occurred. Please try again.' });
    } finally {
      setDeleting(false);
    }
  };

  const handleFilter = () => {
    loadAccounts();
  };

  const clearFilters = () => {
    setFilters({ name: '', bankName: '', accountNumber: '', ifsc: '' });
  };

  if (showAddForm) {
    return (
      <AddBankAccount
        onCancel={() => setShowAddForm(false)}
        onSuccess={handleAccountAdded}
      />
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 px-4 sm:px-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-slate-100">All Bank Accounts</h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600 dark:text-slate-400">
            Manage verified bank accounts for payouts
          </p>
        </div>
        <Button
          onClick={() => setShowAddForm(true)}
          variant="primary"
          icon={FaPlus}
          iconPosition="left"
          className="mt-4 sm:mt-0"
        >
          Create Account
        </Button>
      </div>

      <Card padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-4">Filter</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">Name</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-slate-500" size={18} />
              <input
                type="text"
                value={filters.name}
                onChange={(e) => setFilters({ ...filters, name: e.target.value })}
                placeholder="Enter Name"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">Bank Name</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-slate-500" size={18} />
              <input
                type="text"
                value={filters.bankName}
                onChange={(e) => setFilters({ ...filters, bankName: e.target.value })}
                placeholder="Enter Bank name"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">Account Number</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-slate-500" size={18} />
              <input
                type="text"
                value={filters.accountNumber}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '');
                  setFilters({ ...filters, accountNumber: value });
                }}
                placeholder="Enter Account Number"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">IFSC CODE</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-slate-500" size={18} />
              <input
                type="text"
                value={filters.ifsc}
                onChange={(e) => {
                  const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 11);
                  setFilters({ ...filters, ifsc: value });
                }}
                placeholder="Enter IFSC Code"
                maxLength={11}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent uppercase"
              />
            </div>
          </div>
        </div>
        <div className="mt-4 flex justify-end space-x-3">
          <Button onClick={clearFilters} variant="outline" size="sm">
            Clear
          </Button>
          <Button onClick={handleFilter} variant="primary" size="sm">
            Filter
          </Button>
        </div>
      </Card>

      <Card padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-4">All Links</h3>
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600 dark:text-slate-400">Loading bank accounts...</p>
          </div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-12 text-gray-500 dark:text-slate-400">
            <p className="text-lg">No bank accounts found</p>
            <p className="text-sm mt-2">Click "Create Account" to add a new bank account</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">#</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                    ACCOUNT HOLDER NAME
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                    ACCOUNT NUMBER
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                    BANK NAME
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                    MOBILE
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                    IFSC
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                    ACTIONS
                  </th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account, index) => {
                  const accountHolderName = account.account_holder_name || account.beneficiary_name || 'N/A';
                  const accountNumber = account.account_number || 'N/A';
                  const bankName = account.bank_name || 'N/A';
                  const ifsc = account.ifsc || 'N/A';
                  const mobile = account.mobile_number || '—';

                  return (
                    <tr key={account.id} className="border-b border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors">
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900 dark:text-slate-100">{index + 1}</td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900 dark:text-slate-100">
                        {accountHolderName}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-slate-300 font-mono">
                        {accountNumber}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-slate-300">
                        <div className="flex items-center space-x-2">
                          <FaBuilding size={14} className="text-gray-400 dark:text-slate-500" />
                          <span>{bankName}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-slate-300">
                        {mobile !== '—' ? formatPhone(mobile) : mobile}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700 dark:text-slate-300 font-mono">{ifsc}</td>
                      <td className="px-4 py-4 whitespace-nowrap text-center">
                        <div className="inline-flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => setViewAccount(account)}
                            className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 transition-colors p-1 rounded hover:bg-blue-50 dark:hover:bg-blue-950/60"
                            title="View Details"
                          >
                            <FaEye size={18} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDelete(account)}
                            className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200 transition-colors p-1 rounded hover:bg-red-50 dark:hover:bg-red-950/60"
                            title="Delete Account"
                          >
                            <FaTrash size={18} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {viewAccount && (
        <BankAccountViewModal account={viewAccount} onClose={() => setViewAccount(null)} />
      )}

      {deleteTarget && (
        <BankAccountDeleteModal
          account={deleteTarget}
          loading={deleting}
          onCancel={() => !deleting && setDeleteTarget(null)}
          onConfirm={confirmDelete}
        />
      )}

      <FeedbackModal
        open={deleteError.open}
        onClose={() => setDeleteError({ open: false, message: '' })}
        title="Could not delete account"
        description={deleteError.message}
      />
    </div>
  );
};

export default BankAccounts;
