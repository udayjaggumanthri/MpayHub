import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { canCreateRole } from '../../utils/rolePermissions';
import UserList from './UserList';
import AddUser from './AddUser';

const UserManagement = () => {
  const { user } = useAuth();
  const [activeRole, setActiveRole] = useState('all');
  const [showAddUser, setShowAddUser] = useState(false);
  const [targetRole, setTargetRole] = useState('');

  // Get available roles based on current user's role
  const availableRoles = React.useMemo(() => {
    if (!user) return [];
    const roles = [];
    if (canCreateRole(user.role, 'Master Distributor')) roles.push('Master Distributor');
    if (canCreateRole(user.role, 'Distributor')) roles.push('Distributor');
    if (canCreateRole(user.role, 'Retailer')) roles.push('Retailer');
    return roles;
  }, [user]);

  const handleCreateNew = (role = null) => {
    if (role) {
      setTargetRole(role);
    } else {
      setTargetRole(activeRole === 'all' ? availableRoles[0] : activeRole);
    }
    setShowAddUser(true);
  };

  const handleUserCreated = (newUser) => {
    setShowAddUser(false);
    setActiveRole(newUser.role);
    // Reload the user list
    window.location.reload(); // In real app, this would be state update
  };

  if (showAddUser) {
    return (
      <AddUser
        onCancel={() => {
          setShowAddUser(false);
          setTargetRole('');
        }}
        onSuccess={handleUserCreated}
        initialRole={targetRole}
      />
    );
  }

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold text-gray-900">User Management</h1>
          {availableRoles.length > 0 && (
            <button
              onClick={() => handleCreateNew()}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Add New User
            </button>
          )}
        </div>

        {/* Role Tabs */}
        {user?.role === 'Admin' && (
          <div className="border-b border-gray-200 mb-6">
            <nav className="flex -mb-px space-x-4">
              <button
                onClick={() => setActiveRole('all')}
                className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeRole === 'all'
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                All Users
              </button>
              {availableRoles.map((role) => (
                <button
                  key={role}
                  onClick={() => setActiveRole(role)}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                    activeRole === role
                      ? 'border-blue-600 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {role}
                </button>
              ))}
            </nav>
          </div>
        )}

        {/* User List */}
        <UserList
          role={activeRole === 'all' ? undefined : activeRole}
          onCreateNew={
            activeRole !== 'all' && canCreateRole(user?.role, activeRole)
              ? () => handleCreateNew(activeRole)
              : null
          }
          currentUserId={user?.id}
        />
      </div>
    </div>
  );
};

export default UserManagement;
