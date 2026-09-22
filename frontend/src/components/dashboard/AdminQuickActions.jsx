import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FiCheck,
  FiChevronRight,
  FiEdit2,
  FiMenu,
  FiPlus,
  FiRotateCcw,
  FiSettings,
  FiTrash2,
  FiX,
} from 'react-icons/fi';
import {
  ADMIN_QUICK_ICON_MAP,
  getAvailableToAdd,
  loadAdminQuickActionPrefs,
  resetAdminQuickActionPrefs,
  resolveAdminQuickActions,
  saveAdminQuickActionPrefs,
} from './adminDashboardCatalog';

const SECTION =
  'text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400';

function QuickActionTile({
  action,
  editing,
  dragOver,
  onDragStart,
  onDragOver,
  onDragLeave,
  onDrop,
  onDragEnd,
  onEdit,
  onRemove,
  onNavigate,
}) {
  const Icon = action.icon;
  return (
    <div
      draggable={editing}
      onDragStart={editing ? onDragStart : undefined}
      onDragOver={editing ? onDragOver : undefined}
      onDragLeave={editing ? onDragLeave : undefined}
      onDrop={editing ? onDrop : undefined}
      onDragEnd={editing ? onDragEnd : undefined}
      className={`group relative flex min-h-[88px] flex-col items-start gap-2 rounded-2xl border bg-white p-3 text-left shadow-sm transition dark:bg-slate-900 ${
        editing
          ? 'cursor-grab border-dashed border-indigo-300 active:cursor-grabbing dark:border-indigo-700'
          : 'border-slate-200/90 hover:border-slate-300 hover:shadow-md motion-safe:hover:-translate-y-0.5 dark:border-slate-700/90 dark:hover:border-slate-600'
      } ${dragOver ? 'border-indigo-500 bg-indigo-50/60 ring-2 ring-indigo-300/50 dark:bg-indigo-950/40' : ''}`}
    >
      {editing ? (
        <span className="absolute left-1.5 top-1.5 text-slate-400" aria-hidden>
          <FiMenu size={14} />
        </span>
      ) : null}

      {action.badge != null && !editing ? (
        <span className="absolute right-2 top-2 inline-flex min-w-[1.25rem] items-center justify-center rounded-full bg-amber-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
          {action.badge}
        </span>
      ) : null}

      {editing ? (
        <div className="absolute right-1.5 top-1.5 flex gap-1">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onEdit(action);
            }}
            className="rounded-md bg-white p-1 text-slate-500 shadow-sm ring-1 ring-slate-200 hover:text-indigo-600 dark:bg-slate-800 dark:ring-slate-600"
            aria-label={`Edit ${action.title}`}
          >
            <FiEdit2 size={12} />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onRemove(action.id);
            }}
            className="rounded-md bg-white p-1 text-slate-500 shadow-sm ring-1 ring-slate-200 hover:text-rose-600 dark:bg-slate-800 dark:ring-slate-600"
            aria-label={`Remove ${action.title}`}
          >
            <FiTrash2 size={12} />
          </button>
        </div>
      ) : null}

      <button
        type="button"
        disabled={editing}
        onClick={() => {
          if (!editing) onNavigate(action);
        }}
        className={`flex w-full flex-col items-start gap-2 text-left ${editing ? 'pointer-events-none pl-3 pt-1' : ''}`}
      >
        <span
          className={`inline-flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br text-white shadow-sm ${action.tone}`}
        >
          <Icon className="h-4.5 w-4.5" aria-hidden />
        </span>
        <span>
          <span className="block text-sm font-semibold text-slate-900 dark:text-slate-100">
            {action.title}
          </span>
          <span className="mt-0.5 block text-[11px] leading-snug text-slate-500 dark:text-slate-400">
            {action.description}
          </span>
        </span>
      </button>
    </div>
  );
}

/**
 * Configurable quick-actions grid for Admin / Super Admin.
 * Prefs persist per user in localStorage (order + label overrides).
 */
