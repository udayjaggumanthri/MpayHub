import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { FaGear } from 'react-icons/fa6';
import { useAuth } from '../../context/AuthContext';
import { creatableRolesFor } from '../../utils/rolePermissions';
import UserList from './UserList';
import AddUser from './AddUser';

const UserManagement = () => {
  const { user } = useAuth();
  const [activeRole, setActiveRole] = useState('all');
  const [showAddUser, setShowAddUser] = useState(false);
  const [targetRole, setTargetRole] = useState('');
  const isAdmin = user?.role === 'Admin';

  // Get available roles based on current user's role
  const availableRoles = React.useMemo(() => {
    if (!user) return [];
    return creatableRolesFor(user.role);
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
      <div className="overflow-hidden rounded-2xl border border-slate-200/90 dark:border-slate-700/90 bg-white dark:bg-slate-900 shadow-sm ring-1 ring-slate-900/5">
        <div className="relative border-b border-slate-100 dark:border-slate-800 bg-gradient-to-r from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-indigo-50/40 dark:to-indigo-950/40 px-6 py-8 sm:px-8">
          <div className="absolute inset-y-0 right-0 w-1/3 max-w-md bg-gradient-to-l from-indigo-100/30 dark:from-indigo-900/40 to-transparent pointer-events-none" />
          <div className="relative flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600 dark:text-indigo-400">Directory</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-3xl">User management</h1>
              <p className="mt-2 max-w-xl text-sm text-slate-600 dark:text-slate-400">
                Onboard hierarchy users, review KYC readiness, and control account access (admin).
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-3">
              {isAdmin ? (
                <Link
                  to="/admin/user-management-settings"
                  className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-300 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 dark:hover:bg-indigo-950/60 hover:text-indigo-800 dark:hover:text-indigo-200 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  <FaGear size={14} />
                  Session settings
                </Link>
              ) : null}
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
                    : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
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
                      : 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700'
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
              activeRole !== 'all' && availableRoles.includes(activeRole)
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
