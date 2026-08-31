import React from 'react';
import { Link } from 'react-router-dom';
import { FaUser, FaChevronRight } from 'react-icons/fa6';
import Card from '../common/Card';
import { formatUserId } from '../../utils/formatters';

const roleBadgeClass = (role) => {
  const r = role || '';
  const map = {
    Admin: 'bg-violet-100 dark:bg-violet-900/40 text-violet-900 dark:text-violet-300 ring-1 ring-violet-200 dark:ring-violet-800',
    'Super Distributor': 'bg-sky-100 dark:bg-sky-900/40 text-sky-900 dark:text-sky-300 ring-1 ring-sky-200 dark:ring-sky-800',
    'Master Distributor': 'bg-cyan-100 dark:bg-cyan-900/40 text-cyan-900 dark:text-cyan-300 ring-1 ring-cyan-200 dark:ring-cyan-800',
    Distributor: 'bg-indigo-100 dark:bg-indigo-900/40 text-indigo-900 dark:text-indigo-300 ring-1 ring-indigo-200 dark:ring-indigo-800',
    Retailer: 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 ring-1 ring-slate-200 dark:ring-slate-700',
  };
  return map[r] || 'bg-slate-100 dark:bg-slate-800 text-slate-800 dark:text-slate-200 ring-1 ring-slate-200 dark:ring-slate-700';
};

const PointOfContactCard = ({ pointOfContact }) => {
  const contacts = pointOfContact?.contacts || [];

  return (
    <Card>
      <div className="px-6 py-4 border-b border-slate-100 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-indigo-100 dark:bg-indigo-900/40 flex items-center justify-center">
            <FaUser className="text-indigo-600 dark:text-indigo-400" size={18} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Know Your Point of Contact</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Immediate upline for this user — contact them for support or escalations.
            </p>
          </div>
        </div>
      </div>
      <div className="p-6">
        {contacts.length === 0 ? (
          <p className="text-sm text-slate-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 rounded-xl px-4 py-4 border border-slate-100 dark:border-slate-800">
            No point of contact is assigned in the hierarchy for this user.
          </p>
        ) : (
          <div className="space-y-3">
            {contacts.map((contact) => {
              const inner = (
                <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-indigo-100 dark:border-indigo-900 bg-indigo-50/60 dark:bg-indigo-950/40 px-4 py-4">
                  <div className="space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">User ID</p>
                    <p className="font-mono text-lg font-bold text-indigo-800 dark:text-indigo-300">{formatUserId(contact)}</p>
                  </div>
                  <div className="space-y-1 min-w-[120px]">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Role</p>
                    <span className={`inline-flex text-xs font-semibold px-2.5 py-1 rounded-lg ${roleBadgeClass(contact.role)}`}>
                      {contact.role}
                    </span>
                  </div>
                  <div className="space-y-1 flex-1 min-w-[140px]">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Name</p>
                    <p className="text-slate-900 dark:text-slate-100 font-medium">{contact.name || '—'}</p>
                  </div>
                  {contact.linked_at && (
                    <div className="space-y-1">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Linked</p>
                      <p className="text-slate-600 dark:text-slate-400 text-sm">{new Date(contact.linked_at).toLocaleDateString()}</p>
                    </div>
                  )}
                  {contact.id != null && (
                    <FaChevronRight className="text-indigo-400 shrink-0" size={14} />
                  )}
                </div>
              );

              if (contact.id != null) {
                return (
                  <Link
                    key={contact.user_id}
                    to={`/user-management/users/${contact.id}`}
                    className="block transition-opacity hover:opacity-90"
                  >
                    {inner}
                  </Link>
                );
              }

              return <div key={contact.user_id}>{inner}</div>;
            })}
          </div>
        )}
      </div>
    </Card>
  );
};

export default PointOfContactCard;
