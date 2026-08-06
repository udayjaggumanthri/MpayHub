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

function todayISO() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function daysAgoISO(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

const BbpsOpsConsole = () => {
  const [planIds, setPlanIds] = useState('');
  const [planLoading, setPlanLoading] = useState(false);
  const [planOutput, setPlanOutput] = useState(null);

  const [agentOptions, setAgentOptions] = useState([]);
  const [selectedAgents, setSelectedAgents] = useState([]);
  const [extraAgent, setExtraAgent] = useState('');
  const [depositForm, setDepositForm] = useState({
    from_date: daysAgoISO(30),
    to_date: todayISO(),
    trans_type: '',
  });
  const [running, setRunning] = useState(false);
  const [activeResult, setActiveResult] = useState(null);

  const [history, setHistory] = useState([]);
  const [pagination, setPagination] = useState({ page: 1, page_size: 15, total: 0, total_pages: 1 });
  const [historyLoading, setHistoryLoading] = useState(false);
  const [envLabel, setEnvLabel] = useState('');

  const [feedback, setFeedback] = useState({ open: false, title: '', description: '' });
  const showFeedback = (title, description) => setFeedback({ open: true, title, description });

  const loadHistory = useCallback(async (page = 1) => {
    setHistoryLoading(true);
    const res = await bbpsAPI.getDepositEnquiryHistory({ page, page_size: 15 });
    setHistoryLoading(false);
    if (!res.success) {
      showFeedback('Could not load history', res.message || 'Please try again.');
      return;
    }
    const data = res.data || {};
    setHistory(data.results || []);
    setPagination(data.pagination || { page: 1, page_size: 15, total: 0, total_pages: 1 });
    setAgentOptions(data.agent_options || []);
    setEnvLabel(data.environment || '');
    if ((!selectedAgents || selectedAgents.length === 0) && (data.default_agents || []).length) {
      setSelectedAgents(data.default_agents);
    }
  }, [selectedAgents]);

  useEffect(() => {
    loadHistory(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleAgent = (agentId) => {
    setSelectedAgents((prev) =>
      prev.includes(agentId) ? prev.filter((x) => x !== agentId) : [...prev, agentId]
    );
  };

  const addExtraAgent = () => {
    const id = String(extraAgent || '').trim();
    if (!id) return;
    setSelectedAgents((prev) => (prev.includes(id) ? prev : [...prev, id]));
    setExtraAgent('');
  };

  const pullPlans = async () => {
    const ids = planIds.split(',').map((x) => x.trim()).filter(Boolean);
    if (!ids.length) {
      showFeedback('Biller IDs required', 'Enter one or more BillAvenue biller IDs, comma-separated.');
      return;
    }
    setPlanLoading(true);
    const res = await bbpsAPI.pullPlans(ids);
    setPlanLoading(false);
    setPlanOutput(res);
    if (!res.success) {
      showFeedback('Plan pull failed', res.message || 'Check biller IDs and BillAvenue config.');
    }
  };

  const runEnquiry = async () => {
    if (!depositForm.from_date || !depositForm.to_date) {
      showFeedback('Dates required', 'Choose from and to dates (YYYY-MM-DD).');
      return;
    }
    if (!selectedAgents.length) {
      showFeedback(
        'Agent required',
        'Select at least one BillAvenue agent profile, or paste an agent ID. Deposit enquiry cannot run without agents.'
      );
      return;
    }
    setRunning(true);
    const res = await bbpsAPI.depositEnquiry({
      from_date: depositForm.from_date,
      to_date: depositForm.to_date,
      trans_type: depositForm.trans_type || '',
      agents: selectedAgents,
    });
    setRunning(false);
    if (!res.success) {
      const snap = res.data?.snapshot;
      if (snap) setActiveResult(snap);
      showFeedback('Deposit enquiry failed', res.message || 'BillAvenue rejected the request.');
      await loadHistory(1);
      return;
    }
    const snap = res.data?.snapshot || {
      ...res.data,
      transactions: res.data?.transactions || [],
      current_balance: res.data?.current_balance,
    };
    setActiveResult(snap);
    showFeedback('Enquiry complete', res.message || 'Deposit enquiry stored for reporting.');
    await loadHistory(1);
  };

  const openHistoryRow = async (id) => {
    const res = await bbpsAPI.getDepositEnquiryDetail(id);
    if (!res.success) {
      showFeedback('Could not open enquiry', res.message || 'Snapshot not found.');
      return;
    }
    setActiveResult(res.data?.snapshot || null);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const txns = useMemo(() => activeResult?.transactions || [], [activeResult]);

  return (
    <div className="mx-auto max-w-6xl space-y-6 p-4 md:p-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">BBPS Ops Console</h1>
        <p className="mt-1 text-sm text-slate-600">
          Operator tools against the live BillAvenue config
          {envLabel ? ` (${String(envLabel).toUpperCase()})` : ''}. Deposit enquiry results are stored for
          reporting.
        </p>
      </div>

      <Card className="space-y-3 p-5">
        <h2 className="text-lg font-semibold text-slate-900">Plan Pull</h2>
        <p className="text-sm text-slate-600">Pull plan MDM for specific biller IDs (comma-separated).</p>
        <input
          className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          placeholder="e.g. BSNL00000NAT01, ..."
          value={planIds}
          onChange={(e) => setPlanIds(e.target.value)}
        />
        <Button onClick={pullPlans} disabled={planLoading}>
          {planLoading ? 'Running…' : 'Run Plan Pull'}
        </Button>
        {planOutput && (
          <pre className="max-h-48 overflow-auto rounded-md border border-slate-200 bg-slate-50 p-3 text-xs">
            {JSON.stringify(planOutput, null, 2)}
          </pre>
        )}
      </Card>

      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-slate-900">Deposit Enquiry</h2>
            <p className="mt-1 text-sm text-slate-600">
              Fetches BillAvenue prepaid deposit ledger for selected agent(s). Each run is saved so you can
              review balance and CR/DR rows later.
            </p>
          </div>
          <Button variant="secondary" size="sm" onClick={() => loadHistory(pagination.page || 1)} disabled={historyLoading}>
            <FaRotate className="mr-2" /> Refresh history
          </Button>
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <Input
            label="From date"
            type="date"
            value={depositForm.from_date}
            onChange={(e) => setDepositForm((p) => ({ ...p, from_date: e.target.value }))}
          />
          <Input
            label="To date"
            type="date"
            value={depositForm.to_date}
            onChange={(e) => setDepositForm((p) => ({ ...p, to_date: e.target.value }))}
          />
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">Trans type</label>
            <select
              className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
              value={depositForm.trans_type}
              onChange={(e) => setDepositForm((p) => ({ ...p, trans_type: e.target.value }))}
            >
              <option value="">All (CR + DR)</option>
              <option value="CR">Credit (CR)</option>
              <option value="DR">Debit (DR)</option>
            </select>
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-xs font-medium text-slate-600">Agents (required)</div>
          {agentOptions.length === 0 ? (
            <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-md px-3 py-2">
              No agent profiles on the active BillAvenue config. Add one under BillAvenue Settings, or paste an
              agent ID below.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {agentOptions.map((opt) => {
                const checked = selectedAgents.includes(opt.agent_id);
                return (
                  <button
                    key={opt.id || opt.agent_id}
                    type="button"
                    onClick={() => toggleAgent(opt.agent_id)}
                    className={`rounded-lg border px-3 py-2 text-left text-sm transition ${
                      checked
                        ? 'border-blue-500 bg-blue-50 text-blue-900'
                        : 'border-slate-200 bg-white text-slate-700 hover:border-slate-300'
                    }`}
                  >
                    <div className="font-medium">{opt.name || 'Agent'}</div>
                    <div className="font-mono text-xs opacity-80">{opt.agent_id}</div>
                    {!opt.enabled && <span className="text-xs text-amber-700">disabled</span>}
                  </button>
                );
              })}
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <input
              className="min-w-[220px] flex-1 rounded-md border border-slate-300 px-3 py-2 text-sm font-mono"
              placeholder="Paste extra agent ID"
              value={extraAgent}
              onChange={(e) => setExtraAgent(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  addExtraAgent();
                }
              }}
            />
            <Button variant="secondary" onClick={addExtraAgent}>
              Add agent ID
            </Button>
          </div>
          {selectedAgents.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {selectedAgents.map((id) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => toggleAgent(id)}
                  className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-0.5 font-mono text-xs text-slate-700 hover:bg-red-50"
                  title="Remove"
                >
                  {id} ×
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <Button onClick={runEnquiry} disabled={running}>
            {running ? 'Running enquiry…' : 'Run Deposit Enquiry'}
          </Button>
        </div>
      </Card>

      {running && (
        <div className="flex justify-center py-6">
          <LoadingSpinner />
        </div>
      )}

      {activeResult && !running && (
        <Card className="space-y-4 p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-slate-900">Enquiry result</h2>
              <p className="mt-1 text-sm text-slate-600">
                Snapshot #{activeResult.id} · {activeResult.from_date} → {activeResult.to_date} · request{' '}
                <span className="font-mono text-xs">{activeResult.request_id || '—'}</span>
              </p>
            </div>
            <Badge variant={activeResult.status === 'SUCCESS' ? 'success' : 'error'}>
              {activeResult.status || '—'}
            </Badge>
          </div>

          {activeResult.error_message ? (
            <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
              {activeResult.error_message}
            </div>
          ) : null}

          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <FaWallet /> Current balance (BillAvenue)
              </div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">
                {formatCurrency(activeResult.current_balance)}
              </div>
              <div className="text-xs text-slate-500">{activeResult.currency || 'INR'}</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">Transactions</div>
              <div className="mt-1 text-2xl font-semibold text-slate-900">
                {activeResult.transaction_count ?? txns.length}
              </div>
              <div className="text-xs text-slate-500">In this date range</div>
            </div>
            <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
              <div className="text-xs text-slate-500">Agents queried</div>
              <div className="mt-2 space-y-1">
                {(activeResult.agents || []).length ? (
                  (activeResult.agents || []).map((a) => (
                    <div key={a} className="font-mono text-xs text-slate-800">
                      {a}
                    </div>
                  ))
                ) : (
                  <span className="text-sm text-slate-500">—</span>
                )}
              </div>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">Date/time</th>
                  <th className="px-3 py-2">Agent</th>
                  <th className="px-3 py-2">Type</th>
                  <th className="px-3 py-2">Amount</th>
                  <th className="px-3 py-2">Source</th>
                  <th className="px-3 py-2">Txn ID</th>
                  <th className="px-3 py-2">Request ID</th>
                </tr>
              </thead>
              <tbody>
                {txns.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-3 py-8 text-center text-slate-500">
                      No deposit transactions in this range.
                    </td>
                  </tr>
                ) : (
                  txns.map((row, idx) => (
                    <tr key={`${row.transaction_id}-${idx}`} className="border-b border-slate-100">
                      <td className="px-3 py-2 whitespace-nowrap">{row.datetime || '—'}</td>
                      <td className="px-3 py-2 font-mono text-xs">{row.agent_id || '—'}</td>
                      <td className="px-3 py-2">
                        <Badge variant={row.trans_type === 'CR' ? 'success' : row.trans_type === 'DR' ? 'error' : 'info'} size="sm">
                          {row.trans_type || '—'}
                        </Badge>
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">{formatCurrency(row.amount)}</td>
                      <td className="px-3 py-2">{row.source || '—'}</td>
                      <td className="px-3 py-2 font-mono text-xs">{row.transaction_id || '—'}</td>
                      <td className="px-3 py-2 font-mono text-xs">{row.request_id || '—'}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card className="space-y-4 p-5">
        <h2 className="text-lg font-semibold text-slate-900">Enquiry history</h2>
        <p className="text-sm text-slate-600">Saved BillAvenue deposit enquiry runs — click a row to reopen the report.</p>
        {historyLoading && history.length === 0 ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="border-b border-slate-200 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">When</th>
                  <th className="px-3 py-2">Range</th>
                  <th className="px-3 py-2">Agents</th>
                  <th className="px-3 py-2">Balance</th>
                  <th className="px-3 py-2">Txns</th>
                  <th className="px-3 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {history.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-3 py-8 text-center text-slate-500">
                      No enquiries yet. Run one above.
                    </td>
                  </tr>
                ) : (
                  history.map((row) => (
                    <tr
                      key={row.id}
                      className="cursor-pointer border-b border-slate-100 hover:bg-slate-50"
                      onClick={() => openHistoryRow(row.id)}
                    >
                      <td className="px-3 py-2 whitespace-nowrap">{formatWhen(row.created_at)}</td>
                      <td className="px-3 py-2 whitespace-nowrap">
                        {row.from_date} → {row.to_date}
                        {row.trans_type ? ` · ${row.trans_type}` : ''}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs max-w-[180px] truncate" title={(row.agents || []).join(', ')}>
                        {(row.agents || []).join(', ') || '—'}
                      </td>
                      <td className="px-3 py-2 whitespace-nowrap">{formatCurrency(row.current_balance)}</td>
                      <td className="px-3 py-2">{row.transaction_count}</td>
                      <td className="px-3 py-2">
                        <Badge variant={row.status === 'SUCCESS' ? 'success' : 'error'} size="sm">
                          {row.status || '—'}
                        </Badge>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
        {pagination.total_pages > 1 && (
          <div className="flex items-center justify-between text-sm text-slate-600">
            <span>
              Page {pagination.page} of {pagination.total_pages}
            </span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                size="sm"
                disabled={historyLoading || pagination.page <= 1}
                onClick={() => loadHistory(pagination.page - 1)}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={historyLoading || pagination.page >= pagination.total_pages}
                onClick={() => loadHistory(pagination.page + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </Card>

      <FeedbackModal
        open={feedback.open}
        title={feedback.title}
        description={feedback.description}
        onClose={() => setFeedback((s) => ({ ...s, open: false }))}
      />
    </div>
  );
};

export default BbpsOpsConsole;
