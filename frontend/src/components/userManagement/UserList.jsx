import React, { useState, useEffect, useCallback } from 'react';
import { usersAPI } from '../../services/api';
import { formatUserId } from '../../utils/formatters';
import Card from '../common/Card';
import { FaMagnifyingGlass, FaPlus, FaEye, FaBuilding, FaPhone, FaEnvelope } from 'react-icons/fa6';
import Button from '../common/Button';

const UserList = ({ role, onCreateNew, currentUserId }) => {
  const [users, setUsers] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [loading, setLoading] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [showDetailsModal, setShowDetailsModal] = useState(false);

  const loadUsers = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch users from API
      const params = role && role !== 'all' ? { role } : {};
      const result = await usersAPI.listUsers(params);
      
      if (result.success && result.data?.users) {
        // Filter users based on search term
        const filtered = result.data.users.filter((u) => {
          const searchLower = searchTerm.toLowerCase();
          const firstName = (u.first_name || '').toLowerCase();
          const lastName = (u.last_name || '').toLowerCase();
          const fullName = `${firstName} ${lastName}`.trim();
          const userId = (u.user_id || '').toLowerCase();
          const phone = (u.phone || '').toLowerCase();
          const email = (u.email || '').toLowerCase();
          const businessName = (u.profile?.business_name || '').toLowerCase();
          
          return (
            fullName.includes(searchLower) ||
            userId.includes(searchLower) ||
            phone.includes(searchTerm) ||
            email.includes(searchLower) ||
            businessName.includes(searchLower)
          );
        });
        setUsers(filtered);
      } else {
        setUsers([]);
        console.error('Error loading users:', result.message);
      }
    } catch (error) {
      console.error('Error loading users:', error);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [role, searchTerm]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const handleViewDetails = (user) => {
    setSelectedUser(user);
    setShowDetailsModal(true);
  };

  const closeDetailsModal = () => {
    setShowDetailsModal(false);
    setSelectedUser(null);
  };

  return (
    <div className="space-y-4">
      {/* Search and Add Button */}
      <div className="flex flex-col sm:flex-row gap-4 items-center justify-between">
        <div className="relative flex-1 w-full sm:max-w-md">
          <FaMagnifyingGlass className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search users by name, ID, phone, business, or email..."
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>
        {onCreateNew && (
          <Button
            onClick={onCreateNew}
            variant="primary"
            icon={FaPlus}
            iconPosition="left"
          >
            Add {role || 'User'}
          </Button>
        )}
      </div>

      {/* Users Table */}
      {loading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading users...</p>
        </div>
      ) : users.length === 0 ? (
        <div className="text-center py-12 text-gray-500">
          {searchTerm ? 'No users found matching your search' : `No ${role || 'users'} found`}
        </div>
      ) : (
        <Card padding="lg">
          <div className="overflow-x-auto">
            <table className="w-full border-collapse">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">User ID</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Business</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Phone</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Email</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Role</th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">Action</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => {
                  const userId = user.user_id || user.id;
                  const fullName = `${user.first_name || ''} ${user.last_name || ''}`.trim() || 'N/A';
                  const businessName = user.profile?.business_name || 'N/A';
                  
                  return (
                    <tr key={user.id || userId} className="border-b border-gray-200 hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 text-sm text-gray-900 font-medium">
                        <span className="text-blue-600">{formatUserId(userId)}</span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">{fullName}</td>
                      <td className="px-4 py-3 text-sm text-gray-700">
                        {businessName}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-700">{user.phone || 'N/A'}</td>
                      <td className="px-4 py-3 text-sm text-gray-700">{user.email || 'N/A'}</td>
                      <td className="px-4 py-3 text-sm">
                        <span className="px-3 py-1 rounded-full text-xs font-semibold bg-blue-100 text-blue-800 border border-blue-200">
                          {user.role}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-center">
                        <button
                          onClick={() => handleViewDetails(user)}
                          className="text-blue-600 hover:text-blue-800 transition-colors p-1 rounded hover:bg-blue-50"
                          title="View Details"
                        >
                          <FaEye size={18} />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* User Details Modal */}
      {showDetailsModal && selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-6 my-auto max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-2xl font-bold text-gray-900">User Details</h2>
              <button
                onClick={closeDetailsModal}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <span className="text-2xl">&times;</span>
              </button>
            </div>

            <div className="space-y-6">
              {/* User ID and Role */}
              <div className="bg-blue-50 rounded-lg p-4 border border-blue-200">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-gray-500 uppercase mb-1">User ID</p>
                    <p className="text-xl font-bold text-blue-600">{formatUserId(selectedUser.user_id || selectedUser.id)}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-500 uppercase mb-1">Role</p>
                    <span className="px-3 py-1 rounded-full text-sm font-semibold bg-blue-100 text-blue-800 border border-blue-200">
                      {selectedUser.role}
                    </span>
                  </div>
                </div>
              </div>

              {/* Personal Information */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                  Personal Information
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="text-xs text-gray-500 uppercase">Full Name</label>
                    <p className="text-sm font-medium text-gray-900 mt-1">
                      {`${selectedUser.first_name || ''} ${selectedUser.last_name || ''}`.trim() || 'N/A'}
                    </p>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase">Email Address</label>
                    <p className="text-sm font-medium text-gray-900 mt-1 flex items-center space-x-1">
                      <FaEnvelope size={14} className="text-gray-400" />
                      <span>{selectedUser.email || 'N/A'}</span>
                    </p>
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 uppercase">Primary Mobile</label>
                    <p className="text-sm font-medium text-gray-900 mt-1 flex items-center space-x-1">
                      <FaPhone size={14} className="text-gray-400" />
                      <span>{selectedUser.phone || 'N/A'}</span>
                    </p>
                  </div>
                  {(selectedUser.profile?.alternate_phone || selectedUser.alternatePhone) && (
                    <div>
                      <label className="text-xs text-gray-500 uppercase">Alternate Mobile</label>
                      <p className="text-sm font-medium text-gray-900 mt-1 flex items-center space-x-1">
                        <FaPhone size={14} className="text-gray-400" />
                        <span>{selectedUser.profile?.alternate_phone || selectedUser.alternatePhone}</span>
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* Business Information */}
              <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                  Business Information
                </h3>
                <div className="space-y-3">
                  <div>
                    <label className="text-xs text-gray-500 uppercase">Business Name</label>
                    <p className="text-sm font-medium text-gray-900 mt-1 flex items-center space-x-1">
                      <FaBuilding size={14} className="text-gray-400" />
                      <span>{selectedUser.profile?.business_name || selectedUser.businessName || 'N/A'}</span>
                    </p>
                  </div>
                  {(selectedUser.profile?.business_address || selectedUser.businessAddress) && (
                    <div>
                      <label className="text-xs text-gray-500 uppercase">Business Address</label>
                      <p className="text-sm text-gray-900 mt-1">
                        {selectedUser.profile?.business_address || selectedUser.businessAddress}
                      </p>
                    </div>
                  )}
                </div>
              </div>

              {/* KYC Information */}
              {(selectedUser.kyc?.pan_number || selectedUser.kyc?.aadhaar_number || selectedUser.pan || selectedUser.aadhaar) && (
                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <h3 className="text-sm font-semibold text-gray-700 mb-3 uppercase tracking-wide">
                    KYC Information
                  </h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {(selectedUser.kyc?.pan_number || selectedUser.pan) && (
                      <div>
                        <label className="text-xs text-gray-500 uppercase">PAN Number</label>
                        <p className="text-sm font-medium text-gray-900 mt-1 font-mono">
                          {selectedUser.kyc?.pan_number || selectedUser.pan}
                          {(selectedUser.kyc?.pan_verified || selectedUser.panVerified) && (
                            <span className="ml-2 text-green-600">✓ Verified</span>
                          )}
                        </p>
                      </div>
                    )}
                    {(selectedUser.kyc?.aadhaar_number || selectedUser.aadhaar) && (
                      <div>
                        <label className="text-xs text-gray-500 uppercase">Aadhaar Number</label>
                        <p className="text-sm font-medium text-gray-900 mt-1 font-mono">
                          {(() => {
                            const aadhaar = selectedUser.kyc?.aadhaar_number || selectedUser.aadhaar;
                            return aadhaar ? `${aadhaar.substring(0, 4)} **** ${aadhaar.substring(8)}` : 'N/A';
                          })()}
                          {(selectedUser.kyc?.aadhaar_verified || selectedUser.aadhaarVerified) && (
                            <span className="ml-2 text-green-600">✓ Verified</span>
                          )}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Created Date */}
              {(selectedUser.created_at || selectedUser.createdAt) && (
                <div className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                  <label className="text-xs text-gray-500 uppercase">Created On</label>
                  <p className="text-sm font-medium text-gray-900 mt-1">
                    {new Date(selectedUser.created_at || selectedUser.createdAt).toLocaleString()}
                  </p>
                </div>
              )}
            </div>

            <div className="mt-6 flex justify-end">
              <Button onClick={closeDetailsModal} variant="primary">
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UserList;
