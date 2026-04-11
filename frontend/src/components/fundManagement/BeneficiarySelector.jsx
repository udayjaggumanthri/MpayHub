import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { contactsAPI } from '../../services/api';
import { contactsFromListResult, mapContactRow } from '../../utils/contactsHelpers';

const BeneficiarySelector = ({ onSelect, selectedBeneficiary }) => {
  const { user } = useAuth();
  const [contacts, setContacts] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);
  const [loading, setLoading] = useState(false);

  const loadContacts = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const result = await contactsAPI.listContacts({ page_size: 500 });
      const { contacts: rows } = contactsFromListResult(result);
      if (result.success) {
        setContacts(rows.map((r) => mapContactRow(r)).filter(Boolean));
      } else {
        setContacts([]);
      }
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    loadContacts();
  }, [loadContacts]);

  const term = (searchTerm || '').trim().toLowerCase();
  const filteredContacts =
    !term && !showDropdown
      ? []
      : contacts.filter((contact) => {
          if (!term) return true;
          const digits = searchTerm.replace(/\D/g, '');
          return (
            contact.name.toLowerCase().includes(term) ||
            (contact.email || '').toLowerCase().includes(term) ||
            contact.phone.includes(digits) ||
            contact.phone.includes(searchTerm.trim())
          );
        });

  const handleSelect = (contact) => {
    onSelect(contact);
    setShowDropdown(false);
    setSearchTerm(contact.name);
  };

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Search beneficiary
      </label>
      <input
        type="text"
        value={searchTerm}
        onChange={(e) => {
          setSearchTerm(e.target.value);
          setShowDropdown(true);
        }}
        onFocus={() => {
          setShowDropdown(true);
        }}
        placeholder="Type name or phone (from your Contacts)"
        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />
      {loading && (
        <p className="text-xs text-gray-500 mt-1">Loading your contacts…</p>
      )}

      {showDropdown && (term || contacts.length > 0) && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setShowDropdown(false)}
          ></div>
          <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
            {filteredContacts.length === 0 ? (
              <div className="px-4 py-3 text-sm text-gray-500">
                {contacts.length === 0
                  ? 'No contacts yet. Add them under User Management → Contacts.'
                  : 'No matches. Try another name or phone.'}
              </div>
            ) : (
              filteredContacts.map((contact) => (
                <button
                  key={contact.id}
                  type="button"
                  onClick={() => handleSelect(contact)}
                  className="w-full px-4 py-3 text-left hover:bg-gray-100 transition-colors border-b border-gray-100 last:border-0"
                >
                  <p className="font-medium text-gray-900">{contact.name}</p>
                  <p className="text-sm text-gray-500">{contact.phone}</p>
                  {contact.email ? (
                    <p className="text-xs text-gray-400 mt-0.5">{contact.email}</p>
                  ) : null}
                  {contact.contactRoleLabel ? (
                    <p className="text-xs text-blue-600 mt-0.5">{contact.contactRoleLabel}</p>
                  ) : null}
                </button>
              ))
            )}
          </div>
        </>
      )}

      {selectedBeneficiary && (
        <div className="mt-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-gray-600">Selected beneficiary</p>
          <p className="font-semibold text-gray-900">{selectedBeneficiary.name}</p>
          <p className="text-sm text-gray-600">{selectedBeneficiary.phone}</p>
          {selectedBeneficiary.email ? (
            <p className="text-sm text-gray-600">{selectedBeneficiary.email}</p>
          ) : null}
          {selectedBeneficiary.contactRoleLabel ? (
            <p className="text-xs text-blue-700 mt-1">{selectedBeneficiary.contactRoleLabel}</p>
          ) : null}
        </div>
      )}
    </div>
  );
};

export default BeneficiarySelector;
