import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FaRotate, FaWallet } from 'react-icons/fa6';
import { bbpsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import Badge from '../common/Badge';
import Button from '../common/Button';
import Card from '../common/Card';
import FeedbackModal from '../common/FeedbackModal';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';
import ReportDateRange from '../common/ReportDateRange';

const ENTRY_TYPES = [
  { value: '', label: 'All types' },
  { value: 'MANUAL_SET', label: 'Manual set' },
  { value: 'AUTO_DEBIT', label: 'Auto debit' },
  { value: 'AUTO_CREDIT', label: 'Auto credit' },
];

function formatWhen(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

function entryBadgeVariant(type) {
  if (type === 'AUTO_DEBIT') return 'error';
  if (type === 'AUTO_CREDIT') return 'success';
  return 'info';
}

function entryLabel(type) {
  if (type === 'AUTO_DEBIT') return 'Auto debit';
  if (type === 'AUTO_CREDIT') return 'Auto credit';
  if (type === 'MANUAL_SET') return 'Manual set';
  return type || '—';
}

const BbpsProviderFloat = () => {
  const [floatInfo, setFloatInfo] = useState(null);
  const [ledger, setLedger] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: 25, total: 0, total_pages: 1 });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [settingsSaving, setSettingsSaving] = useState(false);

  const [newBalance, setNewBalance] = useState('');
  const [remarks, setRemarks] = useState('');
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [thresholdDraft, setThresholdDraft] = useState('');
  const [filters, setFilters] = useState({ entry_type: '', date_from: '', date_to: '' });
  const [appliedFilters, setAppliedFilters] = useState({ entry_type: '', date_from: '', date_to: '' });

  const [feedback, setFeedback] = useState({ open: false, title: '', description: '' });
  const showFeedback = (title, description) => setFeedback({ open: true, title, description });

  const balanceNum = useMemo(() => Number(floatInfo?.balance || 0), [floatInfo]);
  const thresholdNum = useMemo(() => Number(floatInfo?.low_balance_threshold || 0), [floatInfo]);
  const isNegative = Boolean(floatInfo?.is_negative) || balanceNum < 0;
  const isLow = Boolean(floatInfo?.is_low_balance) || (!isNegative && balanceNum <= thresholdNum);

  const load = useCallback(
    async (page = 1, filterOverride = null) => {
      setLoading(true);
      const f = filterOverride || appliedFilters;
      const res = await bbpsAPI.getProviderFloat({
        page,
        page_size: pagination.page_size || 25,
        entry_type: f.entry_type || undefined,
        date_from: f.date_from || undefined,
        date_to: f.date_to || undefined,
      });
      setLoading(false);
      if (!res.success) {
        showFeedback('Could not load provider float', res.message || 'Please try again.');
        return;
      }
      const data = res.data || {};
      const flt = data.float || {};
      setFloatInfo(flt);
      setThresholdDraft(String(flt.low_balance_threshold ?? ''));
      const led = data.ledger || {};
      setLedger(led.results || []);
      setPagination(led.pagination || { page: 1, page_size: 25, total: 0, total_pages: 1 });
    },
    [appliedFilters, pagination.page_size]
  );

  useEffect(() => {
    load(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openConfirm = () => {
    const amt = Number(newBalance);
    if (!Number.isFinite(amt) || amt < 0) {
      showFeedback('Invalid balance', 'Enter a non-negative number for the new float balance.');
      return;
    }
    if (!String(remarks || '').trim() || String(remarks).trim().length < 5) {
      showFeedback('Remarks required', 'Add remarks (at least 5 characters) explaining this override.');
      return;
    }
    setConfirmOpen(true);
  };

  const submitOverride = async () => {
    setSaving(true);
    const res = await bbpsAPI.setProviderFloat({
      new_balance: newBalance,
      remarks: String(remarks).trim(),
    });
    setSaving(false);
    setConfirmOpen(false);
    if (!res.success) {
      showFeedback('Update failed', res.message || 'Could not update provider float.');
      return;
    }
    setNewBalance('');
    setRemarks('');
    showFeedback('Float updated', res.message || `Balance set to ${formatCurrency(res.data?.float?.balance)}`);
    await load(1);
  };

  const toggleEnforcement = async () => {
    if (!floatInfo) return;
    setSettingsSaving(true);
    const res = await bbpsAPI.updateProviderFloatSettings({
      enforcement_enabled: !floatInfo.enforcement_enabled,
    });
    setSettingsSaving(false);
    if (!res.success) {
      showFeedback('Settings update failed', res.message || 'Could not update enforcement.');
      return;
    }
    setFloatInfo(res.data?.float || floatInfo);
    showFeedback(
      'Enforcement updated',
      res.data?.float?.enforcement_enabled
        ? 'Payments will be blocked when float is insufficient.'
        : 'Float gate is off — payments will not check company float.'
    );
  };

  const saveThreshold = async () => {
    setSettingsSaving(true);
    const res = await bbpsAPI.updateProviderFloatSettings({
      low_balance_threshold: thresholdDraft,
    });
    setSettingsSaving(false);
    if (!res.success) {
      showFeedback('Threshold update failed', res.message || 'Could not update threshold.');
      return;
    }
    setFloatInfo(res.data?.float || floatInfo);
    showFeedback('Threshold saved', `Low-balance warning at ${formatCurrency(res.data?.float?.low_balance_threshold)}`);
  };

  const applyFilters = async () => {
    setAppliedFilters({ ...filters });
    await load(1, filters);
  };

  return (
    <div className="space-y-6 p-4 md:p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-slate-100">BBPS Provider Float</h1>
          <p className="mt-1 text-sm text-slate-600 dark:text-slate-400">
            Track your company BillAvenue prepaid balance. Admin-only — retailers never see this figure.
          </p>
        </div>
        <Button variant="secondary" onClick={() => load(pagination.page || 1)} disabled={loading}>
          <FaRotate className="mr-2" /> Refresh
        </Button>
      </div>

      {loading && !floatInfo ? (
        <div className="flex justify-center py-16">
          <LoadingSpinner />
        </div>
      ) : (
        <>
          {(isNegative || isLow) && (
            <div
              className={`rounded-lg border px-4 py-3 text-sm ${
                isNegative
                  ? 'border-red-300 dark:border-red-800 bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300'
                  : 'border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300'
              }`}
            >
              {isNegative
                ? 'Tracked float is negative. Reconcile with the BillAvenue dashboard and set the correct balance.'
                : `Tracked float is at or below the low-balance threshold (${formatCurrency(thresholdNum)}).`}
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-3">
            <Card className="p-5">
              <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 text-sm">
                <FaWallet /> Tracked float balance
              </div>
              <div className={`mt-2 text-3xl font-semibold ${isNegative ? 'text-red-600 dark:text-red-400' : 'text-slate-900 dark:text-slate-100'}`}>
                {formatCurrency(floatInfo?.balance)}
              </div>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                Mode: {(floatInfo?.environment || '—').toUpperCase()}
                {floatInfo?.last_manual_set_at
                  ? ` · Last set ${formatWhen(floatInfo.last_manual_set_at)}`
                  : ''}
              </p>
            </Card>
            <Card className="p-5">
              <div className="text-sm text-slate-500 dark:text-slate-400">Today&apos;s auto-debit (spend)</div>
              <div className="mt-2 text-3xl font-semibold text-slate-900 dark:text-slate-100">
                {formatCurrency(floatInfo?.today_auto_debit_total)}
              </div>
              <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Sum of AUTO_DEBIT ledger entries for today</p>
            </Card>
            <Card className="p-5 space-y-3">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <div className="text-sm text-slate-500 dark:text-slate-400">Payment gate</div>
                  <div className="mt-1 font-medium text-slate-900 dark:text-slate-100">
                    {floatInfo?.enforcement_enabled ? 'Enforcement ON' : 'Enforcement OFF'}
                  </div>
                </div>
                <Button
                  variant={floatInfo?.enforcement_enabled ? 'danger' : 'primary'}
                  size="sm"
                  disabled={settingsSaving}
                  onClick={toggleEnforcement}
                >
                  {floatInfo?.enforcement_enabled ? 'Disable gate' : 'Enable gate'}
                </Button>
              </div>
              <div className="flex flex-wrap items-end gap-2">
                <div className="flex-1 min-w-[140px]">
                  <Input
                    label="Low-balance threshold"
                    type="number"
                    value={thresholdDraft}
                    onChange={(e) => setThresholdDraft(e.target.value)}
                  />
                </div>
                <Button variant="secondary" disabled={settingsSaving} onClick={saveThreshold}>
                  Save
                </Button>
              </div>
            </Card>
          </div>

          <Card className="p-5 space-y-4">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Update balance</h2>
            <p className="text-sm text-slate-600 dark:text-slate-400">
              After recharging on the BillAvenue dashboard, override the tracked balance here (e.g. ₹2,00,000 →
              ₹7,00,000). This does not call BillAvenue — it only updates MpayHub tracking.
            </p>
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="New balance (₹)"
                type="number"
                value={newBalance}
                onChange={(e) => setNewBalance(e.target.value)}
                placeholder="e.g. 700000"
              />
              <Input
                label="Remarks (required)"
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder="Synced from BillAvenue dashboard after recharge"
              />
            </div>
            <div className="flex justify-end">
              <Button onClick={openConfirm} disabled={saving}>
                Update balance
              </Button>
            </div>
          </Card>

          <Card className="p-5 space-y-4">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Ledger</h2>
              <div className="flex flex-wrap items-end gap-2">
                <div>
                  <label className="mb-1 block text-xs font-medium text-slate-600 dark:text-slate-400">Type</label>
                  <select
                    className="rounded-md border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
                    value={filters.entry_type}
                    onChange={(e) => setFilters((s) => ({ ...s, entry_type: e.target.value }))}
                  >
                    {ENTRY_TYPES.map((o) => (
                      <option key={o.value || 'all'} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="min-w-0 w-full sm:min-w-[280px]">
                  <ReportDateRange
                    idPrefix="bbps-float"
                    dateFrom={filters.date_from}
                    dateTo={filters.date_to}
                    fromLabel="From"
                    toLabel="To"
                    onChange={({ dateFrom, dateTo }) =>
                      setFilters((s) => ({ ...s, date_from: dateFrom, date_to: dateTo }))
                    }
                  />
                </div>
                <Button variant="secondary" onClick={applyFilters} disabled={loading}>
                  Apply
                </Button>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm">
                <thead className="border-b border-slate-200 dark:border-slate-700 text-xs uppercase text-slate-500 dark:text-slate-400">
                  <tr>
                    <th className="px-3 py-2">Date</th>
                    <th className="px-3 py-2">Type</th>
                    <th className="px-3 py-2">Amount</th>
                    <th className="px-3 py-2">Before → After</th>
                    <th className="px-3 py-2">Service ID</th>
                    <th className="px-3 py-2">Admin</th>
                    <th className="px-3 py-2">Remarks</th>
                  </tr>
                </thead>
                <tbody>
                  {ledger.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-3 py-8 text-center text-slate-500 dark:text-slate-400">
                        No ledger entries yet.
                      </td>
                    </tr>
                  ) : (
                    ledger.map((row) => (
                      <tr key={row.id} className="border-b border-slate-100 dark:border-slate-800">
                        <td className="px-3 py-2 whitespace-nowrap">{formatWhen(row.created_at)}</td>
                        <td className="px-3 py-2">
                          <Badge variant={entryBadgeVariant(row.entry_type)}>{entryLabel(row.entry_type)}</Badge>
                        </td>
                        <td className="px-3 py-2 whitespace-nowrap">{formatCurrency(row.amount)}</td>
                        <td className="px-3 py-2 whitespace-nowrap">
                          {formatCurrency(row.balance_before)} → {formatCurrency(row.balance_after)}
                        </td>
                        <td className="px-3 py-2 font-mono text-xs">{row.service_id || '—'}</td>
                        <td className="px-3 py-2">{row.performed_by?.name || '—'}</td>
                        <td className="px-3 py-2 max-w-xs truncate" title={row.remarks || ''}>
                          {row.remarks || '—'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {pagination.total_pages > 1 && (
              <div className="flex items-center justify-between text-sm text-slate-600 dark:text-slate-400">
                <span>
                  Page {pagination.page} of {pagination.total_pages} · {pagination.total} entries
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={loading || pagination.page <= 1}
                    onClick={() => load(pagination.page - 1)}
                  >
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={loading || pagination.page >= pagination.total_pages}
                    onClick={() => load(pagination.page + 1)}
                  >
                    Next
                  </Button>
                </div>
              </div>
            )}
          </Card>
        </>
      )}

      {confirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-xl bg-white dark:bg-slate-900 p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-slate-900 dark:text-slate-100">Confirm float override</h3>
            <p className="mt-3 text-sm text-slate-700 dark:text-slate-300">
              Override{' '}
              <span className="font-semibold">{formatCurrency(floatInfo?.balance)}</span> →{' '}
              <span className="font-semibold">{formatCurrency(newBalance)}</span>?
            </p>
            <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">Remarks: {remarks}</p>
            <div className="mt-6 flex justify-end gap-2">
              <Button variant="secondary" disabled={saving} onClick={() => setConfirmOpen(false)}>
                Cancel
              </Button>
              <Button disabled={saving} onClick={submitOverride}>
                {saving ? 'Saving…' : 'Confirm override'}
              </Button>
            </div>
          </div>
        </div>
      )}

      <FeedbackModal
        open={feedback.open}
        title={feedback.title}
        description={feedback.description}
        onClose={() => setFeedback((s) => ({ ...s, open: false }))}
      />
    </div>
  );
};

export default BbpsProviderFloat;
