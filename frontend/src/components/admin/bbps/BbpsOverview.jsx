import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FaArrowsRotate,
  FaDatabase,
  FaEye,
  FaEyeSlash,
  FaHeartPulse,
  FaWallet,
} from 'react-icons/fa6';
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { bbpsAPI, billAvenueAdminAPI } from '../../../services/api';
import { formatCurrency } from '../../../utils/formatters';
import { useTheme } from '../../../context/ThemeContext';
import { getChartTheme } from '../../../utils/chartTheme';
import Badge from '../../common/Badge';
import Card from '../../common/Card';
import LoadingSpinner from '../../common/LoadingSpinner';
import StatCard from '../../common/StatCard';

const DONUT_COLORS = [
  '#2563eb', '#0ea5e9', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#14b8a6', '#f97316', '#64748b', '#a3e635',
];

function formatWhen(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('en-IN', {
      day: '2-digit',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

const BbpsOverview = () => {
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const chart = getChartTheme(isDark);
  const [loading, setLoading] = useState(true);
  const [catData, setCatData] = useState(null);
  const [quota, setQuota] = useState(null);
  const [floatData, setFloatData] = useState(null);
  const [obs, setObs] = useState(null);
  const [syncHistory, setSyncHistory] = useState([]);
  const [mdmJobs, setMdmJobs] = useState([]);
  const [deposits, setDeposits] = useState([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      const [cats, q, flt, ob, hist, jobs, dep] = await Promise.all([
        billAvenueAdminAPI.getBillerCategoryCounts(),
        bbpsAPI.getSyncUsageToday(),
        bbpsAPI.getProviderFloat({ page_size: 5 }),
        billAvenueAdminAPI.getGovernanceObservability(),
        bbpsAPI.getSyncUsageHistory(),
        bbpsAPI.listMdmImportJobs(),
        bbpsAPI.getDepositEnquiryHistory({ page_size: 5 }),
      ]);
      if (cancelled) return;
      if (cats.success) setCatData(cats.data);
      if (q.success) setQuota(q.data);
      if (flt.success) setFloatData(flt.data);
      if (ob.success) setObs(ob.data);
      if (hist.success) setSyncHistory(hist.data?.history || []);
      if (jobs.success) setMdmJobs((jobs.data?.jobs || []).slice(0, 5));
      if (dep.success) setDeposits(dep.data?.results || []);
      setLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const donutData = useMemo(() => {
    const cats = catData?.categories || [];
    const top = cats.slice(0, 9);
    const rest = cats.slice(9);
    const restTotal = rest.reduce((acc, c) => acc + (c.total || 0), 0);
    const rows = top.map((c) => ({ name: c.category, value: c.total }));
    if (restTotal > 0) rows.push({ name: 'Other', value: restTotal });
    return rows;
  }, [catData]);

  const sparkData = useMemo(() => {
    const rows = (syncHistory || [])
      .slice(0, 14)
      .map((r) => ({
        date: String(r.usage_date || '').slice(5),
        calls: Number(r.call_count ?? r.calls ?? 0),
      }))
      .reverse();
    return rows;
  }, [syncHistory]);

  const apiHealth = useMemo(() => {
    const counts = obs?.endpoint_counts || {};
    return Object.entries(counts)
      .map(([name, v]) => ({
        name,
        total: Number(v?.total || 0),
        failed: Number(v?.failed || 0),
        rate: v?.total ? (v.failed / v.total) * 100 : 0,
      }))
      .sort((a, b) => b.total - a.total);
  }, [obs]);

  if (loading) {
    return (
      <div className="flex justify-center py-24">
        <LoadingSpinner size="lg" />
      </div>
    );
  }

  const totals = catData?.totals || {};
  const flt = floatData?.float || {};
  const floatNegative = Boolean(flt.is_negative);
  const floatLow = Boolean(flt.is_low_balance);
  const ledger = floatData?.ledger?.results || [];

  return (
    <div className="space-y-5">
      {/* KPI row */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Catalog billers"
          icon={FaDatabase}
          value={totals.total ?? '—'}
          sub={`${(catData?.catalog_environment || '').toUpperCase()} catalog · PROD ${catData?.catalog_counts?.prod ?? 0} / UAT ${catData?.catalog_counts?.uat ?? 0}`}
          onClick={() => navigate('/admin/bbps/directory')}
        />
        <StatCard
          label="Visibility"
          icon={totals.hidden ? FaEyeSlash : FaEye}
          value={`${totals.visible ?? 0} visible`}
          sub={`${totals.hidden ?? 0} hidden from partners`}
          tone={totals.hidden ? 'warning' : 'success'}
          onClick={() => navigate('/admin/bbps/directory')}
        />
        <StatCard
          label="Sync quota today"
          icon={FaArrowsRotate}
          value={`${quota?.used_calls_today ?? 0}/${quota?.max_calls_per_day ?? 15}`}
          sub={`${quota?.remaining_calls_today ?? '—'} calls remaining (${(quota?.environment || '').toUpperCase()})`}
          tone={(quota?.remaining_calls_today ?? 1) <= 0 ? 'danger' : 'default'}
          onClick={() => navigate('/admin/bbps/catalog')}
        />
        <StatCard
          label="Provider float"
          icon={FaWallet}
          value={formatCurrency(flt.balance ?? 0)}
          sub={
            flt.enforcement_enabled
              ? 'Payment gate enforced'
              : 'Gate disabled — payments unchecked'
          }
          tone={floatNegative ? 'danger' : floatLow ? 'warning' : 'success'}
          chip={floatNegative ? 'Negative' : floatLow ? 'Low' : 'OK'}
          onClick={() => navigate('/admin/bbps/float')}
        />
      </div>

      <div className="grid gap-5 xl:grid-cols-3">
        {/* Category donut */}
        <Card title="Billers by category" subtitle="Click a category in the Directory to drill in" padding="md">
          {donutData.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">No billers in this catalog yet.</p>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <div className="h-52 w-full">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie
                      data={donutData}
                      dataKey="value"
                      nameKey="name"
                      innerRadius="55%"
                      outerRadius="85%"
                      paddingAngle={2}
                    >
                      {donutData.map((entry, idx) => (
                        <Cell key={entry.name} fill={DONUT_COLORS[idx % DONUT_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(v, n) => [`${v} billers`, n]}
                      contentStyle={chart.tooltip}
                      itemStyle={{ color: chart.tooltip.color }}
                      labelStyle={{ color: chart.tooltip.color }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="grid w-full grid-cols-2 gap-x-3 gap-y-1">
                {donutData.map((entry, idx) => (
                  <button
                    key={entry.name}
                    type="button"
                    onClick={() =>
                      entry.name !== 'Other' &&
                      navigate(`/admin/bbps/directory?category=${encodeURIComponent(entry.name)}`)
                    }
                    className="flex items-center gap-1.5 truncate text-left text-xs text-slate-600 dark:text-slate-400 hover:text-blue-700 dark:hover:text-blue-200"
                    title={entry.name}
                  >
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ backgroundColor: DONUT_COLORS[idx % DONUT_COLORS.length] }}
                    />
                    <span className="truncate">{entry.name}</span>
                    <span className="ml-auto font-semibold text-slate-800 dark:text-slate-200">{entry.value}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </Card>

        {/* API health */}
        <Card
          title="API health"
          subtitle={`Last 300 BillAvenue calls · ${obs?.awaited_count ?? 0} awaited · ${obs?.complaint_pending_count ?? 0} open complaints`}
          padding="md"
        >
          {apiHealth.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">No recent API activity.</p>
          ) : (
            <div className="space-y-2.5">
              {apiHealth.slice(0, 8).map((row) => {
                const tone =
                  row.rate >= 50 ? 'bg-red-500' : row.rate >= 15 ? 'bg-amber-500' : 'bg-emerald-500';
                return (
                  <div key={row.name}>
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-medium capitalize text-slate-700 dark:text-slate-300">
                        {row.name.replace(/_/g, ' ')}
                      </span>
                      <span className="text-slate-500 dark:text-slate-400">
                        {row.failed > 0 ? `${row.failed} failed / ` : ''}
                        {row.total} calls
                      </span>
                    </div>
                    <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800">
                      <div
                        className={`h-full rounded-full ${tone}`}
                        style={{ width: `${Math.max(4, 100 - row.rate)}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </Card>

        {/* Sync usage sparkline */}
        <Card title="MDM sync usage" subtitle="Daily sync calls (latest 14 entries)" padding="md">
          {sparkData.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-500 dark:text-slate-400">No sync history yet.</p>
          ) : (
            <div className="h-40 w-full">
              <ResponsiveContainer>
                <AreaChart data={sparkData} margin={{ top: 6, right: 6, bottom: 0, left: 6 }}>
                  <defs>
                    <linearGradient id="syncFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#2563eb" stopOpacity={0.25} />
                      <stop offset="100%" stopColor="#2563eb" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <Tooltip
                    formatter={(v) => [`${v} calls`, 'Sync']}
                    labelFormatter={(l) => `Date ${l}`}
                    contentStyle={chart.tooltip}
                    itemStyle={{ color: chart.tooltip.color }}
                    labelStyle={{ color: chart.tooltip.color }}
                    cursor={{ stroke: chart.axisLine }}
                  />
                  <Area
                    type="monotone"
                    dataKey="calls"
                    stroke="#2563eb"
                    strokeWidth={2}
                    fill="url(#syncFill)"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
          <div className="mt-3 flex items-center justify-between border-t border-slate-100 dark:border-slate-800 pt-3 text-xs text-slate-500 dark:text-slate-400">
            <span>
              Last sync: {quota?.last_sync_at ? formatWhen(quota.last_sync_at) : '—'}
            </span>
            <Badge variant={quota?.last_sync_result === 'failed' ? 'error' : 'success'} size="sm">
              {quota?.last_sync_result || 'idle'}
            </Badge>
          </div>
        </Card>
      </div>

      {/* Activity feed */}
      <div className="grid gap-5 xl:grid-cols-3">
        <Card title="Recent MDM imports" padding="md">
          {mdmJobs.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">No import jobs.</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {mdmJobs.map((j) => (
                <li key={j.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-slate-800 dark:text-slate-200">
                      #{j.id} {j.original_filename || 'Import'}
                    </div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {(j.environment || '').toUpperCase()} · {j.synced_ids ?? 0}/{j.total_ids ?? 0} synced
                    </div>
                  </div>
                  <Badge
                    size="sm"
                    variant={
                      j.status === 'completed'
                        ? 'success'
                        : ['failed', 'cancelled'].includes(j.status)
                          ? 'error'
                          : 'warning'
                    }
                  >
                    {j.status}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Recent deposit enquiries" padding="md">
          {deposits.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">No enquiries yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {deposits.map((d) => (
                <li key={d.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                  <div className="min-w-0">
                    <div className="font-medium text-slate-800 dark:text-slate-200">{formatCurrency(d.current_balance)}</div>
                    <div className="text-xs text-slate-500 dark:text-slate-400">
                      {d.from_date} → {d.to_date} · {d.transaction_count} txns
                    </div>
                  </div>
                  <Badge size="sm" variant={d.status === 'SUCCESS' ? 'success' : 'error'}>
                    {d.status}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Recent float activity" padding="md">
          {ledger.length === 0 ? (
            <p className="py-6 text-center text-sm text-slate-500 dark:text-slate-400">No float ledger entries.</p>
          ) : (
            <ul className="divide-y divide-slate-100 dark:divide-slate-800">
              {ledger.map((e) => (
                <li key={e.id} className="flex items-center justify-between gap-2 py-2 text-sm">
                  <div className="min-w-0">
                    <div className="font-medium text-slate-800 dark:text-slate-200">{formatCurrency(e.amount)}</div>
                    <div className="truncate text-xs text-slate-500 dark:text-slate-400">
                      {formatWhen(e.created_at)} · {e.remarks || e.service_id || '—'}
                    </div>
                  </div>
                  <Badge
                    size="sm"
                    variant={
                      e.entry_type === 'AUTO_DEBIT'
                        ? 'error'
                        : e.entry_type === 'AUTO_CREDIT'
                          ? 'success'
                          : 'info'
                    }
                  >
                    {e.entry_type === 'MANUAL_SET'
                      ? 'Manual set'
                      : e.entry_type === 'AUTO_DEBIT'
                        ? 'Debit'
                        : 'Credit'}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
        <FaHeartPulse />
        Data refreshes on page load. Open individual modules from the left navigation for live operations.
      </div>
    </div>
  );
};

export default BbpsOverview;
