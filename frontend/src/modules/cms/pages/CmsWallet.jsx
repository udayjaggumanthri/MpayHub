import React, { useCallback, useEffect, useState } from 'react';
import Card from '../../../components/common/Card';
import cmsAPI from '../services/cmsApi';
import { formatCmsAmount, formatCmsDateTime } from '../utils/cmsUserCopy';

const CmsWallet = () => {
  const [wallet, setWallet] = useState(null);

  const load = useCallback(async () => {
    const res = await cmsAPI.wallet();
    if (res.success) setWallet(res.data);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">CMS balance</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          CMS holds and settlements use your Main wallet directly. No separate funding transfer is required.
        </p>
      </header>

      <div className="grid gap-3 sm:grid-cols-3">
        <Card shadow="sm">
          <p className="text-[10px] font-semibold uppercase text-slate-400">Main balance</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{formatCmsAmount(wallet?.balance)}</p>
        </Card>
        <Card shadow="sm">
          <p className="text-[10px] font-semibold uppercase text-slate-400">Held</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{formatCmsAmount(wallet?.held_balance)}</p>
        </Card>
        <Card shadow="sm">
          <p className="text-[10px] font-semibold uppercase text-slate-400">Available</p>
          <p className="mt-1 text-2xl font-bold tabular-nums text-emerald-700 dark:text-emerald-300">
            {formatCmsAmount(wallet?.available)}
          </p>
        </Card>
      </div>

      <Card title="Recent CMS ledger" shadow="sm">
        <ul className="divide-y divide-slate-100 dark:divide-slate-800">
          {(wallet?.recent_entries || []).length === 0 ? (
            <li className="py-4 text-sm text-slate-500">No CMS entries yet.</li>
          ) : (
            (wallet?.recent_entries || []).map((e) => (
              <li key={e.id || e.reference} className="flex justify-between gap-3 py-3 text-sm">
                <div>
                  <p className="font-medium text-slate-800 dark:text-slate-100">{e.entry_type || e.description}</p>
                  <p className="text-xs text-slate-500">{formatCmsDateTime(e.created_at)}</p>
                </div>
                <p className="tabular-nums font-semibold">{formatCmsAmount(e.amount)}</p>
              </li>
            ))
          )}
        </ul>
      </Card>
    </div>
  );
};

export default CmsWallet;
