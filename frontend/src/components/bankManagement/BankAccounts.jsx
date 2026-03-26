import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { bankAccountsAPI } from '../../services/api';
import { formatAccountNumber } from '../../utils/formatters';
import Card from '../common/Card';
import Button from '../common/Button';
import Input from '../common/Input';
import { 
  FaPlus, 
  FaMagnifyingGlass, 
  FaTrash,
  FaUser,
  FaPhone,
  FaBuilding,
  FaCreditCard
} from 'react-icons/fa6';
import AddBankAccount from './AddBankAccount';

const BankAccounts = () => {
  const { user } = useAuth();
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [filters, setFilters] = useState({
    name: '',
    phone: '',
    bankName: '',
    accountNumber: '',
    ifsc: '',
  });

  const loadAccounts = useCallback(async () => {
    if (!user) return;

    setLoading(true);
    try {
      const result = await bankAccountsAPI.listBankAccounts();
      if (result.success && result.data?.bank_accounts) {
        let filtered = result.data.bank_accounts || [];

        // Apply filters
        if (filters.name) {
          filtered = filtered.filter((acc) =>
            (acc.account_holder_name?.toLowerCase().includes(filters.name.toLowerCase())) ||
            (acc.beneficiary_name?.toLowerCase().includes(filters.name.toLowerCase())) ||
            (acc.contact?.name?.toLowerCase().includes(filters.name.toLowerCase()))
          );
        }

        if (filters.phone) {
          filtered = filtered.filter((acc) => 
            acc.contact?.phone?.includes(filters.phone) || 
            acc.phone?.includes(filters.phone)
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

  const handleDelete = async (accountId) => {
    if (window.confirm('Are you sure you want to delete this bank account?')) {
      try {
        const result = await bankAccountsAPI.deleteBankAccount(accountId);
        if (result.success) {
          loadAccounts();
        } else {
          const errorMsg = result.errors?.join(', ') || result.message || 'Failed to delete bank account';
          alert(errorMsg);
        }
      } catch (error) {
        console.error('Error deleting bank account:', error);
        alert('An error occurred. Please try again.');
      }
    }
  };

  const handleFilter = () => {
    loadAccounts();
  };

  const clearFilters = () => {
    setFilters({ name: '', phone: '', bankName: '', accountNumber: '', ifsc: '' });
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
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">All Bank Accounts</h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600">
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

      {/* Filter Section */}
      <Card padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Filter</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
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

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Bank Name</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="text"
                value={filters.bankName}
                onChange={(e) => setFilters({ ...filters, bankName: e.target.value })}
                placeholder="Enter Bank name"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Account Number</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="text"
                value={filters.accountNumber}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '');
                  setFilters({ ...filters, accountNumber: value });
                }}
                placeholder="Enter Account Number"
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">IFSC CODE</label>
            <div className="relative">
              <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
              <input
                type="text"
                value={filters.ifsc}
                onChange={(e) => {
                  const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 11);
                  setFilters({ ...filters, ifsc: value });
                }}
                placeholder="Enter IFSC Code"
                maxLength={11}
                className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent uppercase"
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

      {/* Accounts List */}
      <Card padding="lg">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">All Links</h3>
        {loading ? (
          <div className="text-center py-12">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Loading bank accounts...</p>
          </div>
        ) : accounts.length === 0 ? (
          <div className="text-center py-12 text-gray-500">
            <p className="text-lg">No bank accounts found</p>
            <p className="text-sm mt-2">Click "Create Account" to add a new bank account</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    CONTACT NAME
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    PHONE
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ACCOUNT HOLDER NAME
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ACCOUNT NUMBER
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    BANK NAME
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    IFSC
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ACTIONS
                  </th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account, index) => {
                  const contactName = account.contact?.name || 'N/A';
                  const contactPhone = account.contact?.phone || account.phone || 'N/A';
                  const accountHolderName = account.account_holder_name || account.beneficiary_name || 'N/A';
                  const accountNumber = account.account_number || 'N/A';
                  const bankName = account.bank_name || 'N/A';
                  const ifsc = account.ifsc || 'N/A';
                  
                  return (
                    <tr key={account.id} className="border-b border-gray-200 hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-900">
                        {index + 1}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        <div className="flex items-center space-x-2">
                          <FaUser size={14} className="text-gray-400" />
                          <span>{contactName}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700">
                        <div className="flex items-center space-x-2">
                          <FaPhone size={14} className="text-gray-400" />
                          <span>{contactPhone}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                        {accountHolderName}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700 font-mono">
                        {formatAccountNumber(accountNumber)}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700">
                        <div className="flex items-center space-x-2">
                          <FaBuilding size={14} className="text-gray-400" />
                          <span>{bankName}</span>
                        </div>
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-sm text-gray-700 font-mono">
                        {ifsc}
                      </td>
                      <td className="px-4 py-4 whitespace-nowrap text-center">
                        <button
                          onClick={() => handleDelete(account.id)}
                          className="text-red-600 hover:text-red-800 transition-colors p-1 rounded hover:bg-red-50"
                          title="Delete Account"
                        >
                          <FaTrash size={18} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
};

export default BankAccounts;
