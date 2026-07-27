import React from 'react';
import { Link } from 'react-router-dom';
import { FaChevronRight, FaSitemap } from 'react-icons/fa6';
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

const HierarchyCard = ({ lineage, user }) => {
  if (!lineage) return null;

  return (
    <Card>
      <div className="px-6 py-4 border-b border-slate-100">
        <div className="flex items-center gap-3">
          <div className="h-10 w-10 rounded-xl bg-cyan-100 flex items-center justify-center">
            <FaSitemap className="text-cyan-600" size={18} />
          </div>
          <div>
            <h2 className="text-lg font-bold text-slate-900">Hierarchy</h2>
            <p className="text-sm text-slate-500">
              Path: <code className="font-mono text-indigo-600">{lineage.map_path || '—'}</code>
            </p>
          </div>
        </div>
      </div>
      <div className="p-6 space-y-6">
        <div className="flex flex-wrap items-center gap-2">
          {(lineage.upline || []).map((node, idx) => (
            <React.Fragment key={`${node.id || node.display_code || node.user_id}-${idx}`}>
              {idx > 0 && <FaChevronRight className="text-slate-300" size={12} />}
              <div className="inline-flex flex-col items-center rounded-xl border border-slate-200 bg-slate-50 px-3 py-2">
                <span className="font-mono text-sm font-bold text-indigo-700">{formatUserId(node)}</span>
                <span className="text-[10px] uppercase text-slate-500 mt-0.5">{node.role}</span>
              </div>
            </React.Fragment>
          ))}
          {(lineage.upline || []).length > 0 && (
            <FaChevronRight className="text-slate-300" size={12} />
          )}
          <div className="inline-flex flex-col items-center rounded-xl border-2 border-indigo-400 bg-indigo-50 px-3 py-2">
            <span className="font-mono text-sm font-bold text-indigo-800">
              {formatUserId(user)}
            </span>
            <span className="text-[10px] uppercase text-indigo-600 mt-0.5">{user.role}</span>
          </div>
        </div>

        {(lineage.direct_parents || []).length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">Direct Parent</p>
            <div className="overflow-hidden rounded-xl border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-slate-500">User ID</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-slate-500">Role</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-slate-500">Name</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold uppercase text-slate-500">Linked</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {lineage.direct_parents.map((p) => (
                    <tr key={p.id || p.display_code || p.user_id} className="bg-white">
                      <td className="px-4 py-3 font-mono text-indigo-700 font-medium">{formatUserId(p)}</td>
                      <td className="px-4 py-3 text-slate-700">{p.role}</td>
                      <td className="px-4 py-3 text-slate-900">{p.name}</td>
                      <td className="px-4 py-3 text-slate-500 text-xs">
                        {p.linked_at ? new Date(p.linked_at).toLocaleDateString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {lineage.direct_reports_total > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-600 mb-3">
              Direct Reports ({lineage.direct_reports_total})
            </p>
            <div className="max-h-48 overflow-y-auto rounded-xl border border-slate-200 bg-white">
              <div className="divide-y divide-slate-100">
                {(lineage.direct_reports || []).map((c) => (
                  <Link
                    key={c.id || c.display_code || c.user_id}
                    to={`/user-management/users/${c.id}`}
                    className="flex items-center gap-4 px-4 py-3 hover:bg-slate-50 transition-colors"
                  >
                    <span className="font-mono text-sm font-semibold text-indigo-700">{formatUserId(c)}</span>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded-md ${roleBadgeClass(c.role)}`}>{c.role}</span>
                    <span className="text-slate-700 text-sm">{c.name}</span>
                  </Link>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
};

export default HierarchyCard;
