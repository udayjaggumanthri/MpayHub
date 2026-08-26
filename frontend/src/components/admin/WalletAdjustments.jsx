import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  FaArrowDown,
  FaArrowUp,
  FaFileExcel,
  FaMagnifyingGlass,
  FaRotate,
  FaWallet,
} from 'react-icons/fa6';
import { walletAdjustmentsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import Badge from '../common/Badge';
import Button from '../common/Button';
import Card from '../common/Card';
import FeedbackModal from '../common/FeedbackModal';
import Input from '../common/Input';
import LoadingSpinner from '../common/LoadingSpinner';
import ReportDateRange from '../common/ReportDateRange';

const REASON_OPTIONS = [
  { value: 'failed_transaction', label: 'Failed transaction' },
  { value: 'amount_not_reflected', label: 'Amount not reflected' },
  { value: 'transaction_mismatch', label: 'Transaction mismatch' },
  { value: 'refund_reversal', label: 'Refund / reversal' },
  { value: 'other', label: 'Other' },
];

const emptyForm = () => ({
  wallet_type: 'main',
  adjustment_type: 'CREDIT',
  amount: '',
  reference_number: '',
  reason_category: 'failed_transaction',
  remarks: '',
});

const emptyFilters = () => ({
  q: '',
  wallet_type: '',
  adjustment_type: '',
  date_from: '',
  date_to: '',
  reference: '',
  status: '',
});

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

function projectedBalance(current, type, amount) {
  const cur = Number(current || 0);
  const amt = Number(amount || 0);
  if (!Number.isFinite(cur) || !Number.isFinite(amt)) return null;
  return type === 'DEBIT' ? cur - amt : cur + amt;
}

const WalletAdjustments = () => {
  const [tab, setTab] = useState('new'); // new | report

  // --- New adjustment ---
  const [lookupQ, setLookupQ] = useState('');
  const [lookupLoading, setLookupLoading] = useState(false);
  const [lookupResults, setLookupResults] = useState([]);
  const [selectedUser, setSelectedUser] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [fieldErrors, setFieldErrors] = useState({});
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const lookupTimer = useRef(null);

  // --- Report ---
  const [filters, setFilters] = useState(emptyFilters);
  const [appliedFilters, setAppliedFilters] = useState(emptyFilters);
  const [rows, setRows] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: 50, total: 0, total_pages: 1 });
  const [reportLoading, setReportLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [detailRow, setDetailRow] = useState(null);

  const [feedback, setFeedback] = useState({ open: false, title: '', description: '' });

  const showFeedback = (title, description) =>
    setFeedback({ open: true, title, description });

  const currentBalance = useMemo(() => {
    if (!selectedUser) return null;
    return selectedUser.balances?.[form.wallet_type] ?? '0';
  }, [selectedUser, form.wallet_type]);

  const nextBalance = useMemo(() => {
    if (currentBalance == null || !form.amount) return null;
    return projectedBalance(currentBalance, form.adjustment_type, form.amount);
  }, [currentBalance, form.amount, form.adjustment_type]);

  // Debounced user lookup
  useEffect(() => {
    if (lookupTimer.current) clearTimeout(lookupTimer.current);
    const q = lookupQ.trim();
    if (q.length < 2) {
      setLookupResults([]);
      setLookupLoading(false);
      return undefined;
    }
    setLookupLoading(true);
    lookupTimer.current = setTimeout(async () => {
      const res = await walletAdjustmentsAPI.userLookup(q);
      if (res.success) {
        setLookupResults(res.data?.users || []);
      } else {
        setLookupResults([]);
      }
      setLookupLoading(false);
    }, 300);
    return () => {
      if (lookupTimer.current) clearTimeout(lookupTimer.current);
    };
  }, [lookupQ]);

  const loadReport = useCallback(
    async (page = 1, filterOverride = null) => {
      const f = filterOverride || appliedFilters;
      setReportLoading(true);
      const params = {
        page,
        page_size: pagination.page_size || 50,
      };
      Object.entries(f).forEach(([k, v]) => {
        if (v != null && String(v).trim() !== '') params[k] = String(v).trim();
      });
      const res = await walletAdjustmentsAPI.list(params);
      setReportLoading(false);
      if (!res.success) {
        showFeedback('Could not load report', res.message || 'Please try again.');
        return;
      }
      setRows(res.data?.results || []);
      setPagination(res.data?.pagination || { page: 1, page_size: 50, total: 0, total_pages: 1 });
    },
    [appliedFilters, pagination.page_size]
  );

  useEffect(() => {
    if (tab === 'report') {
      loadReport(1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, appliedFilters]);

  const validateForm = () => {
    const errs = {};
    if (!selectedUser) errs.user = 'Select a user first.';
    if (!['main', 'bbps'].includes(form.wallet_type)) errs.wallet_type = 'Select a wallet.';
    if (!['CREDIT', 'DEBIT'].includes(form.adjustment_type)) {
      errs.adjustment_type = 'Select credit or debit.';
    }
    const amt = Number(form.amount);
    if (!form.amount || !Number.isFinite(amt) || amt <= 0) {
      errs.amount = 'Enter a valid amount greater than zero.';
    }
    if (!String(form.reference_number || '').trim()) {
      errs.reference_number = 'Transaction reference is required.';
    }
    if (!form.reason_category) errs.reason_category = 'Select a reason.';
    if (!String(form.remarks || '').trim() || String(form.remarks).trim().length < 5) {
      errs.remarks = 'Remarks are required (at least 5 characters).';
    }
    if (
      form.adjustment_type === 'DEBIT' &&
      currentBalance != null &&
      Number.isFinite(amt) &&
      amt > Number(currentBalance)
    ) {
      errs.amount = `Insufficient balance (available ${formatCurrency(currentBalance)}).`;
    }
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  };

  const openConfirm = (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    setConfirmOpen(true);
  };

  const submitAdjustment = async () => {
    if (!selectedUser) return;
    setSubmitting(true);
    const res = await walletAdjustmentsAPI.create({
      user_id: selectedUser.id,
      wallet_type: form.wallet_type,
      adjustment_type: form.adjustment_type,
      amount: String(form.amount),
      reference_number: String(form.reference_number).trim(),
      reason_category: form.reason_category,
      remarks: String(form.remarks).trim(),
    });
    setSubmitting(false);
    setConfirmOpen(false);
    if (!res.success) {
      showFeedback('Adjustment failed', res.message || 'Please review the details and try again.');
      return;
    }
    const adj = res.data?.adjustment;
    const balances = res.data?.balances;
    if (balances && selectedUser) {
      setSelectedUser({ ...selectedUser, balances });
    }
    setForm(emptyForm());
    setFieldErrors({});
    showFeedback(
      'Adjustment successful',
      `${adj?.adjustment_type || ''} of ${formatCurrency(adj?.amount)} posted as ${adj?.adjustment_id || ''}. ` +
        `New ${adj?.wallet_type || ''} balance: ${formatCurrency(adj?.balance_after)}.`
    );
  };

  const applyReportFilters = (e) => {
    e?.preventDefault?.();
    setAppliedFilters({ ...filters });
  };

  const handleExport = async () => {
    setExporting(true);
    const params = {};
    Object.entries(appliedFilters).forEach(([k, v]) => {
      if (v != null && String(v).trim() !== '') params[k] = String(v).trim();
    });
    const res = await walletAdjustmentsAPI.exportExcel(params);
    setExporting(false);
    if (!res.success) {
      showFeedback('Export failed', res.message || 'Could not download the Excel file.');
    }
  };

  const reasonLabel = (value) =>
    REASON_OPTIONS.find((o) => o.value === value)?.label || value || '—';

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">Wallet Adjustments</h1>
          <p className="mt-1 text-sm text-slate-600">
            Manually credit or debit Main / BBPS wallets with mandatory documentation and a full audit trail.
          </p>
        </div>
        <div className="inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
          <button
            type="button"
            className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
              tab === 'new' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'
            }`}
            onClick={() => setTab('new')}
          >
            New Adjustment
          </button>
          <button
            type="button"
            className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
              tab === 'report' ? 'bg-indigo-600 text-white' : 'text-slate-600 hover:bg-slate-50'
            }`}
            onClick={() => setTab('report')}
          >
            Adjustment Report
          </button>
        </div>
      </div>

      {tab === 'new' && (
        <div className="grid gap-6 lg:grid-cols-5">
          <Card className="lg:col-span-3 space-y-5">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Select user</h2>
              <p className="text-xs text-slate-500 mt-0.5">
                Search by phone, user ID, display code, or name.
              </p>
              <div className="mt-3 relative">
                <Input
                  label="User search"
                  value={lookupQ}
                  onChange={(e) => setLookupQ(e.target.value)}
                  placeholder="Type at least 2 characters…"
                  icon={FaMagnifyingGlass}
                  error={fieldErrors.user}
                />
                {(lookupLoading || lookupResults.length > 0) && !selectedUser && (
                  <div className="absolute z-20 mt-1 w-full max-h-64 overflow-auto rounded-xl border border-slate-200 bg-white shadow-lg">
                    {lookupLoading && (
                      <div className="px-4 py-3 text-sm text-slate-500">Searching…</div>
                    )}
                    {!lookupLoading &&
                      lookupResults.map((u) => (
                        <button
                          key={u.id}
                          type="button"
                          className="w-full text-left px-4 py-3 hover:bg-indigo-50 border-b border-slate-100 last:border-0"
                          onClick={() => {
                            setSelectedUser(u);
                            setLookupQ('');
                            setLookupResults([]);
                            setFieldErrors((prev) => ({ ...prev, user: undefined }));
                          }}
                        >
                          <div className="font-semibold text-slate-900">
                            {u.name || u.display_code || u.user_id}
                          </div>
                          <div className="text-xs text-slate-500">
                            {[u.user_id, u.display_code, u.phone, u.role].filter(Boolean).join(' · ')}
                          </div>
                        </button>
                      ))}
                  </div>
                )}
              </div>

              {selectedUser && (
                <div className="mt-4 rounded-xl border border-indigo-100 bg-indigo-50/60 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-slate-900">
                        {selectedUser.name || selectedUser.user_id}
                      </p>
                      <p className="text-xs text-slate-600 mt-0.5">
                        {[selectedUser.user_id, selectedUser.display_code, selectedUser.phone, selectedUser.role]
                          .filter(Boolean)
                          .join(' · ')}
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedUser(null);
                        setForm(emptyForm());
                      }}
                    >
                      Change
                    </Button>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-3">
                    <div className="rounded-lg bg-white border border-slate-100 px-3 py-2">
                      <p className="text-xs text-slate-500 flex items-center gap-1">
                        <FaWallet /> Main
                      </p>
                      <p className="text-base font-bold text-slate-900">
                        {formatCurrency(selectedUser.balances?.main)}
                      </p>
                    </div>
                    <div className="rounded-lg bg-white border border-slate-100 px-3 py-2">
                      <p className="text-xs text-slate-500 flex items-center gap-1">
                        <FaWallet /> BBPS
                      </p>
                      <p className="text-base font-bold text-slate-900">
                        {formatCurrency(selectedUser.balances?.bbps)}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <form onSubmit={openConfirm} className="space-y-4 border-t border-slate-100 pt-5">
              <h2 className="text-lg font-semibold text-slate-900">Adjustment details</h2>

              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Wallet</label>
                  <select
                    className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500"
                    value={form.wallet_type}
                    onChange={(e) => setForm((f) => ({ ...f, wallet_type: e.target.value }))}
                  >
                    <option value="main">Main wallet</option>
                    <option value="bbps">BBPS wallet</option>
                  </select>
                  {fieldErrors.wallet_type && (
                    <p className="mt-1 text-xs text-red-600">{fieldErrors.wallet_type}</p>
                  )}
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Type</label>
                  <div className="flex rounded-lg border border-slate-200 overflow-hidden">
                    <button
                      type="button"
                      className={`flex-1 px-3 py-2.5 text-sm font-semibold flex items-center justify-center gap-1.5 ${
                        form.adjustment_type === 'CREDIT'
                          ? 'bg-emerald-600 text-white'
                          : 'bg-white text-slate-600 hover:bg-slate-50'
                      }`}
                      onClick={() => setForm((f) => ({ ...f, adjustment_type: 'CREDIT' }))}
                    >
                      <FaArrowUp /> Credit
                    </button>
                    <button
                      type="button"
                      className={`flex-1 px-3 py-2.5 text-sm font-semibold flex items-center justify-center gap-1.5 ${
                        form.adjustment_type === 'DEBIT'
                          ? 'bg-red-600 text-white'
                          : 'bg-white text-slate-600 hover:bg-slate-50'
                      }`}
                      onClick={() => setForm((f) => ({ ...f, adjustment_type: 'DEBIT' }))}
                    >
                      <FaArrowDown /> Debit
                    </button>
                  </div>
                </div>
              </div>

              <Input
                label="Amount (₹)"
                type="number"
                step="0.01"
                min="0.01"
                value={form.amount}
                onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
                error={fieldErrors.amount}
                required
              />

              <Input
                label="Transaction reference"
                value={form.reference_number}
                onChange={(e) => setForm((f) => ({ ...f, reference_number: e.target.value }))}
                placeholder="Original UTR / txn id / service id"
                error={fieldErrors.reference_number}
                helperText="Required — links this adjustment to the original transaction."
                required
              />

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Reason category <span className="text-red-500">*</span>
                </label>
                <select
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500"
                  value={form.reason_category}
                  onChange={(e) => setForm((f) => ({ ...f, reason_category: e.target.value }))}
                >
                  {REASON_OPTIONS.map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Remarks <span className="text-red-500">*</span>
                </label>
                <textarea
                  className={`w-full rounded-lg border px-3 py-2.5 text-sm focus:ring-2 focus:ring-indigo-500 min-h-[96px] ${
                    fieldErrors.remarks ? 'border-red-400' : 'border-slate-300'
                  }`}
                  value={form.remarks}
                  onChange={(e) => setForm((f) => ({ ...f, remarks: e.target.value }))}
                  placeholder="Explain why this adjustment is needed…"
                  maxLength={2000}
                />
                {fieldErrors.remarks && (
                  <p className="mt-1 text-xs text-red-600">{fieldErrors.remarks}</p>
                )}
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setForm(emptyForm());
                    setFieldErrors({});
                  }}
                >
                  Reset
                </Button>
                <Button type="submit" variant="primary">
                  Review &amp; confirm
                </Button>
              </div>
            </form>
          </Card>

          <Card className="lg:col-span-2 h-fit space-y-3">
            <h2 className="text-lg font-semibold text-slate-900">Preview</h2>
            {!selectedUser ? (
              <p className="text-sm text-slate-500">Select a user to see the balance impact.</p>
            ) : (
              <>
                <div className="rounded-xl bg-slate-50 border border-slate-100 p-4 space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Wallet</span>
                    <span className="font-semibold capitalize">{form.wallet_type}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Current balance</span>
                    <span className="font-semibold">{formatCurrency(currentBalance)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Adjustment</span>
                    <span
                      className={`font-semibold ${
                        form.adjustment_type === 'DEBIT' ? 'text-red-600' : 'text-emerald-600'
                      }`}
                    >
                      {form.adjustment_type === 'DEBIT' ? '−' : '+'}
                      {form.amount ? formatCurrency(form.amount) : '—'}
                    </span>
                  </div>
                  <div className="border-t border-slate-200 pt-2 flex justify-between">
                    <span className="text-slate-500">New balance</span>
                    <span className="font-bold text-slate-900">
                      {nextBalance == null ? '—' : formatCurrency(nextBalance)}
                    </span>
                  </div>
                </div>
                <p className="text-xs text-amber-700 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                  This action posts immediately to the user&apos;s wallet and passbook. A confirmation
                  step is required before funds move.
                </p>
              </>
            )}
          </Card>
        </div>
      )}

      {tab === 'report' && (
        <div className="space-y-4">
          <Card>
            <form
              onSubmit={applyReportFilters}
              className="grid gap-3 md:grid-cols-3 lg:grid-cols-6 items-end"
            >
              <Input
                label="Search"
                value={filters.q}
                onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
                placeholder="User / adj id / ref"
              />
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Wallet</label>
                <select
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm"
                  value={filters.wallet_type}
                  onChange={(e) => setFilters((f) => ({ ...f, wallet_type: e.target.value }))}
                >
                  <option value="">All</option>
                  <option value="main">Main</option>
                  <option value="bbps">BBPS</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Type</label>
                <select
                  className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm"
                  value={filters.adjustment_type}
                  onChange={(e) => setFilters((f) => ({ ...f, adjustment_type: e.target.value }))}
                >
                  <option value="">All</option>
                  <option value="CREDIT">Credit</option>
                  <option value="DEBIT">Debit</option>
                </select>
              </div>
              <div className="md:col-span-3 lg:col-span-2">
                <ReportDateRange
                  idPrefix="wallet-adj"
                  dateFrom={filters.date_from}
                  dateTo={filters.date_to}
                  fromLabel="From"
                  toLabel="To"
                  onChange={({ dateFrom, dateTo }) =>
                    setFilters((f) => ({ ...f, date_from: dateFrom, date_to: dateTo }))
                  }
                />
              </div>
              <Input
                label="Reference"
                value={filters.reference}
                onChange={(e) => setFilters((f) => ({ ...f, reference: e.target.value }))}
              />
              <div className="md:col-span-3 lg:col-span-6 flex flex-wrap gap-2 justify-end">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setFilters(emptyFilters());
                    setAppliedFilters(emptyFilters());
                  }}
                >
                  Clear
                </Button>
                <Button type="submit" variant="primary" icon={FaMagnifyingGlass}>
                  Apply filters
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  icon={FaFileExcel}
                  loading={exporting}
                  onClick={handleExport}
                >
                  Export Excel
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  icon={FaRotate}
                  onClick={() => loadReport(pagination.page || 1)}
                >
                  Refresh
                </Button>
              </div>
            </form>
          </Card>

          <Card className="overflow-hidden" padding="none">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
              <p className="text-sm text-slate-600">
                {reportLoading
                  ? 'Loading…'
                  : `${pagination.total || 0} adjustment${pagination.total === 1 ? '' : 's'}`}
              </p>
            </div>
            {reportLoading ? (
              <div className="py-16 flex justify-center">
                <LoadingSpinner />
              </div>
            ) : rows.length === 0 ? (
              <div className="py-16 text-center text-sm text-slate-500">
                No adjustments match these filters.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <tr>
                      <th className="px-4 py-3 font-semibold">Date</th>
                      <th className="px-4 py-3 font-semibold">Adjustment ID</th>
                      <th className="px-4 py-3 font-semibold">User</th>
                      <th className="px-4 py-3 font-semibold">Wallet</th>
                      <th className="px-4 py-3 font-semibold">Type</th>
                      <th className="px-4 py-3 font-semibold text-right">Amount</th>
                      <th className="px-4 py-3 font-semibold text-right">Before → After</th>
                      <th className="px-4 py-3 font-semibold">Reference</th>
                      <th className="px-4 py-3 font-semibold">Admin</th>
                      <th className="px-4 py-3 font-semibold" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {rows.map((r) => (
                      <tr key={r.id || r.adjustment_id} className="hover:bg-slate-50/80">
                        <td className="px-4 py-3 whitespace-nowrap text-slate-600">
                          {formatWhen(r.created_at)}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-slate-800">
                          {r.adjustment_id}
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium text-slate-900">
                            {r.user?.name || r.user?.user_id || '—'}
                          </div>
                          <div className="text-xs text-slate-500">
                            {[r.user?.user_id, r.user?.phone].filter(Boolean).join(' · ')}
                          </div>
                        </td>
                        <td className="px-4 py-3 capitalize">{r.wallet_type}</td>
                        <td className="px-4 py-3">
                          <Badge
                            variant={r.adjustment_type === 'CREDIT' ? 'success' : 'error'}
                            size="sm"
                          >
                            {r.adjustment_type}
                          </Badge>
                        </td>
                        <td className="px-4 py-3 text-right font-semibold">
                          {formatCurrency(r.amount)}
                        </td>
                        <td className="px-4 py-3 text-right text-xs text-slate-600 whitespace-nowrap">
                          {formatCurrency(r.balance_before)} → {formatCurrency(r.balance_after)}
                        </td>
                        <td className="px-4 py-3 font-mono text-xs max-w-[140px] truncate">
                          {r.reference_number}
                        </td>
                        <td className="px-4 py-3 text-slate-600">{r.adjusted_by?.name || '—'}</td>
                        <td className="px-4 py-3 text-right">
                          <button
                            type="button"
                            className="text-indigo-600 hover:underline text-xs font-semibold"
                            onClick={() => setDetailRow(r)}
                          >
                            Details
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {pagination.total_pages > 1 && (
              <div className="px-4 py-3 border-t border-slate-100 flex items-center justify-between">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={pagination.page <= 1}
                  onClick={() => loadReport(pagination.page - 1)}
                >
                  Previous
                </Button>
                <span className="text-xs text-slate-500">
                  Page {pagination.page} of {pagination.total_pages}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={pagination.page >= pagination.total_pages}
                  onClick={() => loadReport(pagination.page + 1)}
                >
                  Next
                </Button>
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Confirm modal */}
      {confirmOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          onClick={() => !submitting && setConfirmOpen(false)}
        >
          <div
            className="w-full max-w-md rounded-2xl bg-white p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-bold text-slate-900">Confirm wallet adjustment</h3>
            <p className="mt-1 text-sm text-slate-600">
              Review carefully — this posts funds immediately and cannot be undone (a reverse
              adjustment can be created if needed).
            </p>
            <ul className="mt-4 space-y-2 rounded-xl border border-slate-100 bg-slate-50/80 px-4 py-3 text-sm text-slate-700">
              <li>
                <span className="text-slate-500">User:</span>{' '}
                <strong>
                  {selectedUser?.name || selectedUser?.user_id} ({selectedUser?.phone})
                </strong>
              </li>
              <li>
                <span className="text-slate-500">Wallet:</span>{' '}
                <strong className="capitalize">{form.wallet_type}</strong>
              </li>
              <li>
                <span className="text-slate-500">Action:</span>{' '}
                <strong
                  className={
                    form.adjustment_type === 'DEBIT' ? 'text-red-600' : 'text-emerald-600'
                  }
                >
                  {form.adjustment_type} {formatCurrency(form.amount)}
                </strong>
              </li>
              <li>
                <span className="text-slate-500">Balance:</span>{' '}
                <strong>
                  {formatCurrency(currentBalance)} → {formatCurrency(nextBalance)}
                </strong>
              </li>
              <li>
                <span className="text-slate-500">Reference:</span>{' '}
                <strong className="font-mono">{form.reference_number}</strong>
              </li>
              <li>
                <span className="text-slate-500">Reason:</span>{' '}
                <strong>{reasonLabel(form.reason_category)}</strong>
              </li>
              <li>
                <span className="text-slate-500">Remarks:</span> {form.remarks}
              </li>
            </ul>
            <div className="mt-5 flex justify-end gap-3">
              <Button
                type="button"
                variant="outline"
                disabled={submitting}
                onClick={() => setConfirmOpen(false)}
              >
                Cancel
              </Button>
              <Button
                type="button"
                variant={form.adjustment_type === 'DEBIT' ? 'danger' : 'success'}
                loading={submitting}
                onClick={submitAdjustment}
              >
                Confirm {form.adjustment_type === 'DEBIT' ? 'debit' : 'credit'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Detail modal */}
      {detailRow && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm"
          role="dialog"
          aria-modal="true"
          onClick={() => setDetailRow(null)}
        >
          <div
            className="w-full max-w-lg rounded-2xl bg-white p-6 shadow-2xl max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-lg font-bold text-slate-900">Adjustment details</h3>
                <p className="text-xs font-mono text-slate-500 mt-0.5">{detailRow.adjustment_id}</p>
              </div>
              <Badge
                variant={detailRow.adjustment_type === 'CREDIT' ? 'success' : 'error'}
                size="sm"
              >
                {detailRow.adjustment_type}
              </Badge>
            </div>
            <dl className="mt-4 grid grid-cols-2 gap-3 text-sm">
              {[
                ['When', formatWhen(detailRow.created_at)],
                ['User', detailRow.user?.name || '—'],
                ['Phone', detailRow.user?.phone || '—'],
                ['User ID', detailRow.user?.user_id || '—'],
                ['Wallet', detailRow.wallet_type],
                ['Amount', formatCurrency(detailRow.amount)],
                ['Before', formatCurrency(detailRow.balance_before)],
                ['After', formatCurrency(detailRow.balance_after)],
                ['Reference', detailRow.reference_number],
                ['Reason', detailRow.reason_category_label || reasonLabel(detailRow.reason_category)],
                ['Admin', detailRow.adjusted_by?.name || '—'],
                ['Status', detailRow.status],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg bg-slate-50 px-3 py-2">
                  <dt className="text-xs text-slate-500">{k}</dt>
                  <dd className="font-medium text-slate-900 break-all">{v}</dd>
                </div>
              ))}
            </dl>
            <div className="mt-3 rounded-lg bg-slate-50 px-3 py-2 text-sm">
              <p className="text-xs text-slate-500">Remarks</p>
              <p className="text-slate-800 whitespace-pre-wrap">{detailRow.remarks}</p>
            </div>
            <div className="mt-5 flex justify-end">
              <Button type="button" variant="outline" onClick={() => setDetailRow(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      <FeedbackModal
        open={feedback.open}
        onClose={() => setFeedback((f) => ({ ...f, open: false }))}
        title={feedback.title}
        description={feedback.description}
      />
    </div>
  );
};

export default WalletAdjustments;
