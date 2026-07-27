import React from 'react';
import { Link } from 'react-router-dom';
import { FaUser, FaChevronRight } from 'react-icons/fa6';
import Card from '../common/Card';
import { formatUserId } from '../../utils/formatters';

const roleBadgeClass = (role) => {
  const r = role || '';
  const map = {
    Admin: 'bg-violet-100 text-violet-900 ring-1 ring-violet-200',
    'Super Distributor': 'bg-sky-100 text-sky-900 ring-1 ring-sky-200',
    'Master Distributor': 'bg-cyan-100 text-cyan-900 ring-1 ring-cyan-200',
    Distributor: 'bg-indigo-100 text-indigo-900 ring-1 ring-indigo-200',
    Retailer: 'bg-slate-100 text-slate-800 ring-1 ring-slate-200',
  };
  return map[r] || 'bg-slate-100 text-slate-800 ring-1 ring-slate-200';
};

const PointOfContactCard = ({ pointOfContact }) => {
  const contacts = pointOfContact?.contacts || [];

  return (
    <Card>
      <div className="px-6 py-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-indigo-100 flex items-center justify-center">
            <FaUser className="text-indigo-600" size={18} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">Know Your Point of Contact</h2>
            <p className="text-sm text-slate-500">
              Immediate upline for this user — contact them for support or escalations.
            </p>
          </div>
        </div>
      </div>
      <div className="p-6">
        {contacts.length === 0 ? (
          <p className="text-sm text-slate-600 bg-slate-50 rounded-xl px-4 py-4 border border-slate-100">
            No point of contact is assigned in the hierarchy for this user.
          </p>
        ) : (
          <div className="space-y-3">
            {contacts.map((contact) => {
              const inner = (
                <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-indigo-100 bg-indigo-50/60 px-4 py-4">
                  <div className="space-y-1">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">User ID</p>
                    <p className="font-mono text-lg font-bold text-indigo-800">{formatUserId(contact)}</p>
                  </div>
                  <div className="space-y-1 min-w-[120px]">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Role</p>
                    <span className={`inline-flex text-xs font-semibold px-2.5 py-1 rounded-lg ${roleBadgeClass(contact.role)}`}>
                      {contact.role}
                    </span>
                  </div>
                  <div className="space-y-1 flex-1 min-w-[140px]">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Name</p>
                    <p className="text-slate-900 font-medium">{contact.name || '—'}</p>
                  </div>
                  {contact.linked_at && (
                    <div className="space-y-1">
                      <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Linked</p>
                      <p className="text-slate-600 text-sm">{new Date(contact.linked_at).toLocaleDateString()}</p>
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
