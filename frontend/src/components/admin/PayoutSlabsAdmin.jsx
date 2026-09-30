import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { FaPlus, FaTrash, FaArrowRight } from 'react-icons/fa6';
import { adminAPI } from '../../services/api';
import Button from '../common/Button';
import Card from '../common/Card';
import LoadingSpinner from '../common/LoadingSpinner';
import { firstErrorMessage } from './gatewayAdminShared';

const emptyRow = () => ({
  min_amount: '0.00',
  max_amount: '',
  charge: '0.00',
  commission: '0.00',
});

const normalizeContiguity = (rows) => {
  if (!rows.length) return [emptyRow()];
  const next = rows.map((r) => ({ ...r }));
  next[0] = { ...next[0], min_amount: '0.00' };
  for (let i = 1; i < next.length; i += 1) {
    const prevMax = String(next[i - 1].max_amount || '').trim();
    if (prevMax !== '') {
      const n = Number(prevMax);
      if (!Number.isNaN(n)) {
        next[i] = { ...next[i], min_amount: (n + 0.01).toFixed(2) };
      }
    }
  }
  return next;
};

const rowTotal = (row) => {
  const c = Number(row.charge) || 0;
  const m = Number(row.commission) || 0;
  return (c + m).toFixed(2);
};

const PayoutSlabsAdmin = () => {
  const [rows, setRows] = useState([emptyRow()]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await adminAPI.getPlatformPayoutSlabs();
    setLoading(false);
    if (!res.success) {
      setError(res.message || 'Could not load payout slabs');
      return;
    }
    const slabs = res.data?.slabs || [];
    if (!slabs.length) {
      setRows([emptyRow()]);
      return;
    }
    setRows(
      normalizeContiguity(
        slabs.map((s) => ({
          min_amount: String(s.min_amount ?? '0'),
          max_amount: s.max_amount == null || s.max_amount === '' ? '' : String(s.max_amount),
          charge: String(s.charge ?? '0'),
          commission: String(s.commission ?? '0'),
        }))
      )
    );
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const updateRow = (idx, key, value) => {
    setRows((prev) => {
      const next = prev.map((r, i) => (i === idx ? { ...r, [key]: value } : r));
      return normalizeContiguity(next);
    });
  };

  const addRow = () => {
    setRows((prev) =>
      normalizeContiguity([
        ...prev,
        { min_amount: '', max_amount: '', charge: '0.00', commission: '0.00' },
      ])
    );
  };

  const removeRow = (idx) => {
    setRows((prev) => {
      if (prev.length <= 1) return prev;
      return normalizeContiguity(prev.filter((_, i) => i !== idx));
    });
  };

  const save = async (e) => {
    e.preventDefault();
    setSaving(true);
    setError('');
    setMessage('');
    const payload = {
      slabs: rows.map((r, i) => ({
        sort_order: i,
        min_amount: r.min_amount,
        max_amount: r.max_amount === '' ? null : r.max_amount,
        charge: r.charge,
        commission: r.commission,
      })),
    };
    const res = await adminAPI.updatePlatformPayoutSlabs(payload);
    setSaving(false);
    if (!res.success) {
      setError(firstErrorMessage(res, 'Could not save payout slabs'));
      return;
    }
    setMessage('Payout slabs saved');
    await load();
  };

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-slate-50/80">
      <div className="mx-auto max-w-5xl space-y-6 px-4 py-8 sm:px-6 lg:px-8">
        <header className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 sm:text-3xl">
              Payout slabs
            </h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-600 dark:text-slate-400">
              Platform-wide fees. End-user total = Charge + Commission. Charge goes to Service Fee
              Tracker; Commission credits Admin Main as platform profit.
            </p>
          </div>
          <Link
            to="/admin/pay-in-packages"
            className="inline-flex items-center gap-2 self-start rounded-xl border px-4 py-2.5 text-sm font-semibold text-slate-700 dark:text-slate-300"
          >
            Pay-in packages
            <FaArrowRight size={14} />
          </Link>
        </header>

        {loading ? (
          <LoadingSpinner />
        ) : (
          <Card shadow="sm" padding="lg" title="Amount bands">
            <form onSubmit={save} className="space-y-4">
              {error ? (
                <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
                  {error}
                </p>
              ) : null}
              {message ? (
                <p className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">
                  {message}
                </p>
              ) : null}

              <div className="flex justify-end">
                <Button type="button" variant="outline" size="sm" icon={FaPlus} onClick={addRow}>
                  Add tier
                </Button>
              </div>

              <div className="space-y-3">
                {rows.map((row, idx) => (
                  <div
                    key={`tier-${idx}`}
                    className="grid grid-cols-1 gap-3 rounded-xl border border-slate-200 p-3 dark:border-slate-700 sm:grid-cols-2 lg:grid-cols-12 lg:items-end"
                  >
                    <div className="lg:col-span-2">
                      <label className="mb-1 block text-xs font-medium">Min</label>
                      <input
                        className="w-full rounded-lg border px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
                        value={row.min_amount}
                        readOnly
                        title="Filled automatically for contiguity"
                      />
                    </div>
                    <div className="lg:col-span-2">
                      <label className="mb-1 block text-xs font-medium">Max (blank = ∞)</label>
                      <input
                        className="w-full rounded-lg border px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
                        value={row.max_amount}
                        onChange={(e) => updateRow(idx, 'max_amount', e.target.value)}
                      />
                    </div>
                    <div className="lg:col-span-2">
                      <label className="mb-1 block text-xs font-medium">Charge (₹)</label>
                      <input
                        className="w-full rounded-lg border px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
                        value={row.charge}
                        onChange={(e) => updateRow(idx, 'charge', e.target.value)}
                      />
                    </div>
                    <div className="lg:col-span-2">
                      <label className="mb-1 block text-xs font-medium">Commission (₹)</label>
                      <input
                        className="w-full rounded-lg border px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
                        value={row.commission}
                        onChange={(e) => updateRow(idx, 'commission', e.target.value)}
                      />
                    </div>
                    <div className="lg:col-span-2">
                      <label className="mb-1 block text-xs font-medium">Total</label>
                      <input
                        className="w-full rounded-lg border bg-slate-50 px-3 py-2 text-sm font-semibold tabular-nums dark:border-slate-600 dark:bg-slate-800"
                        value={rowTotal(row)}
                        readOnly
                      />
                    </div>
                    <div className="flex lg:col-span-2 lg:justify-end">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        icon={FaTrash}
                        disabled={rows.length <= 1}
                        onClick={() => removeRow(idx)}
                      >
                        Remove
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <Button type="button" variant="secondary" onClick={load} disabled={saving}>
                  Reset
                </Button>
                <Button type="submit" loading={saving}>
                  Save slabs
                </Button>
              </div>
            </form>
          </Card>
        )}
      </div>
    </div>
  );
};

export default PayoutSlabsAdmin;
