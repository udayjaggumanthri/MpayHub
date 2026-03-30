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
  FaTrash
} from 'react-icons/fa6';

const Contacts = () => {
  const { user } = useAuth();
  const [contacts, setContacts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({
    name: '',
    email: '',
    phone: '',
  });
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [selectedContact, setSelectedContact] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
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
      const params = {
        ...filters,
        page_size: 100,
      };
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
  }, [user, filters]);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  const handleAddNew = () => {
    setFormData({ name: '', email: '', phone: '' });
    setErrors({});
    setSelectedContact(null);
    setShowAddModal(true);
  };

  const handleEdit = (contact) => {
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
      newErrors.name = 'Name must be at least 2 characters';
    }

    const emailTrim = (formData.email || '').trim();
    if (emailTrim) {
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

  const handleSave = async () => {
    if (!validateForm()) return;

    setSaving(true);
    try {
      const payload = {
        name: formData.name.trim(),
        email: (formData.email || '').trim() || null,
        phone: formData.phone.trim(),
      };
      if (selectedContact) {
        // Update existing contact
        const result = await contactsAPI.updateContact(selectedContact.id, payload);
        if (result.success) {
          await loadContacts();
          setShowEditModal(false);
          setSelectedContact(null);
        } else {
          const errorMsg = result.errors?.join(', ') || result.message || 'Failed to update contact';
          alert(errorMsg);
        }
      } else {
        // Add new contact
        const result = await contactsAPI.createContact(payload);
        if (result.success) {
          await loadContacts();
          setShowAddModal(false);
          setFormData({ name: '', email: '', phone: '' });
        } else {
          const errorMsg = result.errors?.join(', ') || result.message || 'Failed to add contact';
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

  const handleFilter = () => {
    loadContacts();
  };

  const clearFilters = () => {
    setFilters({ name: '', email: '', phone: '' });
  };

  const handleDelete = async (contact) => {
    if (!contact?.id) return;
    if (
      !window.confirm(
        `Delete contact "${contact.name}" (${contact.phone})? This cannot be undone.`
      )
    ) {
      return;
    }
    const result = await contactsAPI.deleteContact(contact.id);
    if (result.success) {
      await loadContacts();
    } else {
      alert(result.message || 'Failed to delete contact');
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 px-4 sm:px-0">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">All Contacts</h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600">
            Manage your contact directory for quick access
          </p>
        </div>
        <Button
          onClick={handleAddNew}
          variant="primary"
          icon={FaPlus}
          iconPosition="left"
          className="mt-4 sm:mt-0"
        >
          Add New Contact
        </Button>
      </div>

      {/* Filter Section */}
      <Card padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filter</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Name</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="text"
                value={filters.name}
                onChange={(e) => setFilters({ ...filters, name: e.target.value })}
                placeholder="Enter Name"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="email"
                value={filters.email}
                onChange={(e) => setFilters({ ...filters, email: e.target.value })}
                placeholder="Enter Email"
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
                value={filters.phone}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  setFilters({ ...filters, phone: value });
                }}
                placeholder="Enter Phone"
                maxLength={10}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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

      {/* Contacts List */}
      <Card padding="lg">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
          <h3 className="text-lg font-semibold text-gray-900">All Contacts</h3>
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
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading contacts...</p>
          </div>
        ) : contacts.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <p className="text-lg">No contacts found</p>
            <p className="text-sm mt-2">Click "Add New Contact" to get started</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
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
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ACTION
                  </th>
                </tr>
              </thead>
              <tbody>
                {contacts.map((contact, index) => (
                  <tr key={contact.id} className="border-b border-gray-200 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                      {index + 1}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {contact.name}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700">
                      {contact.email || '—'}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700">
                      {contact.phone}
                    </td>
                    <td className="px-4 py-4 whitespace-nowrap text-center">
                      <div className="inline-flex items-center justify-center gap-1">
                        <button
                          type="button"
                          onClick={() => handleEdit(contact)}
                          className="text-blue-600 hover:text-blue-800 transition-colors p-1 rounded hover:bg-blue-50"
                          title="Edit contact"
                        >
                          <FaPen size={18} />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDelete(contact)}
                          className="text-red-600 hover:text-red-800 transition-colors p-1 rounded hover:bg-red-50"
                          title="Delete contact"
                        >
                          <FaTrash size={18} />
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

      {/* Add Contact Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 my-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Add New Contact</h2>
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setFormData({ name: '', email: '', phone: '' });
                  setErrors({});
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <FaX size={24} />
              </button>
            </div>

            <div className="space-y-4">
              <Input
                label="Name"
                value={formData.name}
                onChange={(e) => handleInputChange('name', e.target.value)}
                placeholder="Enter full name"
                icon={FaUser}
                required
                error={errors.name}
              />

              <Input
                label="Email"
                type="email"
                value={formData.email}
                onChange={(e) => handleInputChange('email', e.target.value)}
                placeholder="Optional — enter email address"
                icon={FaEnvelope}
                error={errors.email}
              />

              <Input
                label="Phone Number"
                type="tel"
                value={formData.phone}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  handleInputChange('phone', value);
                }}
                placeholder="Enter 10-digit phone number"
                icon={FaPhone}
                maxLength={10}
                required
                error={errors.phone}
              />
            </div>

            <div className="mt-6 flex space-x-3">
              <Button
                onClick={() => {
                  setShowAddModal(false);
                  setFormData({ name: '', email: '', phone: '' });
                  setErrors({});
                }}
                variant="outline"
                fullWidth
              >
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                variant="primary"
                fullWidth
                loading={saving}
                disabled={saving}
              >
                Save Contact
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Contact Modal */}
      {showEditModal && selectedContact && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6 my-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">Edit Contact</h2>
              <button
                onClick={() => {
                  setShowEditModal(false);
                  setSelectedContact(null);
                  setFormData({ name: '', email: '', phone: '' });
                  setErrors({});
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <FaX size={24} />
              </button>
            </div>

            <div className="space-y-4">
              <Input
                label="Name"
                value={formData.name}
                onChange={(e) => handleInputChange('name', e.target.value)}
                placeholder="Enter full name"
                icon={FaUser}
                required
                error={errors.name}
              />

              <Input
                label="Email"
                type="email"
                value={formData.email}
                onChange={(e) => handleInputChange('email', e.target.value)}
                placeholder="Optional — enter email address"
                icon={FaEnvelope}
                error={errors.email}
              />

              <Input
                label="Phone Number"
                type="tel"
                value={formData.phone}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  handleInputChange('phone', value);
                }}
                placeholder="Enter 10-digit phone number"
                icon={FaPhone}
                maxLength={10}
                required
                error={errors.phone}
              />
            </div>

            <div className="mt-6 flex space-x-3">
              <Button
                onClick={() => {
                  setShowEditModal(false);
                  setSelectedContact(null);
                  setFormData({ name: '', email: '', phone: '' });
                  setErrors({});
                }}
                variant="outline"
                fullWidth
              >
                Cancel
              </Button>
              <Button
                onClick={handleSave}
                variant="primary"
                fullWidth
                loading={saving}
                disabled={saving}
              >
                Update Contact
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Contacts;
