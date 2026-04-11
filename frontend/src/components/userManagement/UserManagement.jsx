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
    if (canCreateRole(user.role, 'Super Distributor')) roles.push('Super Distributor');
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
        initialRole={targetRole || ''}
      />
    );
  }

  return (
    <div className="min-h-[calc(100vh-6rem)] space-y-6">
      <div className="overflow-hidden rounded-2xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/5">
        <div className="relative border-b border-slate-100 bg-gradient-to-r from-slate-50 via-white to-indigo-50/40 px-6 py-8 sm:px-8">
          <div className="absolute inset-y-0 right-0 w-1/3 max-w-md bg-gradient-to-l from-indigo-100/30 to-transparent pointer-events-none" />
          <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">Directory</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">User management</h1>
              <p className="mt-2 max-w-xl text-sm text-slate-600">
                Onboard hierarchy users, review KYC readiness, and control account access (admin).
              </p>
            </div>
            {availableRoles.length > 0 && activeRole === 'all' && (
              <button
                type="button"
                onClick={() => handleCreateNew()}
                className="inline-flex shrink-0 items-center justify-center rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-md shadow-indigo-600/20 transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
              >
                Add new user
              </button>
            )}
          </div>
        </div>

        <div className="p-6 sm:p-8">
          {(user?.role === 'Admin' || user?.role === 'Super Distributor') && (
            <nav className="mb-8 flex flex-wrap gap-2" aria-label="Filter by role">
              <button
                type="button"
                onClick={() => setActiveRole('all')}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition-all ${
                  activeRole === 'all'
                    ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/25'
                    : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                }`}
              >
                All users
              </button>
              {availableRoles.map((r) => (
                <button
                  key={r}
                  type="button"
                  onClick={() => setActiveRole(r)}
                  className={`rounded-full px-4 py-2 text-sm font-semibold transition-all ${
                    activeRole === r
                      ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/25'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
                  }`}
                >
                  {r}
                </button>
              ))}
            </nav>
          )}

          <UserList
            role={activeRole === 'all' ? undefined : activeRole}
            onCreateNew={
              activeRole !== 'all' && canCreateRole(user?.role, activeRole)
                ? () => handleCreateNew(activeRole)
                : null
            }
            currentUserId={user?.id}
            isAdmin={user?.role === 'Admin'}
          />
        </div>
      </div>
    </div>
  );
};

export default UserManagement;
