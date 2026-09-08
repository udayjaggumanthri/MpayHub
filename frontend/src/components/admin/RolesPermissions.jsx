import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FaRotate } from 'react-icons/fa6';
import { adminAPI } from '../../services/api';
import Button from '../common/Button';
import Card from '../common/Card';
import { isSuperAdminUser } from '../../utils/rolePermissions';
import { useAuth } from '../../context/AuthContext';

const RolesPermissions = () => {
  const { user } = useAuth();
  const canEdit = isSuperAdminUser(user);
  const [roles, setRoles] = useState([]);
  const [modules, setModules] = useState([]);
  const [permissions, setPermissions] = useState({});
  const [selectedRole, setSelectedRole] = useState('Admin');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const apply = useCallback((data) => {
    setRoles(data.roles || []);
    setModules(data.modules || []);
    setPermissions(data.permissions || {});
    setSelectedRole((prev) => {
      if (prev && (data.roles || []).includes(prev)) return prev;
      return (data.roles || [])[0] || 'Admin';
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await adminAPI.getRolesPermissions();
    if (res.success && res.data) {
      apply(res.data);
    } else {
      setError(res.message || 'Could not load permissions matrix');
    }
    setLoading(false);
  }, [apply]);

  useEffect(() => {
    load();
  }, [load]);

  const rolePerms = useMemo(() => permissions[selectedRole] || {}, [permissions, selectedRole]);

  const toggle = async (moduleCode, nextEnabled) => {
    if (!canEdit) return;
    setSaving(true);
    setError('');
    setSuccess('');
    const res = await adminAPI.updateRolePermission({
      role: selectedRole,
      module_code: moduleCode,
      enabled: nextEnabled,
    });
    if (res.success && res.data) {
      apply(res.data);
      setSuccess(`Updated ${selectedRole} / ${moduleCode}`);
    } else {
      setError(res.message || 'Update failed');
    }
    setSaving(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">
            Roles &amp; permissions
          </h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400 max-w-2xl">
            Enable or disable portal modules per role. Super Admin always has full access.
            {!canEdit ? ' You can view this matrix; only Super Admin can edit.' : null}
          </p>
        </div>
        <Button type="button" variant="secondary" onClick={load} disabled={loading || saving}>
          <FaRotate className="mr-2 inline" />
          Refresh
        </Button>
      </div>

      {error ? (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      ) : null}
      {success ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {success}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        <Card>
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">Roles</h2>
          <div className="space-y-1">
            {roles.map((role) => (
              <button
                key={role}
                type="button"
                onClick={() => setSelectedRole(role)}
                className={`w-full text-left rounded-md px-3 py-2 text-sm ${
                  selectedRole === role
                    ? 'bg-indigo-600 text-white'
                    : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-200'
                }`}
              >
                {role}
              </button>
            ))}
          </div>
        </Card>

        <Card>
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100 mb-3">
            Modules for {selectedRole}
          </h2>
          {loading ? (
            <p className="text-sm text-slate-500">Loading…</p>
          ) : (
            <div className="divide-y divide-slate-200 dark:divide-slate-700">
              {modules.map((mod) => {
                const enabled = Boolean(rolePerms[mod.code]);
                const lockedSuper = selectedRole === 'Super Admin';
                return (
                  <label
                    key={mod.code}
                    className="flex items-center justify-between gap-3 py-3 cursor-pointer"
                  >
                    <span>
                      <span className="block text-sm font-medium text-slate-900 dark:text-white">
                        {mod.name}
                      </span>
                      <span className="block text-xs text-slate-500">
                        {mod.code}
                        {mod.group ? ` · ${mod.group}` : ''}
                      </span>
                    </span>
                    <input
                      type="checkbox"
                      className="h-4 w-4"
                      checked={lockedSuper ? true : enabled}
                      disabled={!canEdit || lockedSuper || saving}
                      onChange={(e) => toggle(mod.code, e.target.checked)}
                    />
                  </label>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
};

export default RolesPermissions;
