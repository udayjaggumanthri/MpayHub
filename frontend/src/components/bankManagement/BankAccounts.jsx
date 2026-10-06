import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { bankAccountsAPI } from '../../services/api';
import { formatPhone } from '../../utils/formatters';
import Card from '../common/Card';
import Button from '../common/Button';
import FeedbackModal from '../common/FeedbackModal';
import {
  FaPlus,
  FaBuilding,
} from 'react-icons/fa6';
import AddBankAccount from './AddBankAccount';
import BankAccountPager, { linkedContactLabel } from './BankAccountPager';
import { AccountRowActions, BankAccountConfirmModal, BankAccountDetailsModal } from './BankAccountDialogs';
import {
  DataTableScroll,
  FilterActions,
  FilterField,
  actionTdClass,
  actionThClass,
  filterInputClass,
  tdClass,
  thClass,
} from './ListChrome';

const BankAccounts = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [viewAccount, setViewAccount] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState({ open: false, message: '' });
  const [filterDraft, setFilterDraft] = useState({
    name: '',
    bankName: '',
    accountNumber: '',
    ifsc: '',
  });
  const [appliedFilters, setAppliedFilters] = useState({
    name: '',
    bankName: '',
    accountNumber: '',
    ifsc: '',
  });
  const [page, setPage] = useState(1);
  const [totalCount, setTotalCount] = useState(0);
  const pageSize = 20;

  const loadAccounts = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    try {
      const params = { page, page_size: pageSize };
      if (appliedFilters.name) params.name = appliedFilters.name;
      if (appliedFilters.bankName) params.bank_name = appliedFilters.bankName;
      if (appliedFilters.accountNumber) params.account_number = appliedFilters.accountNumber;
      if (appliedFilters.ifsc) params.ifsc = appliedFilters.ifsc;
      const result = await bankAccountsAPI.listBankAccounts(params);
      if (result.success) {
        const payload = result.data || {};
        const rows = payload.bank_accounts || payload.results || (Array.isArray(payload) ? payload : []);
        setAccounts(rows);
        setTotalCount(Number(payload.count ?? rows.length) || 0);
      } else {
        setAccounts([]);
        setTotalCount(0);
      }
    } catch (error) {
      console.error('Error loading bank accounts:', error);
      setAccounts([]);
      setTotalCount(0);
    } finally {
      setLoading(false);
    }
  }, [user, appliedFilters, page]);

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
    setPage(1);
    setAppliedFilters({ ...filterDraft });
  };

  const clearFilters = () => {
    const empty = { name: '', bankName: '', accountNumber: '', ifsc: '' };
    setFilterDraft(empty);
    setAppliedFilters(empty);
    setPage(1);
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
            Manage verified bank accounts linked to contacts for payouts
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
        <div className="grid grid-cols-1 items-end gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <FilterField label="Name">
            <input
              type="text"
              value={filterDraft.name}
              onChange={(e) => setFilterDraft({ ...filterDraft, name: e.target.value })}
              placeholder="Account holder"
              className={filterInputClass}
            />
          </FilterField>
          <FilterField label="Bank name">
            <input
              type="text"
              value={filterDraft.bankName}
              onChange={(e) => setFilterDraft({ ...filterDraft, bankName: e.target.value })}
              placeholder="Bank name"
              className={filterInputClass}
            />
          </FilterField>
          <FilterField label="Account number">
            <input
              type="text"
              value={filterDraft.accountNumber}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '');
                setFilterDraft({ ...filterDraft, accountNumber: value });
              }}
              placeholder="Account number"
              className={filterInputClass}
            />
          </FilterField>
          <FilterField label="IFSC">
            <input
              type="text"
              value={filterDraft.ifsc}
              onChange={(e) => {
                const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 11);
                setFilterDraft({ ...filterDraft, ifsc: value });
              }}
              placeholder="IFSC"
              maxLength={11}
              className={`${filterInputClass} uppercase`}
            />
          </FilterField>
          <FilterActions onClear={clearFilters} onApply={handleFilter} />
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
          <>
          <div className="md:hidden space-y-3">
            {accounts.map((account, index) => (
              <div key={account.id} className="rounded-xl border border-gray-200 dark:border-slate-700 p-4 bg-gray-50 dark:bg-slate-800/40">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-xs text-gray-500 dark:text-slate-400">#{(page - 1) * pageSize + index + 1}</p>
                    <p className="text-sm font-semibold text-gray-900 dark:text-slate-100 break-words">
                      {account.account_holder_name || account.beneficiary_name || 'N/A'}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-slate-400 mt-1 break-all">{account.account_number}</p>
                  </div>
                  <FaBuilding className="text-gray-400 dark:text-slate-500 shrink-0" size={16} />
                </div>
                <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <dt className="text-xs text-gray-500 dark:text-slate-400">Bank</dt>
                    <dd className="text-gray-800 dark:text-slate-200 break-words">{account.bank_name || '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500 dark:text-slate-400">IFSC</dt>
                    <dd className="font-mono text-gray-800 dark:text-slate-200">{account.ifsc || '—'}</dd>
                  </div>
                  <div className="col-span-2">
                    <dt className="text-xs text-gray-500 dark:text-slate-400">Contacts</dt>
                    <dd className="text-gray-800 dark:text-slate-200 break-words">{linkedContactLabel(account)}</dd>
                  </div>
                </dl>
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-slate-700">
                  <AccountRowActions
                    onView={() => setViewAccount(account)}
                    onDelete={() => handleDelete(account)}
                  />
                </div>
              </div>
            ))}
          </div>
          <DataTableScroll>
            <table className="w-max min-w-full border-separate border-spacing-0">
              <thead>
                <tr>
                  <th className={thClass}>#</th>
                  <th className={thClass}>Contact</th>
                  <th className={thClass}>Account holder</th>
                  <th className={thClass}>Account number</th>
                  <th className={thClass}>Bank</th>
                  <th className={thClass}>Mobile</th>
                  <th className={thClass}>IFSC</th>
                  <th className={actionThClass}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account, index) => {
                  const contactLabel = linkedContactLabel(account);
                  const accountHolderName = account.account_holder_name || account.beneficiary_name || '—';
                  const mobile = account.mobile_number ? formatPhone(account.mobile_number) : '—';
                  return (
                    <tr key={account.id} className="group">
                      <td className={tdClass}>{(page - 1) * pageSize + index + 1}</td>
                      <td className={`${tdClass} font-medium text-gray-900 dark:text-slate-100`} title={contactLabel}>
                        {contactLabel}
                      </td>
                      <td className={`${tdClass} font-medium text-gray-900 dark:text-slate-100`}>{accountHolderName}</td>
                      <td className={`${tdClass} font-mono`}>{account.account_number || '—'}</td>
                      <td className={tdClass}>
                        <span className="inline-flex items-center gap-2">
                          <FaBuilding size={14} className="text-gray-400 dark:text-slate-500" />
                          {account.bank_name || '—'}
                        </span>
                      </td>
                      <td className={tdClass}>{mobile}</td>
                      <td className={`${tdClass} font-mono`}>{account.ifsc || '—'}</td>
                      <td className={actionTdClass}>
                        <AccountRowActions
                          onView={() => setViewAccount(account)}
                          onDelete={() => handleDelete(account)}
                        />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </DataTableScroll>
          </>
        )}
        {!loading && (
          <BankAccountPager
            page={page}
            pageSize={pageSize}
            totalCount={totalCount}
            onPageChange={setPage}
          />
        )}
      </Card>

      <BankAccountDetailsModal account={viewAccount} onClose={() => setViewAccount(null)} />

      <BankAccountConfirmModal
        account={deleteTarget}
        title="Delete bank account?"
        description="This removes the account from your profile. Payout history already recorded for this account is left as it is."
        confirmLabel="Delete account"
        loading={deleting}
        onCancel={() => !deleting && setDeleteTarget(null)}
        onConfirm={confirmDelete}
      />

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
