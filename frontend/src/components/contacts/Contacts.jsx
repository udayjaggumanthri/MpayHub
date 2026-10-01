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
import {
  FaMagnifyingGlass,
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
  const [showAddBank, setShowAddBank] = useState(false);

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
      const result = await bankAccountsAPI.listBankAccounts({ contact: contact.id });
      if (result.success) {
        const payload = result.data || {};
        const rows = payload.bank_accounts || payload.results || (Array.isArray(payload) ? payload : []);
        setContactAccounts(rows);
      } else {
        setContactAccounts([]);
        setAccountsError(result.message || 'Failed to load bank accounts');
      }
    } catch (error) {
      console.error('Error loading contact bank accounts:', error);
      setContactAccounts([]);
      setAccountsError('Failed to load bank accounts');
    } finally {
      setAccountsLoading(false);
    }
  }, []);

  const openContactDetail = (contact) => {
    setDetailContact(contact);
    setShowAddBank(false);
    setContactAccounts([]);
    loadContactAccounts(contact);
  };

  const closeContactDetail = () => {
    setDetailContact(null);
    setContactAccounts([]);
    setAccountsError('');
    setShowAddBank(false);
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
            <div className="overflow-x-auto -mx-4 sm:mx-0">
              <table className="w-full min-w-[640px] border-collapse">
                <thead>
                  <tr className="bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">#</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">Account holder</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">Account number</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">Bank</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">IFSC</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">Mobile</th>
                  </tr>
                </thead>
                <tbody>
                  {contactAccounts.map((account, index) => (
                    <tr key={account.id} className="border-b border-gray-200 dark:border-slate-700 hover:bg-gray-50 dark:hover:bg-slate-800 transition-colors">
                      <td className="px-4 py-4 text-sm text-gray-900 dark:text-slate-100">{index + 1}</td>
                      <td className="px-4 py-4 text-sm font-medium text-gray-900 dark:text-slate-100">
                        {account.account_holder_name || account.beneficiary_name || '—'}
                      </td>
                      <td className="px-4 py-4 text-sm font-mono text-gray-700 dark:text-slate-300">
                        {account.account_number || '—'}
                      </td>
                      <td className="px-4 py-4 text-sm text-gray-700 dark:text-slate-300">
                        <span className="inline-flex items-center gap-2">
                          <FaBuilding size={14} className="text-gray-400 dark:text-slate-500" />
                          {account.bank_name || '—'}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-sm font-mono text-gray-700 dark:text-slate-300">{account.ifsc || '—'}</td>
                      <td className="px-4 py-4 text-sm text-gray-700 dark:text-slate-300">
                        {account.mobile_number ? formatPhone(account.mobile_number) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

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
        <p className="text-sm text-gray-500 dark:text-slate-400 mb-4">
          Enter criteria and click <strong>Filter</strong> to run a server-side search.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">Name</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-slate-500" size={18} />
              <input
                type="text"
                value={filterDraft.name}
                onChange={(e) => setFilterDraft({ ...filterDraft, name: e.target.value })}
                placeholder="Name"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">Email</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-slate-500" size={18} />
              <input
                type="text"
                value={filterDraft.email}
                onChange={(e) => setFilterDraft({ ...filterDraft, email: e.target.value })}
                placeholder="Email"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">Phone</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 dark:text-slate-500" size={18} />
              <input
                type="tel"
                value={filterDraft.phone}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  setFilterDraft({ ...filterDraft, phone: value });
                }}
                placeholder="10-digit phone"
                maxLength={10}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap justify-end gap-3">
          <Button onClick={clearFilters} variant="outline" size="sm" type="button">
            Clear
          </Button>
          <Button onClick={applyFilters} variant="primary" size="sm" type="button">
            Filter
          </Button>
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
          <div className="overflow-x-auto -mx-4 sm:mx-0">
            <table className="w-full min-w-[640px] border-collapse">
              <thead>
                <tr className="bg-gray-50 dark:bg-slate-800/50 border-b border-gray-200 dark:border-slate-700">
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider w-16">
                    S.NO
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                    NAME
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                    EMAIL
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider">
                    PHONE
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 dark:text-slate-400 uppercase tracking-wider w-36">
                    ACTION
                  </th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact, index) => (
                  <tr
                    key={contact.id}
                    onClick={() => openContactDetail(contact)}
                    className="border-b border-gray-200 dark:border-slate-700 hover:bg-blue-50/60 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-4 text-sm text-gray-900 dark:text-slate-100 tabular-nums">{index + 1}</td>
                    <td className="px-4 py-4 text-sm font-medium text-gray-900 dark:text-slate-100">{contact.name}</td>
                    <td className="px-4 py-4 text-sm text-gray-700 dark:text-slate-300 break-all max-w-[220px]">{contact.email}</td>
                    <td className="px-4 py-4 text-sm text-gray-700 dark:text-slate-300 tabular-nums">{contact.phone}</td>
                    <td className="px-4 py-4 text-center" onClick={(e) => e.stopPropagation()}>
                      <div className="inline-flex items-center gap-1">
                        <button
                          type="button"
                          onClick={() => openContactDetail(contact)}
                          className="inline-flex items-center justify-center text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 transition-colors p-2 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-950/60"
                          title="View bank accounts"
                          aria-label="View bank accounts"
                        >
                          <FaEye size={18} />
                        </button>
                        <button
                          type="button"
                          onClick={(e) => handleEdit(contact, e)}
                          className="inline-flex items-center justify-center text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200 transition-colors p-2 rounded-lg hover:bg-blue-50 dark:hover:bg-blue-950/60"
                          title="Edit contact"
                          aria-label="Edit contact"
                        >
                          <FaPen size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
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
