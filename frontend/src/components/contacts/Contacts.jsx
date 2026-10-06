import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { contactsAPI, bankAccountsAPI } from '../../services/api';
import { validatePhone, validateEmail } from '../../utils/validators';
import { contactsFromListResult } from '../../utils/contactsHelpers';
import { formatPhone } from '../../utils/formatters';
import Card from '../common/Card';
import Button from '../common/Button';
import Input from '../common/Input';
import AddBankAccount from '../bankManagement/AddBankAccount';
import BankAccountPager from '../bankManagement/BankAccountPager';
import { AccountRowActions, BankAccountConfirmModal, BankAccountDetailsModal } from '../bankManagement/BankAccountDialogs';
import {
  DataTableScroll,
  FilterActions,
  FilterField,
  actionTdClass,
  actionThClass,
  filterInputClass,
  tdClass,
  thClass,
} from '../bankManagement/ListChrome';
import {
  FaPlus,
  FaPen,
  FaX,
  FaUser,
  FaEnvelope,
  FaPhone,
  FaBuilding,
  FaEye,
  FaArrowLeft,
} from 'react-icons/fa6';

const EMPTY_FILTERS = { name: '', email: '', phone: '' };

const EMPTY_FORM = { name: '', email: '', phone: '' };

const Contacts = () => {
  const { user } = useAuth();
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterDraft, setFilterDraft] = useState({ ...EMPTY_FILTERS });
  const [filterApplied, setFilterApplied] = useState({ ...EMPTY_FILTERS });
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedContact, setSelectedContact] = useState(null);
  const [formData, setFormData] = useState({ ...EMPTY_FORM });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [totalCount, setTotalCount] = useState(null);
  const [loadError, setLoadError] = useState('');

  // Contact → bank accounts drill-down
  const [detailContact, setDetailContact] = useState(null);
  const [contactAccounts, setContactAccounts] = useState([]);
  const [accountsLoading, setAccountsLoading] = useState(false);
  const [accountsError, setAccountsError] = useState('');
  const [accountFilterDraft, setAccountFilterDraft] = useState({
    name: '',
    bankName: '',
    accountNumber: '',
    ifsc: '',
  });
  const [accountFilters, setAccountFilters] = useState({
    name: '',
    bankName: '',
    accountNumber: '',
    ifsc: '',
  });
  const [accountPage, setAccountPage] = useState(1);
  const [accountTotal, setAccountTotal] = useState(0);
  const accountPageSize = 20;
  const [showAddBank, setShowAddBank] = useState(false);
  const [viewAccount, setViewAccount] = useState(null);
  const [removeTarget, setRemoveTarget] = useState(null);
  const [removing, setRemoving] = useState(false);

  const loadContacts = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    setLoadError('');
    try {
      const params = { page_size: 100 };
      const n = filterApplied.name?.trim();
      const e = filterApplied.email?.trim();
      const p = filterApplied.phone?.replace(/\D/g, '').slice(0, 10);
      if (n) params.name = n;
      if (e) params.email = e;
      if (p) params.phone = p;

      const result = await contactsAPI.listContacts(params);
      const { contacts: rows, totalCount: total } = contactsFromListResult(result);
      if (result.success) {
        setContacts(rows);
        setTotalCount(total);
      } else {
        setContacts([]);
        setTotalCount(null);
        setLoadError(result.message || 'Failed to load contacts');
      }
    } catch (error) {
      console.error('Error loading contacts:', error);
      setContacts([]);
      setTotalCount(null);
      setLoadError('Failed to load contacts');
    } finally {
      setLoading(false);
    }
  }, [user, filterApplied]);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  const loadContactAccounts = useCallback(async (contact) => {
    if (!contact?.id) return;
    setAccountsLoading(true);
    setAccountsError('');
    try {
      const params = { contact: contact.id, page: accountPage, page_size: accountPageSize };
      if (accountFilters.name) params.name = accountFilters.name;
      if (accountFilters.bankName) params.bank_name = accountFilters.bankName;
      if (accountFilters.accountNumber) params.account_number = accountFilters.accountNumber;
      if (accountFilters.ifsc) params.ifsc = accountFilters.ifsc;
      const result = await bankAccountsAPI.listBankAccounts(params);
      if (result.success) {
        const payload = result.data || {};
        const rows = payload.bank_accounts || payload.results || (Array.isArray(payload) ? payload : []);
        setContactAccounts(rows);
        setAccountTotal(Number(payload.count ?? rows.length) || 0);
      } else {
        setContactAccounts([]);
        setAccountTotal(0);
        setAccountsError(result.message || 'Failed to load bank accounts');
      }
    } catch (error) {
      console.error('Error loading contact bank accounts:', error);
      setContactAccounts([]);
      setAccountTotal(0);
      setAccountsError('Failed to load bank accounts');
    } finally {
      setAccountsLoading(false);
    }
  }, [accountPage, accountFilters]);

  useEffect(() => {
    if (detailContact?.id) {
      loadContactAccounts(detailContact);
    }
  }, [detailContact, loadContactAccounts]);

  const openContactDetail = (contact) => {
    setDetailContact(contact);
    setShowAddBank(false);
    setContactAccounts([]);
    setAccountPage(1);
    const empty = { name: '', bankName: '', accountNumber: '', ifsc: '' };
    setAccountFilterDraft(empty);
    setAccountFilters(empty);
  };

  const closeContactDetail = () => {
    setDetailContact(null);
    setContactAccounts([]);
    setAccountsError('');
    setShowAddBank(false);
    setViewAccount(null);
    setRemoveTarget(null);
  };

  const confirmRemoveAccount = async () => {
    if (!removeTarget?.id || !detailContact?.id) return;
    setRemoving(true);
    try {
      const result = await bankAccountsAPI.unlinkBankAccount({
        bankAccountId: removeTarget.id,
        contactId: detailContact.id,
      });
      if (result.success) {
        setRemoveTarget(null);
        await loadContactAccounts(detailContact);
      } else {
        setAccountsError(result.message || 'Could not remove this bank account from the contact.');
        setRemoveTarget(null);
      }
    } catch (error) {
      console.error('Error removing bank account link:', error);
      setAccountsError('Could not remove this bank account from the contact.');
      setRemoveTarget(null);
    } finally {
      setRemoving(false);
    }
  };

  const handleAddNew = () => {
    setFormData({ ...EMPTY_FORM });
    setErrors({});
    setSelectedContact(null);
    setShowAddModal(true);
  };

  const handleEdit = (contact, e) => {
    if (e) e.stopPropagation();
    setFormData({
      name: contact.name || '',
      email: contact.email || '',
      phone: contact.phone || '',
    });
    setErrors({});
    setSelectedContact(contact);
    setShowEditModal(true);
  };

  const handleInputChange = (field, value) => {
    setFormData({ ...formData, [field]: value });
    if (errors[field]) {
      setErrors({ ...errors, [field]: '' });
    }
  };

  const validateForm = () => {
    const newErrors = {};

    if (!formData.name || formData.name.trim().length < 2) {
      newErrors.name = 'Full name must be at least 2 characters';
    }

    const emailTrim = (formData.email || '').trim();
    if (!emailTrim) {
      newErrors.email = 'Email address is required';
    } else {
      const emailValidation = validateEmail(emailTrim);
      if (!emailValidation.valid) {
        newErrors.email = emailValidation.message;
      }
    }

    const phoneValidation = validatePhone(formData.phone);
    if (!phoneValidation.valid) {
      newErrors.phone = phoneValidation.message;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const formatApiErrors = (result) => {
    if (Array.isArray(result.errors) && result.errors.length > 0) {
      return result.errors.join(', ');
    }
    if (result.errors && typeof result.errors === 'object') {
      const flattened = Object.entries(result.errors).flatMap(([field, messages]) => {
        if (Array.isArray(messages)) {
          return messages.map((msg) => `${field}: ${msg}`);
        }
        return [`${field}: ${messages}`];
      });
      if (flattened.length > 0) return flattened.join(', ');
    }
    return result.message || 'Request failed';
  };

  const handleSave = async () => {
    if (!validateForm()) return;

    setSaving(true);
    try {
      const payload = {
        name: formData.name.trim(),
        email: formData.email.trim(),
        phone: String(formData.phone || '').replace(/\D/g, '').slice(0, 10),
      };
      if (selectedContact) {
        const result = await contactsAPI.updateContact(selectedContact.id, payload);
        if (result.success) {
          await loadContacts();
          if (detailContact?.id === selectedContact.id) {
            const updated = { ...detailContact, ...payload };
            setDetailContact(updated);
          }
          setShowEditModal(false);
          setSelectedContact(null);
        } else {
          alert(formatApiErrors(result));
        }
      } else {
        const result = await contactsAPI.createContact(payload);
        if (result.success) {
          await loadContacts();
          setShowAddModal(false);
          setFormData({ ...EMPTY_FORM });
        } else {
          alert(formatApiErrors(result));
        }
      }
    } catch (error) {
      console.error('Error saving contact:', error);
      alert('An error occurred. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const applyFilters = () => {
    setFilterApplied({
      name: filterDraft.name,
      email: filterDraft.email,
      phone: filterDraft.phone,
    });
  };

  const clearFilters = () => {
    setFilterDraft({ ...EMPTY_FILTERS });
    setFilterApplied({ ...EMPTY_FILTERS });
  };

  const closeAddModal = () => {
    setShowAddModal(false);
    setFormData({ ...EMPTY_FORM });
    setErrors({});
  };

  const closeEditModal = () => {
    setShowEditModal(false);
    setSelectedContact(null);
    setFormData({ ...EMPTY_FORM });
    setErrors({});
  };

  // Full-page add bank under selected contact
  if (showAddBank && detailContact) {
    return (
      <AddBankAccount
        presetContact={detailContact}
        onCancel={() => setShowAddBank(false)}
        onSuccess={() => {
          setShowAddBank(false);
          loadContactAccounts(detailContact);
        }}
      />
    );
  }

  // Contact detail: linked bank accounts
  if (detailContact) {
    return (
      <div className="max-w-7xl mx-auto space-y-6 px-4 sm:px-0">
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <button
              type="button"
              onClick={closeContactDetail}
              className="inline-flex items-center gap-2 text-sm text-blue-600 dark:text-blue-400 hover:underline mb-3"
            >
              <FaArrowLeft size={14} />
              Back to contacts
            </button>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-slate-100">
              {detailContact.name}
            </h1>
            <p className="mt-1 text-sm text-gray-600 dark:text-slate-400">
              {detailContact.phone}
              {detailContact.email ? ` · ${detailContact.email}` : ''}
            </p>
            <p className="mt-2 text-sm text-gray-500 dark:text-slate-400">
              Bank accounts linked to this contact
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              variant="outline"
              icon={FaPen}
              iconPosition="left"
              onClick={() => handleEdit(detailContact)}
            >
              Edit contact
            </Button>
            <Button
              type="button"
              variant="primary"
              icon={FaPlus}
              iconPosition="left"
              onClick={() => setShowAddBank(true)}
            >
              Add bank account
            </Button>
          </div>
        </div>

        <Card padding="lg">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-4">Filter</h3>
          <div className="mb-6 grid grid-cols-1 items-end gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <FilterField label="Account holder">
              <input
                type="text"
                value={accountFilterDraft.name}
                onChange={(e) => setAccountFilterDraft({ ...accountFilterDraft, name: e.target.value })}
                placeholder="Account holder"
                className={filterInputClass}
              />
            </FilterField>
            <FilterField label="Bank name">
              <input
                type="text"
                value={accountFilterDraft.bankName}
                onChange={(e) => setAccountFilterDraft({ ...accountFilterDraft, bankName: e.target.value })}
                placeholder="Bank name"
                className={filterInputClass}
              />
            </FilterField>
            <FilterField label="Account number">
              <input
                type="text"
                value={accountFilterDraft.accountNumber}
                onChange={(e) => setAccountFilterDraft({
                  ...accountFilterDraft,
                  accountNumber: e.target.value.replace(/\D/g, ''),
                })}
                placeholder="Account number"
                className={filterInputClass}
              />
            </FilterField>
            <FilterField label="IFSC">
              <input
                type="text"
                value={accountFilterDraft.ifsc}
                onChange={(e) => setAccountFilterDraft({
                  ...accountFilterDraft,
                  ifsc: e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 11),
                })}
                placeholder="IFSC"
                maxLength={11}
                className={`${filterInputClass} uppercase`}
              />
            </FilterField>
            <FilterActions
              onClear={() => {
                const empty = { name: '', bankName: '', accountNumber: '', ifsc: '' };
                setAccountFilterDraft(empty);
                setAccountFilters(empty);
                setAccountPage(1);
              }}
              onApply={() => {
                setAccountPage(1);
                setAccountFilters({ ...accountFilterDraft });
              }}
            />
          </div>
          {accountsError && (
            <div className="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-100 dark:border-red-900 text-red-700 dark:text-red-300 text-sm px-4 py-2">
              {accountsError}
            </div>
          )}
          {accountsLoading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
              <p className="mt-4 text-gray-600 dark:text-slate-400">Loading bank accounts...</p>
            </div>
          ) : contactAccounts.length === 0 ? (
            <div className="text-center py-12 text-gray-500 dark:text-slate-400">
              <FaBuilding className="mx-auto mb-3 text-gray-300 dark:text-slate-600" size={36} />
              <p className="text-lg">No bank accounts for this contact</p>
              <p className="text-sm mt-2 mb-4">Add a verified account to use for payouts.</p>
              <Button type="button" variant="primary" icon={FaPlus} iconPosition="left" onClick={() => setShowAddBank(true)}>
                Add bank account
              </Button>
            </div>
          ) : (
            <>
            <div className="md:hidden space-y-3">
              {contactAccounts.map((account, index) => (
                <div key={account.id} className="rounded-xl border border-gray-200 dark:border-slate-700 p-4 bg-gray-50 dark:bg-slate-800/40">
                  <p className="text-xs text-gray-500 dark:text-slate-400">#{(accountPage - 1) * accountPageSize + index + 1}</p>
                  <p className="text-sm font-semibold text-gray-900 dark:text-slate-100 break-words">
                    {account.account_holder_name || account.beneficiary_name || '—'}
                  </p>
                  <p className="text-sm text-gray-600 dark:text-slate-400 mt-1 break-all">{account.account_number || '—'}</p>
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
                      <dt className="text-xs text-gray-500 dark:text-slate-400">Mobile</dt>
                      <dd className="text-gray-800 dark:text-slate-200">{account.mobile_number ? formatPhone(account.mobile_number) : '—'}</dd>
                    </div>
                  </dl>
                  <div className="mt-3 pt-3 border-t border-gray-200 dark:border-slate-700">
                    <AccountRowActions
                      onView={() => setViewAccount(account)}
                      onRemove={() => setRemoveTarget(account)}
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
                    <th className={thClass}>Account holder</th>
                    <th className={thClass}>Account number</th>
                    <th className={thClass}>Bank</th>
                    <th className={thClass}>IFSC</th>
                    <th className={thClass}>Mobile</th>
                    <th className={actionThClass}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {contactAccounts.map((account, index) => (
                    <tr key={account.id} className="group">
                      <td className={tdClass}>{(accountPage - 1) * accountPageSize + index + 1}</td>
                      <td className={`${tdClass} font-medium text-gray-900 dark:text-slate-100`}>
                        {account.account_holder_name || account.beneficiary_name || '—'}
                      </td>
                      <td className={`${tdClass} font-mono`}>{account.account_number || '—'}</td>
                      <td className={tdClass}>
                        <span className="inline-flex items-center gap-2">
                          <FaBuilding size={14} className="text-gray-400 dark:text-slate-500" />
                          {account.bank_name || '—'}
                        </span>
                      </td>
                      <td className={`${tdClass} font-mono`}>{account.ifsc || '—'}</td>
                      <td className={tdClass}>{account.mobile_number ? formatPhone(account.mobile_number) : '—'}</td>
                      <td className={actionTdClass}>
                        <AccountRowActions
                          onView={() => setViewAccount(account)}
                          onRemove={() => setRemoveTarget(account)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </DataTableScroll>
            </>
          )}
          {!accountsLoading && (
            <BankAccountPager
              page={accountPage}
              pageSize={accountPageSize}
              totalCount={accountTotal}
              onPageChange={setAccountPage}
            />
          )}
        </Card>

        <BankAccountDetailsModal account={viewAccount} onClose={() => setViewAccount(null)} />
        <BankAccountConfirmModal
          account={removeTarget}
          title="Remove from this contact?"
          description="This takes the account off this contact only. The verified account stays saved, and it remains on any other contact it is already linked to."
          confirmLabel="Remove"
          loading={removing}
          onCancel={() => !removing && setRemoveTarget(null)}
          onConfirm={confirmRemoveAccount}
        />

        {showEditModal && selectedContact && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 overflow-y-auto">
            <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-md w-full p-6 my-auto max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Edit contact</h2>
                <button type="button" onClick={closeEditModal} className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors">
                  <FaX size={24} />
                </button>
              </div>
              <div className="space-y-4">
                <Input
                  label="Full name"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  placeholder="Full name"
                  icon={FaUser}
                  required
                  error={errors.name}
                />
                <Input
                  label="Email address"
                  type="email"
                  value={formData.email}
                  onChange={(e) => handleInputChange('email', e.target.value)}
                  placeholder="name@example.com"
                  icon={FaEnvelope}
                  required
                  error={errors.email}
                />
                <Input
                  label="Phone number"
                  type="tel"
                  value={formData.phone}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                    handleInputChange('phone', value);
                  }}
                  placeholder="10-digit mobile"
                  icon={FaPhone}
                  maxLength={10}
                  required
                  error={errors.phone}
                />
              </div>
              <div className="mt-6 flex gap-3">
                <Button onClick={closeEditModal} variant="outline" fullWidth type="button">
                  Cancel
                </Button>
                <Button onClick={handleSave} variant="primary" fullWidth loading={saving} disabled={saving} type="button">
                  Update contact
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 px-4 sm:px-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-slate-100">Contacts</h1>
          <p className="mt-1 text-sm sm:text-base text-gray-600 dark:text-slate-400">
            Click a contact to view and manage linked bank accounts
          </p>
        </div>
        <button
          type="button"
          onClick={handleAddNew}
          className="inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold text-white shadow-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition-colors"
        >
          <FaPlus className="shrink-0" size={18} />
          Add New Contact
        </button>
      </div>

      <Card padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100 mb-4">Filter</h3>
        <div className="grid grid-cols-1 items-end gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <FilterField label="Name">
            <input
              type="text"
              value={filterDraft.name}
              onChange={(e) => setFilterDraft({ ...filterDraft, name: e.target.value })}
              placeholder="Name"
              className={filterInputClass}
            />
          </FilterField>
          <FilterField label="Email">
            <input
              type="text"
              value={filterDraft.email}
              onChange={(e) => setFilterDraft({ ...filterDraft, email: e.target.value })}
              placeholder="Email"
              className={filterInputClass}
            />
          </FilterField>
          <FilterField label="Phone">
            <input
              type="tel"
              value={filterDraft.phone}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                setFilterDraft({ ...filterDraft, phone: value });
              }}
              placeholder="10-digit phone"
              maxLength={10}
              className={filterInputClass}
            />
          </FilterField>
          <FilterActions onClear={clearFilters} onApply={applyFilters} />
        </div>
      </Card>

      <Card padding="lg">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-slate-100">Contact list</h3>
          {totalCount != null && !loading && (
            <p className="text-sm text-gray-500 dark:text-slate-400">
              {contacts.length} shown
              {typeof totalCount === 'number' && totalCount > contacts.length
                ? ` of ${totalCount} total`
                : typeof totalCount === 'number'
                  ? ` · ${totalCount} total`
                  : ''}
            </p>
          )}
        </div>
        {loadError && (
          <div className="mb-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-100 dark:border-red-900 text-red-700 dark:text-red-300 text-sm px-4 py-2">
            {loadError}
          </div>
        )}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
            <p className="mt-4 text-gray-600 dark:text-slate-400">Loading contacts...</p>
          </div>
        ) : contacts.length === 0 ? (
          <div className="text-center py-12 text-gray-500 dark:text-slate-400">
            <p className="text-lg">No contacts found</p>
            <p className="text-sm mt-2">Use &quot;Add New Contact&quot; or adjust filters.</p>
          </div>
        ) : (
          <>
          <div className="md:hidden space-y-3">
            {contacts.map((contact, index) => (
              <div key={contact.id} className="rounded-xl border border-gray-200 dark:border-slate-700 p-4">
                <button type="button" onClick={() => openContactDetail(contact)} className="w-full text-left">
                  <p className="text-xs text-gray-500 dark:text-slate-400">#{index + 1}</p>
                  <p className="text-base font-semibold text-gray-900 dark:text-slate-100">{contact.name}</p>
                  <p className="text-sm text-gray-600 dark:text-slate-400 mt-1 break-all">{contact.email || '—'}</p>
                  <p className="text-sm text-gray-600 dark:text-slate-400 mt-0.5">{contact.phone ? formatPhone(contact.phone) : '—'}</p>
                </button>
                <div className="mt-3 pt-3 border-t border-gray-200 dark:border-slate-700 flex flex-wrap gap-2">
                  <Button type="button" size="sm" variant="outline" icon={FaEye} iconPosition="left" onClick={() => openContactDetail(contact)}>
                    Accounts
                  </Button>
                  <Button type="button" size="sm" variant="outline" icon={FaPen} iconPosition="left" onClick={(e) => handleEdit(contact, e)}>
                    Edit
                  </Button>
                </div>
              </div>
            ))}
          </div>
          <DataTableScroll>
            <table className="w-max min-w-full border-separate border-spacing-0">
              <thead>
                <tr>
                  <th className={thClass}>S.No</th>
                  <th className={thClass}>Name</th>
                  <th className={thClass}>Email</th>
                  <th className={thClass}>Phone</th>
                  <th className={actionThClass}>Action</th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact, index) => (
                  <tr
                    key={contact.id}
                    onClick={() => openContactDetail(contact)}
                    className="group cursor-pointer"
                  >
                    <td className={tdClass}>{index + 1}</td>
                    <td className={`${tdClass} font-medium text-gray-900 dark:text-slate-100`}>{contact.name}</td>
                    <td className={tdClass}>{contact.email || '—'}</td>
                    <td className={tdClass}>{contact.phone ? formatPhone(contact.phone) : '—'}</td>
                    <td className={actionTdClass} onClick={(e) => e.stopPropagation()}>
                      <div className="inline-flex flex-nowrap items-center gap-1">
                        <button
                          type="button"
                          onClick={() => openContactDetail(contact)}
                          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-semibold text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-950/60"
                        >
                          <FaEye size={16} />
                          Accounts
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleEdit(contact, e)}
                          className="inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-semibold text-blue-600 hover:bg-blue-50 dark:text-blue-400 dark:hover:bg-blue-950/60"
                        >
                          <FaPen size={15} />
                          Edit
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </DataTableScroll>
          </>
        )}
      </Card>

      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 overflow-y-auto">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-md w-full p-6 my-auto max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Add New Contact</h2>
              <button type="button" onClick={closeAddModal} className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors">
                <FaX size={24} />
              </button>
            </div>

            <div className="space-y-4">
              <Input
                label="Full name"
                value={formData.name}
                onChange={(e) => handleInputChange('name', e.target.value)}
                placeholder="Full name"
                icon={FaUser}
                required
                error={errors.name}
              />
              <Input
                label="Email address"
                type="email"
                value={formData.email}
                onChange={(e) => handleInputChange('email', e.target.value)}
                placeholder="name@example.com"
                icon={FaEnvelope}
                required
                error={errors.email}
              />
              <Input
                label="Phone number (unique)"
                type="tel"
                value={formData.phone}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  handleInputChange('phone', value);
                }}
                placeholder="10-digit mobile"
                icon={FaPhone}
                maxLength={10}
                required
                error={errors.phone}
              />
            </div>

            <div className="mt-6 flex gap-3">
              <Button onClick={closeAddModal} variant="outline" fullWidth type="button">
                Cancel
              </Button>
              <Button onClick={handleSave} variant="primary" fullWidth loading={saving} disabled={saving} type="button">
                Save contact
              </Button>
            </div>
          </div>
        </div>
      )}

      {showEditModal && selectedContact && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 overflow-y-auto">
          <div className="bg-white dark:bg-slate-900 rounded-xl shadow-2xl max-w-md w-full p-6 my-auto max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Edit contact</h2>
              <button type="button" onClick={closeEditModal} className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors">
                <FaX size={24} />
              </button>
            </div>
            <p className="text-sm text-gray-500 dark:text-slate-400 mb-4">
              Update contact details. Phone must stay unique in your directory.
            </p>

            <div className="space-y-4">
              <Input
                label="Full name"
                value={formData.name}
                onChange={(e) => handleInputChange('name', e.target.value)}
                placeholder="Full name"
                icon={FaUser}
                required
                error={errors.name}
              />
              <Input
                label="Email address"
                type="email"
                value={formData.email}
                onChange={(e) => handleInputChange('email', e.target.value)}
                placeholder="name@example.com"
                icon={FaEnvelope}
                required
                error={errors.email}
              />
              <Input
                label="Phone number"
                type="tel"
                value={formData.phone}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  handleInputChange('phone', value);
                }}
                placeholder="10-digit mobile"
                icon={FaPhone}
                maxLength={10}
                required
                error={errors.phone}
              />
            </div>

            <div className="mt-6 flex gap-3">
              <Button onClick={closeEditModal} variant="outline" fullWidth type="button">
                Cancel
              </Button>
              <Button onClick={handleSave} variant="primary" fullWidth loading={saving} disabled={saving} type="button">
                Update contact
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Contacts;
