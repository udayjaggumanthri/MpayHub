import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { contactsAPI } from '../../services/api';
import { validatePhone, validateEmail } from '../../utils/validators';
import { contactsFromListResult } from '../../utils/contactsHelpers';
import Card from '../common/Card';
import Button from '../common/Button';
import Input from '../common/Input';
import {
  FaMagnifyingGlass,
  FaPlus,
  FaPen,
  FaX,
  FaUser,
  FaEnvelope,
  FaPhone,
} from 'react-icons/fa6';

const EMPTY_FILTERS = { name: '', email: '', phone: '' };

const CONTACT_ROLE_OPTIONS = [
  { value: 'end_user', label: 'End-user' },
  { value: 'merchant', label: 'Merchant' },
  { value: 'dealer', label: 'Dealer' },
];

const Contacts = () => {
  const { user } = useAuth();
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filterDraft, setFilterDraft] = useState({ ...EMPTY_FILTERS });
  const [filterApplied, setFilterApplied] = useState({ ...EMPTY_FILTERS });
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedContact, setSelectedContact] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    contact_role: 'end_user',
  });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);
  const [totalCount, setTotalCount] = useState(null);
  const [loadError, setLoadError] = useState('');

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

  const handleAddNew = () => {
    setFormData({
      name: '',
      email: '',
      phone: '',
      contact_role: 'end_user',
    });
    setErrors({});
    setSelectedContact(null);
    setShowAddModal(true);
  };

  const handleEdit = (contact) => {
    setFormData({
      name: contact.name || '',
      email: contact.email || '',
      phone: contact.phone || '',
      contact_role: contact.contact_role || 'end_user',
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

    if (!formData.contact_role || !CONTACT_ROLE_OPTIONS.some((o) => o.value === formData.contact_role)) {
      newErrors.contact_role = 'Select a valid role';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validateForm()) return;

    setSaving(true);
    try {
      const payload = {
        name: formData.name.trim(),
        email: formData.email.trim(),
        phone: String(formData.phone || '').replace(/\D/g, '').slice(0, 10),
        contact_role: formData.contact_role,
      };
      if (selectedContact) {
        const result = await contactsAPI.updateContact(selectedContact.id, payload);
        if (result.success) {
          await loadContacts();
          setShowEditModal(false);
          setSelectedContact(null);
        } else {
          const errorMsg = formatApiErrors(result);
          alert(errorMsg);
        }
      } else {
        const result = await contactsAPI.createContact(payload);
        if (result.success) {
          await loadContacts();
          setShowAddModal(false);
          setFormData({
            name: '',
            email: '',
            phone: '',
            contact_role: 'end_user',
          });
        } else {
          const errorMsg = formatApiErrors(result);
          alert(errorMsg);
        }
      }
    } catch (error) {
      console.error('Error saving contact:', error);
      alert('An error occurred. Please try again.');
    } finally {
      setSaving(false);
    }
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
    setFormData({ name: '', email: '', phone: '', contact_role: 'end_user' });
    setErrors({});
  };

  const closeEditModal = () => {
    setShowEditModal(false);
    setSelectedContact(null);
    setFormData({ name: '', email: '', phone: '', contact_role: 'end_user' });
    setErrors({});
  };

  const RoleSelect = ({ idPrefix }) => (
    <div>
      <label htmlFor={`${idPrefix}-role`} className="block text-sm font-medium text-gray-700 mb-2">
        Contact role <span className="text-red-500">*</span>
      </label>
      <select
        id={`${idPrefix}-role`}
        value={formData.contact_role}
        onChange={(e) => handleInputChange('contact_role', e.target.value)}
        className="w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white text-gray-900"
      >
        {CONTACT_ROLE_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      {errors.contact_role && <p className="mt-1 text-sm text-red-600">{errors.contact_role}</p>}
      <p className="mt-1 text-xs text-gray-500">Tag as End-user, Merchant, or Dealer for your records.</p>
    </div>
  );

  return (
    <div className="max-w-7xl mx-auto space-y-6 px-4 sm:px-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Contacts</h1>
          <p className="mt-1 text-sm sm:text-base text-gray-600">
            Directory for pay-in and payout verification (phone is the unique key per account)
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
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filter</h3>
        <p className="text-sm text-gray-500 mb-4">
          Enter criteria and click <strong>Filter</strong> to run a server-side search.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Name</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="text"
                value={filterDraft.name}
                onChange={(e) => setFilterDraft({ ...filterDraft, name: e.target.value })}
                placeholder="Name"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="text"
                value={filterDraft.email}
                onChange={(e) => setFilterDraft({ ...filterDraft, email: e.target.value })}
                placeholder="Email"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Phone</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="tel"
                value={filterDraft.phone}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  setFilterDraft({ ...filterDraft, phone: value });
                }}
                placeholder="10-digit phone"
                maxLength={10}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
          <h3 className="text-lg font-semibold text-gray-900">Contact list</h3>
          {totalCount != null && !loading && (
            <p className="text-sm text-gray-500">
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
          <div className="mb-4 rounded-lg bg-red-50 border border-red-100 text-red-700 text-sm px-4 py-2">
            {loadError}
          </div>
        )}
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto" />
            <p className="mt-4 text-gray-600">Loading contacts...</p>
          </div>
        ) : contacts.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <p className="text-lg">No contacts found</p>
            <p className="text-sm mt-2">Use &quot;Add New Contact&quot; or adjust filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto -mx-4 sm:mx-0">
            <table className="w-full min-w-[640px] border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">
                    S.NO
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    NAME
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    EMAIL
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    PHONE
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-28">
                    ACTION
                  </th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact, index) => (
                  <tr key={contact.id} className="border-b border-gray-200 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-4 text-sm text-gray-900 tabular-nums">{index + 1}</td>
                    <td className="px-4 py-4 text-sm font-medium text-gray-900">{contact.name}</td>
                    <td className="px-4 py-4 text-sm text-gray-700 break-all max-w-[220px]">{contact.email}</td>
                    <td className="px-4 py-4 text-sm text-gray-700 tabular-nums">{contact.phone}</td>
                    <td className="px-4 py-4 text-center">
                      <button
                        type="button"
                        onClick={() => handleEdit(contact)}
                        className="inline-flex items-center justify-center text-blue-600 hover:text-blue-800 transition-colors p-2 rounded-lg hover:bg-blue-50"
                        title="Edit contact (name, email, phone, role)"
                        aria-label="Edit contact"
                      >
                        <FaPen size={18} />
                      </button>
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
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 my-auto max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Add New Contact</h2>
              <button type="button" onClick={closeAddModal} className="text-gray-400 hover:text-gray-600 transition-colors">
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
              <RoleSelect idPrefix="add" />
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
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 my-auto max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Edit contact</h2>
              <button type="button" onClick={closeEditModal} className="text-gray-400 hover:text-gray-600 transition-colors">
                <FaX size={24} />
              </button>
            </div>
            <p className="text-sm text-gray-500 mb-4">
              Update details or role. Phone must stay unique in your directory.
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
              <RoleSelect idPrefix="edit" />
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
