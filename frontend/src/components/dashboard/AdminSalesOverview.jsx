import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ResponsiveContainer,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  PieChart,
  Pie,
  Cell,
} from 'recharts';
import {
  HiOutlineShoppingCart,
  HiOutlineCurrencyRupee,
  HiOutlineChartBar,
  HiArrowRight,
} from 'react-icons/hi2';
import { reportsAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { todayIsoDate } from '../../utils/reportDate';
import { useTheme } from '../../context/ThemeContext';
import { getChartTheme } from '../../utils/chartTheme';
import ReportDateRange from '../common/ReportDateRange';

const GATEWAY_COLORS = ['#2563eb', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444', '#64748b', '#06b6d4'];

function weekRange() {
  const to = todayIsoDate();
  const d = new Date(`${to}T12:00:00`);
  d.setDate(d.getDate() - 6);
  const from = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { dateFrom: from, dateTo: to };
}

function periodDates(preset) {
  const today = todayIsoDate();
  if (preset === 'weekly') return weekRange();
  if (preset === 'monthly') {
    const [y, m] = today.split('-');
    return { dateFrom: `${y}-${m}-01`, dateTo: today };
  }
  return { dateFrom: today, dateTo: today };
}

function shortAxis(v) {
  if (v >= 1e7) return `${(v / 1e7).toFixed(1)}Cr`;
  if (v >= 1e5) return `${(v / 1e5).toFixed(1)}L`;
  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}K`;
  return `${Math.round(v)}`;
}

function formatPeriodLabel(period) {
  const s = String(period || '');
  // YYYY-MM-DD → 13 Sep
  const m = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (m) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    return `${Number(m[3])} ${months[Number(m[2]) - 1]}`;
  }
  return s;
}

const ChartTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-lg dark:border-slate-700 dark:bg-slate-800">
      <p className="font-semibold text-slate-800 dark:text-slate-100">{label}</p>
      <ul className="mt-1 space-y-0.5">
        {payload.map((p) => (
          <li key={p.dataKey} className="text-slate-600 dark:text-slate-300">
            <span style={{ color: p.color }}>{p.name}: </span>
            {formatCurrency(Number(p.value) || 0)}
          </li>
        ))}
      </ul>
    </div>
  );
};

const KpiCard = ({ icon: Icon, tone, label, value, loading }) => {
  const tones = {
    blue: 'bg-blue-50 text-blue-600 dark:bg-blue-950/50 dark:text-blue-300',
    amber: 'bg-amber-50 text-amber-600 dark:bg-amber-950/50 dark:text-amber-300',
    green: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-300',
  };
  return (
    <div className="flex items-center gap-3 rounded-xl border border-slate-100 bg-slate-50/80 px-3 py-3 dark:border-slate-800 dark:bg-slate-950/40">
      <span className={`inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${tones[tone]}`}>
        <Icon className="h-5 w-5" aria-hidden />
      </span>
      <div className="min-w-0">
        <p className={`text-base font-bold tabular-nums tracking-tight text-slate-900 dark:text-slate-100 ${loading ? 'animate-pulse' : ''}`}>
          {loading ? '—' : formatCurrency(value)}
        </p>
        <p className="text-[11px] font-medium text-slate-500 dark:text-slate-400">{label}</p>
      </div>
    </div>
  );
};

/**
 * Admin / Super Admin sales widgets matching the ops reference:
 * Sales & Profit (KPI + bar/line) | Sales by Gateway (donut + legend).
 */
const AdminSalesOverview = () => {
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const chart = getChartTheme(isDark);

  const [preset, setPreset] = useState('weekly');
  const [applied, setApplied] = useState(() => periodDates('weekly'));
  const [draft, setDraft] = useState(() => periodDates('weekly'));
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [totals, setTotals] = useState({
    payin_sales: '0',
    payin_charges: '0',
    platform_profit: '0',
  });

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      const res = await reportsAPI.getAnalyticsSummary({
        interval: 'daily',
        date_from: applied.dateFrom,
        date_to: applied.dateTo,
      });
      if (!mounted) return;
      if (res.success) {
        setRows(res.data?.rows || []);
        setTotals(
          res.data?.totals || {
            payin_sales: '0',
            payin_charges: '0',
            platform_profit: '0',
          }
        );
      } else {
        setRows([]);
        setTotals({ payin_sales: '0', payin_charges: '0', platform_profit: '0' });
      }
      setLoading(false);
    };
    load();
    return () => {
      mounted = false;
    };
  }, [applied]);

  const onPreset = (value) => {
    setPreset(value);
    if (value === 'custom') {
      setDraft(applied);
      return;
    }
    const range = periodDates(value);
    setDraft(range);
    setApplied(range);
  };

  const applyCustomRange = ({ dateFrom, dateTo }) => {
    const next = {
      dateFrom: dateFrom || applied.dateFrom,
      dateTo: dateTo || applied.dateTo,
    };
    setDraft(next);
    setApplied(next);
    setPreset('custom');
  };

  const trendData = useMemo(() => {
    const m = {};
    rows.forEach((r) => {
      const p = String(r.period || '');
      if (!m[p]) m[p] = { period: p, label: formatPeriodLabel(p), sales: 0, profit: 0 };
      m[p].sales += parseFloat(r.payin_sales || 0);
      m[p].profit += parseFloat(r.platform_profit || 0);
    });
    return Object.values(m).sort((a, b) => String(a.period).localeCompare(String(b.period)));
  }, [rows]);

  const gatewayPie = useMemo(() => {
    const m = {};
    rows.forEach((r) => {
      const g = (r.gateway || 'Unknown').trim() || 'Unknown';
      m[g] = (m[g] || 0) + parseFloat(r.payin_sales || 0);
    });
    const entries = Object.entries(m)
      .map(([name, value]) => ({ name, value }))
      .filter((e) => e.value > 0)
      .sort((a, b) => b.value - a.value);
    const total = entries.reduce((s, e) => s + e.value, 0);
    const top = entries.slice(0, 5);
    const rest = entries.slice(5);
    const restSum = rest.reduce((s, e) => s + e.value, 0);
    const list = restSum > 0 ? [...top, { name: 'Others', value: restSum }] : top;
    return list.map((e) => ({
      ...e,
      pct: total > 0 ? Math.round((e.value / total) * 100) : 0,
    }));
  }, [rows]);

  const salesTotal = parseFloat(totals.payin_sales || 0);
  const chargesTotal = parseFloat(totals.payin_charges || 0);
  const profitTotal = parseFloat(totals.platform_profit || 0);

  const PeriodSelect = ({ id }) => (
    <select
      id={id}
      value={preset}
      onChange={(e) => onPreset(e.target.value)}
      className="rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-semibold text-slate-700 shadow-sm dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
    >
      <option value="daily">Today</option>
      <option value="weekly">This Week</option>
      <option value="monthly">Month to date</option>
      <option value="custom">Custom date</option>
    </select>
  );

  return (
    <div className="space-y-3">
      {preset === 'custom' ? (
        <div className="rounded-2xl border border-slate-200/90 bg-white p-3 shadow-sm dark:border-slate-700/90 dark:bg-slate-900 sm:p-4">
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-400">
            Custom date range
            <span className="ml-2 font-medium normal-case tracking-normal text-slate-500">
              ({applied.dateFrom} → {applied.dateTo})
            </span>
          </p>
          <ReportDateRange
            idPrefix="admin-sales"
            compact
            showApply
            applyInline
            applyLabel="Apply"
            fromLabel="From"
            toLabel="To"
            dateFrom={draft.dateFrom}
            dateTo={draft.dateTo}
            onChange={({ dateFrom, dateTo }) => setDraft({ dateFrom, dateTo })}
            onApply={applyCustomRange}
          />
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.9fr)]">
      {/* Sales & Profit Overview */}
      <section className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm dark:border-slate-700/90 dark:bg-slate-900 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Sales &amp; Profit Overview
          </h2>
          <PeriodSelect id="sales-profit-period" />
        </div>

        <div className="mb-5 grid grid-cols-1 gap-2.5 sm:grid-cols-3">
          <KpiCard
            icon={HiOutlineShoppingCart}
            tone="blue"
            label="Total Sales"
            value={salesTotal}
            loading={loading}
          />
          <KpiCard
            icon={HiOutlineCurrencyRupee}
            tone="amber"
            label="Total Charges"
            value={chargesTotal}
            loading={loading}
          />
          <KpiCard
            icon={HiOutlineChartBar}
            tone="green"
            label="Platform Profit"
            value={profitTotal}
            loading={loading}
          />
        </div>

        <div className="h-[260px] w-full sm:h-[280px]">
          {loading ? (
            <div className="h-full animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
          ) : trendData.length === 0 ? (
            <div className="flex h-full items-center justify-center rounded-xl border border-dashed border-slate-200 text-sm text-slate-500 dark:border-slate-700">
              No sales data for this period.
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={trendData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="adminSalesBar" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.95} />
                    <stop offset="100%" stopColor="#2563eb" stopOpacity={0.75} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke={chart.grid} vertical={false} />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: chart.axis }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  yAxisId="sales"
                  tickFormatter={shortAxis}
                  tick={{ fontSize: 11, fill: chart.axis }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <YAxis
                  yAxisId="profit"
                  orientation="right"
                  tickFormatter={shortAxis}
                  tick={{ fontSize: 11, fill: chart.axis }}
                  axisLine={false}
                  tickLine={false}
                  width={44}
                />
                <Tooltip content={<ChartTooltip />} />
                <Legend
                  verticalAlign="top"
                  height={28}
                  formatter={(value) => (
                    <span className="text-xs text-slate-600 dark:text-slate-300">{value}</span>
                  )}
                />
                <Bar
                  yAxisId="sales"
                  dataKey="sales"
                  name="Sales (₹)"
                  fill="url(#adminSalesBar)"
                  radius={[6, 6, 0, 0]}
                  maxBarSize={36}
                />
                <Line
                  yAxisId="profit"
                  type="monotone"
                  dataKey="profit"
                  name="Platform Profit (₹)"
                  stroke="#10b981"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#10b981', strokeWidth: 0 }}
                  activeDot={{ r: 6 }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </section>

      {/* Sales by Gateway */}
      <section className="flex flex-col rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm dark:border-slate-700/90 dark:bg-slate-900 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <h2 className="text-base font-semibold text-slate-900 dark:text-slate-100">
            Sales by Gateway
          </h2>
          <PeriodSelect id="sales-gateway-period" />
        </div>

        {loading ? (
          <div className="flex flex-1 animate-pulse flex-col gap-3">
            <div className="mx-auto h-44 w-44 rounded-full bg-slate-100 dark:bg-slate-800" />
            <div className="h-24 rounded-xl bg-slate-100 dark:bg-slate-800" />
          </div>
        ) : gatewayPie.length === 0 ? (
          <div className="flex flex-1 items-center justify-center rounded-xl border border-dashed border-slate-200 text-sm text-slate-500 dark:border-slate-700">
            No gateway sales for this period.
          </div>
        ) : (
          <>
            <div className="relative mx-auto h-44 w-44 shrink-0">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={gatewayPie}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={52}
                    outerRadius={72}
                    paddingAngle={2}
                    stroke="none"
                  >
                    {gatewayPie.map((entry, i) => (
                      <Cell key={entry.name} fill={GATEWAY_COLORS[i % GATEWAY_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v) => formatCurrency(Number(v) || 0)}
                    contentStyle={{
                      borderRadius: 12,
                      border: '1px solid #e2e8f0',
                      fontSize: 12,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center px-4 text-center">
                <p className="text-sm font-bold tabular-nums text-slate-900 dark:text-slate-100">
                  {formatCurrency(salesTotal)}
                </p>
                <p className="text-[10px] font-medium text-slate-500 dark:text-slate-400">
                  Total Sales
                </p>
              </div>
            </div>

            <ul className="mt-4 space-y-2">
              {gatewayPie.map((g, i) => (
                <li
                  key={g.name}
                  className="flex items-center justify-between gap-2 text-xs text-slate-600 dark:text-slate-300"
                >
                  <span className="inline-flex min-w-0 items-center gap-2">
                    <span
                      className="h-2.5 w-2.5 shrink-0 rounded-full"
                      style={{ background: GATEWAY_COLORS[i % GATEWAY_COLORS.length] }}
                      aria-hidden
                    />
                    <span className="truncate font-medium text-slate-800 dark:text-slate-200">
                      {g.name}
                    </span>
                  </span>
                  <span className="shrink-0 tabular-nums font-semibold">
                    {g.pct}% · {formatCurrency(g.value)}
                  </span>
                </li>
              ))}
            </ul>

            <button
              type="button"
              onClick={() => navigate('/reports/payin')}
              className="mt-auto inline-flex w-full items-center justify-center gap-1.5 rounded-xl bg-blue-50 px-3 py-2.5 text-sm font-semibold text-blue-700 transition hover:bg-blue-100 dark:bg-blue-950/50 dark:text-blue-300 dark:hover:bg-blue-950"
            >
              View Detailed Report
              <HiArrowRight className="h-4 w-4" aria-hidden />
            </button>
          </>
        )}
      </section>
      </div>
    </div>
  );
};

export default AdminSalesOverview;
