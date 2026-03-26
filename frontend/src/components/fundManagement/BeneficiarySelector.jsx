import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { getContacts } from '../../services/mockData';

const BeneficiarySelector = ({ onSelect, selectedBeneficiary }) => {
  const { user } = useAuth();
  const [contacts, setContacts] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    if (user) {
      const result = getContacts(user.id);
      if (result.success) {
        setContacts(result.contacts || []);
      }
    }
  }, [user]);

  const filteredContacts = contacts.filter((contact) =>
    contact.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    contact.phone.includes(searchTerm)
  );

  const handleSelect = (contact) => {
    onSelect(contact);
    setShowDropdown(false);
    setSearchTerm(contact.name);
  };

  return (
    <div className="relative">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Search Beneficiary
      </label>
      <input
        type="text"
        value={searchTerm}
        onChange={(e) => {
          setSearchTerm(e.target.value);
          setShowDropdown(true);
        }}
        onFocus={() => setShowDropdown(true)}
        placeholder="Enter phone number or name"
        className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
      />

      {showDropdown && searchTerm && filteredContacts.length > 0 && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setShowDropdown(false)}
          ></div>
          <div className="absolute z-20 w-full mt-1 bg-white border border-gray-200 rounded-lg shadow-lg max-h-60 overflow-y-auto">
            {filteredContacts.map((contact) => (
              <button
                key={contact.id}
                onClick={() => handleSelect(contact)}
                className="w-full px-4 py-3 text-left hover:bg-gray-100 transition-colors border-b border-gray-100 last:border-0"
              >
                <p className="font-medium text-gray-900">{contact.name}</p>
                <p className="text-sm text-gray-500">{contact.phone}</p>
              </button>
            ))}
          </div>
        </>
      )}

      {selectedBeneficiary && (
        <div className="mt-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-gray-600">Selected Beneficiary:</p>
          <p className="font-semibold text-gray-900">{selectedBeneficiary.name}</p>
          <p className="text-sm text-gray-600">{selectedBeneficiary.phone}</p>
        </div>
      )}
    </div>
  );
};

export default BeneficiarySelector;
