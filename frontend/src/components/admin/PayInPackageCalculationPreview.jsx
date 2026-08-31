import React, { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import LoadingSpinner from '../common/LoadingSpinner';
import { firstErrorMessage } from './gatewayAdminShared';
import { FaArrowLeft, FaCalculator } from 'react-icons/fa6';

const PayInPackageCalculationPreview = () => {
  const { id } = useParams();
  const [pkg, setPkg] = useState(null);
  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [amount, setAmount] = useState('100000');
  const [railKey, setRailKey] = useState('');
  const [payerQuery, setPayerQuery] = useState('');
  const [payerUserId, setPayerUserId] = useState('');
  const [userHits, setUserHits] = useState([]);
  const [result, setResult] = useState(null);
  const [activeScenarioId, setActiveScenarioId] = useState('generic');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const res = await adminAPI.getPayInPackage(id);
      setLoading(false);
      if (res.success) {
        setPkg(res.data);
        const gws = res.data?.package_gateways || [];
        const qrs = res.data?.package_qr_accounts || [];
        const defGw = gws.find((g) => g.is_default) || gws[0];
        const defQr = qrs.find((q) => q.is_default) || qrs[0];
        if (defGw) setRailKey(`gw:${defGw.id}`);
        else if (defQr) setRailKey(`qr:${defQr.id}`);
      }
    };
    load();
  }, [id]);

  const rails = useMemo(() => {
    if (!pkg) return [];
    const out = [];
    (pkg.package_gateways || []).forEach((g) => {
      out.push({
        key: `gw:${g.id}`,
        label: `${g.name} (gateway)`,
        gateway_id: g.id,
        qr_account_id: null,
        fee: g.effective_gateway_fee_pct || g.gateway_fee_pct,
        min: g.charge_rate,
      });
    });
    (pkg.package_qr_accounts || []).forEach((q) => {
      out.push({
        key: `qr:${q.id}`,
        label: `${q.name} (QR)`,
        gateway_id: null,
        qr_account_id: q.id,
        fee: q.effective_gateway_fee_pct || q.gateway_fee_pct,
        min: q.charge_rate,
      });
    });
    return out;
  }, [pkg]);

  const selectedRail = rails.find((r) => r.key === railKey) || null;

  const searchUsers = async () => {
    if (!payerQuery.trim()) {
      setUserHits([]);
      return;
    }
    const res = await adminAPI.listUsers({ search: payerQuery.trim(), page_size: 8 });
    if (res.success) {
      setUserHits(res.data?.results || res.data || []);
    }
  };

  const runPreview = async () => {
    setPreviewLoading(true);
    const body = {
      amount,
      payer_user_id: payerUserId ? Number(payerUserId) : null,
      gateway_id: selectedRail?.gateway_id || null,
      qr_account_id: selectedRail?.qr_account_id || null,
    };
    const res = await adminAPI.previewPayInPackage(id, body);
    setPreviewLoading(false);
    if (res.success) {
      setResult(res.data);
      if (res.data?.scenarios?.length) {
        const preferred = res.data.scenarios.find((s) => s.id === 'live_payer') || res.data.scenarios[0];
        setActiveScenarioId(preferred.id);
      }
    }
    else alert(firstErrorMessage(res, 'Preview failed'));
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  if (!pkg) {
    return (
      <Card>
        <p className="text-sm text-slate-600">Package not found.</p>
        <Link to="/admin/pay-in-packages" className="text-blue-700 text-sm font-semibold mt-2 inline-block">
          Back to packages
        </Link>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to="/admin/pay-in-packages"
            className="inline-flex items-center gap-1 text-sm font-semibold text-slate-600 dark:text-slate-400 hover:text-slate-900"
          >
            <FaArrowLeft size={12} /> Back to packages
          </Link>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100 mt-2">
            Calculation preview: {pkg.display_name}
          </h1>
          <p className="text-sm text-slate-500">Code: {pkg.code} · Provider: {pkg.provider}</p>
        </div>
        <Button onClick={runPreview} loading={previewLoading} icon={FaCalculator} iconPosition="left">
          Run preview
        </Button>
      </header>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-1 space-y-4" shadow="sm">
          <Input label="Test amount (INR)" type="number" value={amount} onChange={(e) => setAmount(e.target.value)} />
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-300">
            Payment rail
            <select
              className="mt-1 w-full rounded-lg border border-slate-300 dark:border-slate-600 px-3 py-2 text-sm"
              value={railKey}
              onChange={(e) => setRailKey(e.target.value)}
            >
              {rails.map((r) => (
                <option key={r.key} value={r.key}>
                  {r.label}
                </option>
              ))}
            </select>
          </label>
          {selectedRail ? (
            <p className="text-xs text-slate-500">
              Rail fee {selectedRail.fee}% · Min {selectedRail.min ?? 0}%
            </p>
          ) : null}
          <div>
            <Input
              label="Payer user (optional)"
              value={payerQuery}
              onChange={(e) => setPayerQuery(e.target.value)}
              placeholder="Search name, phone, user id"
            />
            <Button type="button" size="sm" variant="secondary" className="mt-2" onClick={searchUsers}>
              Search users
            </Button>
            {userHits.length > 0 ? (
              <ul className="mt-2 max-h-40 overflow-auto rounded border border-slate-200 dark:border-slate-700 text-sm">
                {userHits.map((u) => (
                  <li key={u.id}>
                    <button
                      type="button"
                      className={`w-full text-left px-3 py-2 hover:bg-slate-50 dark:hover:bg-slate-800 ${payerUserId === String(u.id) ? 'bg-indigo-50 dark:bg-indigo-950/40' : ''}`}
                      onClick={() => setPayerUserId(String(u.id))}
                    >
                      {u.profile?.full_name || u.email || u.phone} · {u.role} · #{u.id}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
            {payerUserId ? (
              <p className="text-xs text-emerald-700 mt-1">Selected payer user id: {payerUserId}</p>
            ) : (
              <p className="text-xs text-slate-500 mt-1">Leave empty for generic (no hierarchy roll-up).</p>
            )}
          </div>
        </Card>

        <Card className="lg:col-span-2" shadow="sm" title="Fee breakdown">
          {!result ? (
            <p className="text-sm text-slate-500">Run preview to see commission lines and net credit.</p>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                <div className="rounded-lg bg-slate-50 dark:bg-slate-800/50 p-3">
                  <p className="text-xs uppercase text-slate-500">Gross</p>
                  <p className="text-lg font-bold">₹{result.breakdown?.gross || amount}</p>
                </div>
                <div className="rounded-lg bg-rose-50 dark:bg-rose-950/30 p-3">
                  <p className="text-xs uppercase text-rose-700">Total deduction</p>
                  <p className="text-lg font-bold">₹{result.total_deduction}</p>
                </div>
                <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/30 p-3">
                  <p className="text-xs uppercase text-emerald-700">Net credit</p>
                  <p className="text-lg font-bold">₹{result.net_credit}</p>
                </div>
              </div>
              <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700">
                <table className="w-full text-sm">
                  <thead className="bg-slate-50 dark:bg-slate-800 text-xs uppercase text-slate-500">
                    <tr>
                      <th className="p-2 text-left">Line</th>
                      <th className="p-2 text-right">%</th>
                      <th className="p-2 text-right">Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(result.lines || []).map((line) => (
                      <tr key={line.key} className="border-t border-slate-100 dark:border-slate-800">
                        <td className="p-2">
                          <div>{line.label}</div>
                          {line.note ? <p className="text-xs text-slate-500 mt-0.5">{line.note}</p> : null}
                        </td>
                        <td className="p-2 text-right tabular-nums">{line.pct}</td>
                        <td className="p-2 text-right tabular-nums">₹{line.amount}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </Card>
      </div>

      {result?.scenarios?.length ? (
        <Card shadow="sm" title="Hierarchy scenarios">
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
            Compare how commission rolls up when upline roles are missing or when admin adds a retailer directly.
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            {result.scenarios.map((scenario) => (
              <button
                key={scenario.id}
                type="button"
                onClick={() => setActiveScenarioId(scenario.id)}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold border transition-colors ${
                  activeScenarioId === scenario.id
                    ? 'bg-indigo-600 text-white border-indigo-600'
                    : 'bg-white dark:bg-slate-900 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700 hover:border-indigo-300'
                }`}
              >
                {scenario.title}
              </button>
            ))}
          </div>
          {(() => {
            const scenario = result.scenarios.find((s) => s.id === activeScenarioId) || result.scenarios[0];
            if (!scenario) return null;
            return (
              <div className="space-y-4">
                <p className="text-sm text-slate-700 dark:text-slate-300">{scenario.description}</p>
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="rounded-lg bg-rose-50 dark:bg-rose-950/30 p-3">
                    <p className="text-xs uppercase text-rose-700">Deduction</p>
                    <p className="text-lg font-bold">₹{scenario.total_deduction}</p>
                  </div>
                  <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/30 p-3">
                    <p className="text-xs uppercase text-emerald-700">Net credit</p>
                    <p className="text-lg font-bold">₹{scenario.net_credit}</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 dark:bg-slate-800/50 p-3">
                    <p className="text-xs uppercase text-slate-500">Absorbed to Admin</p>
                    <p className="text-lg font-bold">₹{scenario.hierarchy?.absorbed_to_admin || '0.00'}</p>
                  </div>
                </div>
                {scenario.hierarchy?.rollup_steps?.length ? (
                  <div className="rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50/50 dark:bg-amber-950/30 p-3">
                    <p className="text-xs font-semibold uppercase text-amber-800 dark:text-amber-300 mb-2">
                      Roll-up steps
                    </p>
                    <ol className="text-sm space-y-1 list-decimal list-inside text-amber-900 dark:text-amber-200">
                      {scenario.hierarchy.rollup_steps.map((step, i) => (
                        <li key={`${scenario.id}-step-${i}`}>{step}</li>
                      ))}
                    </ol>
                  </div>
                ) : null}
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="overflow-x-auto rounded-lg border">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 dark:bg-slate-800 text-xs uppercase text-slate-500">
                        <tr>
                          <th className="p-2 text-left">Line</th>
                          <th className="p-2 text-right">%</th>
                          <th className="p-2 text-right">Amount</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(scenario.lines || []).map((line) => (
                          <tr key={`${scenario.id}-${line.key}`} className="border-t">
                            <td className="p-2">
                              {line.label}
                              {line.note ? <p className="text-xs text-slate-500 mt-0.5">{line.note}</p> : null}
                            </td>
                            <td className="p-2 text-right tabular-nums">{line.pct}</td>
                            <td className="p-2 text-right tabular-nums">₹{line.amount}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div>
                    <p className="text-xs font-semibold uppercase text-slate-500 mb-2">Role payouts</p>
                    <ul className="text-sm space-y-2">
                      {['Super Distributor', 'Master Distributor', 'Distributor'].map((role) => {
                        const a = scenario.hierarchy?.assignments?.[role];
                        let label = '— (rolls up)';
                        if (a?.status === 'paid' || a?.status === 'theoretical') {
                          label = `${a.name || role} · ₹${a.amount}`;
                        } else if (a?.status === 'rolls_up') {
                          label = '— (rolls up)';
                        }
                        return (
                          <li key={role} className="flex justify-between gap-2 border-b pb-1">
                            <span>{role}</span>
                            <span className="text-right text-slate-600 dark:text-slate-400">{label}</span>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </div>
              </div>
            );
          })()}
        </Card>
      ) : null}

      {result?.hierarchy ? (
        <Card shadow="sm" title="Hierarchy commission">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500 mb-2">Payer</p>
              {result.hierarchy.payer ? (
                <p className="text-sm">
                  {result.hierarchy.payer.name} · {result.hierarchy.payer.role} (#{result.hierarchy.payer.id})
                </p>
              ) : (
                <p className="text-sm text-slate-500">No payer selected — full SD/MD/D slices shown.</p>
              )}
              {result.hierarchy.upline_chain?.length ? (
                <div className="mt-3">
                  <p className="text-xs font-semibold uppercase text-slate-500 mb-1">Upline chain</p>
                  <ol className="text-sm space-y-1 list-decimal list-inside">
                    {result.hierarchy.upline_chain.map((u) => (
                      <li key={u.id}>
                        {u.name} · {u.role}
                      </li>
                    ))}
                  </ol>
                </div>
              ) : null}
            </div>
            <div>
              <p className="text-xs font-semibold uppercase text-slate-500 mb-2">Role payouts</p>
              <ul className="text-sm space-y-2">
                {['Super Distributor', 'Master Distributor', 'Distributor'].map((role) => {
                  const a = result.hierarchy.assignments?.[role];
                  return (
                    <li key={role} className="flex justify-between gap-2 border-b border-slate-100 dark:border-slate-800 pb-1">
                      <span>{role}</span>
                      <span className="text-right">
                        {a ? `${a.name} · ₹${a.amount}` : <span className="text-slate-400">— (rolls up)</span>}
                      </span>
                    </li>
                  );
                })}
              </ul>
              <p className="text-xs text-slate-500 mt-3">
                Absorbed to Admin: ₹{result.hierarchy.absorbed_to_admin || '0.00'}
                {result.hierarchy.hierarchy_adjusted ? ' (hierarchy adjusted)' : ''}
              </p>
            </div>
          </div>
        </Card>
      ) : null}

      {result?.rail_comparison?.length ? (
        <Card shadow="sm" title="Rail comparison (same amount)">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 dark:bg-slate-800 text-xs uppercase text-slate-500">
                <tr>
                  <th className="p-2 text-left">Rail</th>
                  <th className="p-2 text-right">Gateway fee %</th>
                  <th className="p-2 text-right">Deduction</th>
                  <th className="p-2 text-right">Net credit</th>
                </tr>
              </thead>
              <tbody>
                {result.rail_comparison.map((row) => (
                  <tr key={`${row.rail_type}-${row.id}`} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="p-2">
                      {row.name}{' '}
                      <span className="text-xs text-slate-500">({row.rail_type})</span>
                    </td>
                    <td className="p-2 text-right">{row.gateway_fee_pct}</td>
                    <td className="p-2 text-right">₹{row.total_deduction}</td>
                    <td className="p-2 text-right font-semibold">₹{row.net_credit}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : null}
    </div>
  );
};

export default PayInPackageCalculationPreview;