const AdminQuickActions = ({ user, qrStats, kycAwaiting = 0 }) => {
  const navigate = useNavigate();
  const userId = user?.id ?? user?.user_id ?? 'anon';

  const [prefs, setPrefs] = useState(() => loadAdminQuickActionPrefs(userId));
  const [editing, setEditing] = useState(false);
  const [dragId, setDragId] = useState(null);
  const [overId, setOverId] = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [editTarget, setEditTarget] = useState(null);
  const [editForm, setEditForm] = useState({ title: '', description: '' });

  useEffect(() => {
    setPrefs(loadAdminQuickActionPrefs(userId));
  }, [userId]);

  // Ensure KYC Approvals is available for users with older saved prefs.
  useEffect(() => {
    if (!prefs?.order || prefs.order.includes('kyc-approvals')) return;
    const next = {
      ...prefs,
      order: ['kyc-approvals', ...prefs.order.filter((id) => id !== 'platform')].slice(0, 12),
    };
    setPrefs(next);
    saveAdminQuickActionPrefs(userId, next);
  }, [prefs, userId]);

  const persist = useCallback(
    (next) => {
      setPrefs(next);
      saveAdminQuickActionPrefs(userId, next);
    },
    [userId]
  );

  const actions = useMemo(
    () => resolveAdminQuickActions({ navigate, qrStats, kycAwaiting, prefs }),
    [navigate, qrStats, kycAwaiting, prefs]
  );

  const available = useMemo(() => getAvailableToAdd(prefs), [prefs]);

  const reorder = (fromId, toId) => {
    if (!fromId || !toId || fromId === toId) return;
    const order = [...prefs.order];
    const fromIdx = order.indexOf(fromId);
    const toIdx = order.indexOf(toId);
    if (fromIdx < 0 || toIdx < 0) return;
    order.splice(fromIdx, 1);
    order.splice(toIdx, 0, fromId);
    persist({ ...prefs, order });
  };

  const removeAction = (id) => {
    persist({
      ...prefs,
      order: prefs.order.filter((x) => x !== id),
    });
  };

  const addAction = (id) => {
    if (prefs.order.includes(id)) return;
    persist({ ...prefs, order: [...prefs.order, id] });
    setAddOpen(false);
  };

  const openEdit = (action) => {
    setEditTarget(action);
    setEditForm({ title: action.title, description: action.description });
  };

  const saveEdit = () => {
    if (!editTarget) return;
    const title = editForm.title.trim();
    const description = editForm.description.trim();
    persist({
      ...prefs,
      overrides: {
        ...prefs.overrides,
        [editTarget.id]: {
          ...(title ? { title } : {}),
          ...(description ? { description } : {}),
        },
      },
    });
    setEditTarget(null);
  };

  const handleReset = () => {
    const next = resetAdminQuickActionPrefs(userId);
    setPrefs(next);
  };

  return (
    <section aria-labelledby="admin-quick-heading">
      <div className="mb-2.5 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h2 id="admin-quick-heading" className={SECTION}>
            Quick actions
          </h2>
          <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
            {editing
              ? 'Drag to reorder · edit labels · add or remove shortcuts'
              : 'Everything you need, one click away'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {editing ? (
            <>
              <button
                type="button"
                onClick={() => setAddOpen(true)}
                disabled={!available.length}
                className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1.5 text-xs font-semibold text-indigo-700 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-300"
              >
                <FiPlus size={13} />
                Add
              </button>
              <button
                type="button"
                onClick={handleReset}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
              >
                <FiRotateCcw size={12} />
                Reset
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditing(false);
                  setAddOpen(false);
                  setEditTarget(null);
                }}
                className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
              >
                <FiCheck size={13} />
                Done
              </button>
            </>
          ) : (
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-600 shadow-sm hover:border-indigo-200 hover:text-indigo-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-300"
              >
                <FiSettings size={13} />
                Customize
              </button>
          )}
        </div>
      </div>

      {actions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center dark:border-slate-700 dark:bg-slate-900/50">
          <p className="text-sm text-slate-600 dark:text-slate-300">No shortcuts pinned yet.</p>
          <button
            type="button"
            onClick={() => {
              setEditing(true);
              setAddOpen(true);
            }}
            className="mt-3 inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white"
          >
            <FiPlus size={14} />
            Add shortcuts
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
          {actions.map((action) => (
            <QuickActionTile
              key={action.id}
              action={action}
              editing={editing}
              dragOver={overId === action.id && dragId !== action.id}
              onDragStart={(e) => {
                setDragId(action.id);
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', action.id);
              }}
              onDragOver={(e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                if (overId !== action.id) setOverId(action.id);
              }}
              onDragLeave={() => {
                if (overId === action.id) setOverId(null);
              }}
              onDrop={(e) => {
                e.preventDefault();
                const from = e.dataTransfer.getData('text/plain') || dragId;
                reorder(from, action.id);
                setDragId(null);
                setOverId(null);
              }}
              onDragEnd={() => {
                setDragId(null);
                setOverId(null);
              }}
              onEdit={openEdit}
              onRemove={removeAction}
              onNavigate={(a) => a.onClick()}
            />
          ))}
          {editing ? (
            <button
              type="button"
              onClick={() => setAddOpen(true)}
              disabled={!available.length}
              className="flex min-h-[88px] flex-col items-center justify-center gap-1 rounded-2xl border border-dashed border-indigo-300 bg-indigo-50/40 text-indigo-700 transition hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-40 dark:border-indigo-800 dark:bg-indigo-950/30 dark:text-indigo-300"
            >
              <FiPlus size={20} />
              <span className="text-xs font-semibold">Add shortcut</span>
            </button>
          ) : null}
        </div>
      )}

      {/* Add picker */}
      {addOpen ? (
        <div
          className="fixed inset-0 z-[80] flex items-end justify-center bg-black/40 p-4 sm:items-center"
          role="presentation"
          onClick={() => setAddOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="qa-add-title"
            className="max-h-[80vh] w-full max-w-lg overflow-hidden rounded-2xl bg-white shadow-2xl dark:bg-slate-900"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3 dark:border-slate-800">
              <h3 id="qa-add-title" className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                Add shortcut
              </h3>
              <button
                type="button"
                onClick={() => setAddOpen(false)}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800"
                aria-label="Close"
              >
                <FiX size={18} />
              </button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto p-3">
              {available.length === 0 ? (
                <p className="px-2 py-8 text-center text-sm text-slate-500">
                  All available shortcuts are already pinned.
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {available.map((item) => {
                    const Icon = ADMIN_QUICK_ICON_MAP[item.iconKey] || FiPlus;
                    return (
                      <li key={item.id}>
                        <button
                          type="button"
                          onClick={() => addAction(item.id)}
                          className="flex w-full items-center gap-3 rounded-xl border border-slate-100 px-3 py-2.5 text-left transition hover:border-indigo-200 hover:bg-indigo-50/50 dark:border-slate-800 dark:hover:border-indigo-800 dark:hover:bg-indigo-950/40"
                        >
                          <span
                            className={`inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br text-white ${item.tone}`}
                          >
                            <Icon className="h-4 w-4" />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-sm font-semibold text-slate-800 dark:text-slate-100">
                              {item.title}
                            </span>
                            <span className="block truncate text-[11px] text-slate-500">
                              {item.description}
                            </span>
                          </span>
                          <FiPlus className="shrink-0 text-indigo-600" size={16} />
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          </div>
        </div>
      ) : null}

      {/* Edit labels */}
      {editTarget ? (
        <div
          className="fixed inset-0 z-[80] flex items-center justify-center bg-black/40 p-4"
          role="presentation"
          onClick={() => setEditTarget(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="qa-edit-title"
            className="w-full max-w-md rounded-2xl bg-white p-5 shadow-2xl dark:bg-slate-900"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 id="qa-edit-title" className="text-sm font-semibold text-slate-900 dark:text-slate-100">
              Edit shortcut
            </h3>
            <label className="mt-4 block text-xs font-semibold text-slate-600 dark:text-slate-400">
              Title
              <input
                type="text"
                value={editForm.title}
                onChange={(e) => setEditForm((f) => ({ ...f, title: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
                maxLength={40}
              />
            </label>
            <label className="mt-3 block text-xs font-semibold text-slate-600 dark:text-slate-400">
              Description
              <input
                type="text"
                value={editForm.description}
                onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-800"
                maxLength={80}
              />
            </label>
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditTarget(null)}
                className="rounded-lg px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={saveEdit}
                className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
};

export default AdminQuickActions;
