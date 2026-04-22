import React, { useMemo } from 'react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Line,
  ComposedChart,
  Area,
} from 'recharts';
import { formatCurrency } from '../../utils/formatters';

const RupeeTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-lg">
      <p className="font-semibold text-slate-800">{label}</p>
      <ul className="mt-1 space-y-0.5">
        {payload.map((p) => (
          <li key={p.name} className="text-slate-600">
            <span style={{ color: p.color }}>{p.name}: </span>
            {formatCurrency(Number(p.value) || 0)}
          </li>
        ))}
      </ul>
    </div>
  );
};

/**
 * Aggregate analytics API rows into chart-friendly series.
 */
export function DashboardAnalyticsCharts({ rows, loading = false }) {
  const byGateway = useMemo(() => {
    const m = {};
    rows.forEach((r) => {
      const g = (r.gateway || 'Unknown').trim() || 'Unknown';
      m[g] = (m[g] || 0) + parseFloat(r.payin_sales || 0);
    });
    return Object.entries(m)
      .map(([fullName, sales]) => ({
        fullName,
        name: fullName.length > 22 ? `${fullName.slice(0, 20)}…` : fullName,
        sales,
      }))
      .sort((a, b) => b.sales - a.sales)
      .slice(0, 14);
  }, [rows]);

  const trendData = useMemo(() => {
    const m = {};
    rows.forEach((r) => {
      const p = String(r.period || '');
      if (!m[p]) {
        m[p] = { period: p, sales: 0, profit: 0, count: 0 };
      }
      m[p].sales += parseFloat(r.payin_sales || 0);
      m[p].profit += parseFloat(r.platform_profit || 0);
      m[p].count += parseInt(r.transactions_count || 0, 10) || 0;
    });
    return Object.values(m).sort((a, b) => String(a.period).localeCompare(String(b.period)));
  }, [rows]);

  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-8 xl:grid-cols-2">
        {[1, 2].map((k) => (
          <div
            key={k}
            className="h-[340px] animate-pulse rounded-2xl border border-slate-100 bg-gradient-to-br from-slate-50 to-slate-100/80"
          />
        ))}
      </div>
    );
  }

  if (!rows.length) {
    return (
      <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/80 py-16 text-center">
        <p className="text-sm font-medium text-slate-600">No chart data for the selected filters.</p>
        <p className="mt-1 text-xs text-slate-500">Try widening the date range or clearing the gateway filter.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 gap-8 xl:grid-cols-2">
      <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm">
        <div className="mb-4 px-1">
          <h3 className="text-base font-semibold text-slate-900">Sales by gateway</h3>
          <p className="text-xs text-slate-500">Pay-in volume aggregated per payment gateway</p>
        </div>
        <div className="h-[300px] w-full min-h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={byGateway}
              layout="vertical"
              margin={{ top: 8, right: 16, left: 4, bottom: 8 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
              <XAxis
                type="number"
                tickFormatter={(v) => {
                  if (v >= 1e7) return `${(v / 1e7).toFixed(1)}Cr`;
                  if (v >= 1e5) return `${(v / 1e5).toFixed(1)}L`;
                  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
                  return `${Math.round(v)}`;
                }}
                tick={{ fontSize: 11, fill: '#64748b' }}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={108}
                tick={{ fontSize: 11, fill: '#475569' }}
              />
              <Tooltip
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const row = payload[0]?.payload;
                  return (
                    <div className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm shadow-lg">
                      <p className="font-medium text-slate-800">{row?.fullName}</p>
                      <p className="text-slate-600">Sales: {formatCurrency(row?.sales || 0)}</p>
                    </div>
                  );
                }}
              />
              <Bar dataKey="sales" name="Sales" fill="#2563eb" radius={[0, 6, 6, 0]} maxBarSize={28} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm">
        <div className="mb-4 px-1">
          <h3 className="text-base font-semibold text-slate-900">Trend: sales &amp; platform profit</h3>
          <p className="text-xs text-slate-500">By period ({trendData.length} data point{trendData.length === 1 ? '' : 's'})</p>
        </div>
        <div className="h-[300px] w-full min-h-[280px]">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={trendData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <defs>
                <linearGradient id="salesArea" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.35} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
              <XAxis
                dataKey="period"
                tick={{ fontSize: 11, fill: '#64748b' }}
                angle={trendData.length > 8 ? -35 : 0}
                textAnchor={trendData.length > 8 ? 'end' : 'middle'}
                height={trendData.length > 8 ? 56 : 32}
              />
              <YAxis
                tickFormatter={(v) => {
                  if (v >= 1e7) return `${(v / 1e7).toFixed(1)}Cr`;
                  if (v >= 1e5) return `${(v / 1e5).toFixed(1)}L`;
                  if (v >= 1e3) return `${(v / 1e3).toFixed(0)}k`;
                  return `${Math.round(v)}`;
                }}
                tick={{ fontSize: 11, fill: '#64748b' }}
              />
              <Tooltip content={<RupeeTooltip />} />
              <Legend
                wrapperStyle={{ fontSize: 12 }}
                formatter={(value) => <span className="text-slate-700">{value}</span>}
              />
              <Area
                type="monotone"
                dataKey="sales"
                name="Sales"
                stroke="#2563eb"
                strokeWidth={2}
                fill="url(#salesArea)"
              />
              <Line
                type="monotone"
                dataKey="profit"
                name="Platform profit"
                stroke="#059669"
                strokeWidth={2}
                dot={{ r: 3 }}
                activeDot={{ r: 5 }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

export default DashboardAnalyticsCharts;
