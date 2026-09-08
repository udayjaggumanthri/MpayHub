import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { FaGear } from 'react-icons/fa6';
import { useAuth } from '../../context/AuthContext';
import { creatableRolesFor, isAdminUser } from '../../utils/rolePermissions';
import UserList from './UserList';
import AddUser from './AddUser';

const UserManagement = () => {
  const { user } = useAuth();
  const [activeRole, setActiveRole] = useState('all');
  const [showAddUser, setShowAddUser] = useState(false);
  const [targetRole, setTargetRole] = useState('');
  const isOperator = isAdminUser(user);
  const showRoleFilters =
    isOperator || user?.role === 'Super Distributor' || user?.role === 'Master Distributor';

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
    window.location.reload();
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
    <div className="min-h-[calc(100vh-6rem)] space-y-4">
      <div className="overflow-hidden rounded-xl border border-slate-200/90 bg-white shadow-sm ring-1 ring-slate-900/5 dark:border-slate-700/90 dark:bg-slate-900">
        <div className="relative border-b border-slate-100 bg-gradient-to-r from-slate-50 via-white to-indigo-50/40 px-5 py-5 dark:border-slate-800 dark:from-slate-900 dark:via-slate-900 dark:to-indigo-950/40 sm:px-6">
          <div className="absolute inset-y-0 right-0 w-1/3 max-w-md bg-gradient-to-l from-indigo-100/30 to-transparent pointer-events-none dark:from-indigo-900/40" />
          <div className="relative flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600 dark:text-indigo-400">
                Directory
              </p>
              <h1 className="mt-0.5 text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100 sm:text-2xl">
                User management
              </h1>
              <p className="mt-1 max-w-xl text-sm text-slate-600 dark:text-slate-400">
                Onboard hierarchy users, review KYC readiness, and control account access.
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              {isOperator ? (
                <Link
                  to="/admin/user-management-settings"
                  className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 shadow-sm transition hover:border-indigo-200 hover:bg-indigo-50 hover:text-indigo-800 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-indigo-950/60 dark:hover:text-indigo-200"
                >
                  <FaGear size={14} />
                  Session settings
                </Link>
              ) : null}
              {availableRoles.length > 0 && activeRole === 'all' && (
                <button
                  type="button"
                  onClick={() => handleCreateNew()}
                  className="inline-flex shrink-0 items-center justify-center rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-indigo-600/20 transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  Add new user
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="p-4 sm:p-6">
          {showRoleFilters && availableRoles.length > 0 ? (
            <div className="mb-5">
              <label
                htmlFor="users-role-filter"
                className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400"
              >
                Filter by role
              </label>
              {/* Mobile: select */}
              <select
                id="users-role-filter"
                value={activeRole}
                onChange={(e) => setActiveRole(e.target.value)}
                className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-800 shadow-sm focus:border-indigo-300 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 md:hidden"
              >
                <option value="all">All users</option>
                {availableRoles.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              {/* Desktop: single horizontal scroll row */}
              <nav
                className="hidden md:flex md:flex-nowrap md:gap-1.5 md:overflow-x-auto md:pb-1"
                aria-label="Filter by role"
              >
                <button
                  type="button"
                  onClick={() => setActiveRole('all')}
                  className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                    activeRole === 'all'
                      ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/25'
                      : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
                  }`}
                >
                  All users
                </button>
                {availableRoles.map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setActiveRole(r)}
                    className={`shrink-0 whitespace-nowrap rounded-lg px-3 py-1.5 text-xs font-semibold transition-all ${
                      activeRole === r
                        ? 'bg-indigo-600 text-white shadow-sm shadow-indigo-600/25'
                        : 'bg-slate-100 text-slate-700 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
                    }`}
                  >
                    {r}
                  </button>
                ))}
              </nav>
            </div>
          ) : null}

          <UserList
            role={activeRole === 'all' ? undefined : activeRole}
            onRoleChange={setActiveRole}
            onCreateNew={
              activeRole !== 'all' && availableRoles.includes(activeRole)
                ? () => handleCreateNew(activeRole)
                : null
            }
            currentUserId={user?.id}
            isAdmin={isOperator}
            showRoleBreakdown={isOperator || user?.role === 'Super Distributor'}
          />
        </div>
      </div>
    </div>
  );
};

export default UserManagement;
