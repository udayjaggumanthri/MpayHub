import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  FaCircleCheck,
  FaClock,
  FaCircleXmark,
  FaUsers,
  FaUserCheck,
  FaUserSlash,
  FaUserLock,
} from 'react-icons/fa6';
import { FiChevronRight } from 'react-icons/fi';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip,
} from 'recharts';
import { useWallet, PERIOD_LABELS, periodDateRange } from '../../context/WalletContext';
import { reportsAPI, adminAPI, usersAPI } from '../../services/api';
import { formatCurrency } from '../../utils/formatters';
import { todayIsoDate } from '../../utils/reportDate';
import {
  buildAllModulesDrillDownUrl,
  buildModuleReportDrillDownUrl,
} from '../../utils/dashboardDrillDown';
import GreetingBanner from './GreetingBanner';
import WalletCard from './WalletCard';
import AdminQuickActions from './AdminQuickActions';
import AdminSalesOverview from './AdminSalesOverview';
import TransactionConfidenceBanner from './TransactionConfidenceBanner';
import ReportDateRange from '../common/ReportDateRange';

const SECTION =
  'text-[12px] font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400';

function weekRange() {
  const to = todayIsoDate();
  const d = new Date(`${to}T12:00:00`);
  d.setDate(d.getDate() - 6);
  const from = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  return { dateFrom: from, dateTo: to };
}

function periodDatesForInterval(interval) {
  const today = todayIsoDate();
  if (interval === 'weekly') return weekRange();
  if (interval === 'monthly') {
    const [y, m] = today.split('-');
    return { dateFrom: `${y}-${m}-01`, dateTo: today };
  }
  return { dateFrom: today, dateTo: today };
}

const ACTIVITY_PERIOD_LABELS = {
  daily: 'Today',
  weekly: 'This week',
  monthly: 'Month to date',
  custom: 'Custom range',
};

const StatusStat = ({ label, value, tone, icon: Icon, onClick, loading }) => {
  const tones = {
    success:
      'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-300',
    pending:
      'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300',
    failed:
      'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-800/60 dark:bg-rose-950/40 dark:text-rose-300',
  };
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex min-h-[64px] flex-col items-start justify-between rounded-xl border p-2.5 text-left transition ${tones[tone]} ${
        onClick
          ? 'cursor-pointer hover:shadow-md motion-safe:hover:-translate-y-0.5'
          : 'cursor-default'
      }`}
    >
      <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wide opacity-80">
        <Icon className="h-3 w-3" aria-hidden />
        {label}
      </span>
      <span className="mt-1 text-xl font-bold tabular-nums tracking-tight sm:text-2xl">
        {loading ? '…' : value}
      </span>
    </button>
  );
};

/**
 * Operator home for Admin / Super Admin — matches the reference ops dashboard.
 * Reuses the shared time-of-day GreetingBanner.
 */
const AdminDashboardHome = ({ user, flashInfo = null }) => {
  const navigate = useNavigate();
  const {
    wallets,
    walletMeta,
    heldBalance,
    loading: walletsLoading,
    loadWallets,
    earningsPeriod,
    changeEarningsPeriod,
    earningsRefreshing,
  } = useWallet();

  const [qrStats, setQrStats] = useState(null);
  const [payoutRecoveryStats, setPayoutRecoveryStats] = useState(null);
  const [userCensus, setUserCensus] = useState(null);
  const [activityLoading, setActivityLoading] = useState(true);
  const [activity, setActivity] = useState(null);
  const [activityPreset, setActivityPreset] = useState('daily');
  const [activityDraft, setActivityDraft] = useState(() => periodDatesForInterval('daily'));
  const [appliedActivity, setAppliedActivity] = useState(() => periodDatesForInterval('daily'));

  useEffect(() => {
    loadWallets();
  }, [loadWallets]);

  useEffect(() => {
    let mounted = true;
    adminAPI.getQrOperationsStats().then((res) => {
      if (mounted && res.success) setQrStats(res.data);
    });
    adminAPI.getPayoutRecoveryStats().then((res) => {
      if (mounted && res.success) setPayoutRecoveryStats(res.data);
    });
    usersAPI.getUserStats().then((res) => {
      if (!mounted) return;
      if (res.success && res.data) {
        setUserCensus({
          total: Number(res.data.total) || 0,
          active: Number(res.data.active) || 0,
          disabled: Number(res.data.disabled) || 0,
          restricted: Number(res.data.restricted) || 0,
          kycAwaiting: Number(res.data.kyc_awaiting_approval) || 0,
          kycRejected: Number(res.data.kyc_rejected) || 0,
        });
      }
    });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    setActivityLoading(true);
    reportsAPI
      .getDashboardTransactionStatusCounts({
        module: 'all',
        interval: 'daily',
        date_from: appliedActivity.dateFrom,
        date_to: appliedActivity.dateTo,
      })
      .then((res) => {
        if (!mounted) return;
        setActivity(res.success ? res.data : null);
        setActivityLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [appliedActivity]);

  const counts = activity?.counts || { PENDING: 0, SUCCESS: 0, FAILED: 0, total: 0 };
  const byModule = activity?.by_module || {};

  const userMixPie = useMemo(() => {
    if (!userCensus) return [];
    return [
      { name: 'Active', value: Number(userCensus.active) || 0, color: '#059669', status: 'active' },
      { name: 'Disabled', value: Number(userCensus.disabled) || 0, color: '#e11d48', status: 'disabled' },
      { name: 'Restricted', value: Number(userCensus.restricted) || 0, color: '#d97706', status: 'restricted' },
    ].filter((d) => d.value > 0);
  }, [userCensus]);

  const applyActivityRange = (range, preset = 'custom') => {
    const next = {
      dateFrom: range.dateFrom || appliedActivity.dateFrom,
      dateTo: range.dateTo || appliedActivity.dateTo,
    };
    setActivityDraft(next);
    setAppliedActivity(next);
    setActivityPreset(preset);
  };

  const onActivityPresetChange = (preset) => {
    if (preset === 'custom') {
      setActivityPreset('custom');
      return;
    }
    const range = periodDatesForInterval(preset);
    applyActivityRange(range, preset);
  };

  const drillStatus = (statusKey) => {
    navigate(
      buildAllModulesDrillDownUrl({
        status: statusKey,
        dateFrom: appliedActivity.dateFrom,
        dateTo: appliedActivity.dateTo,
      })
    );
  };

  const drillModule = (moduleKey, statusKey = 'SUCCESS') => {
    navigate(
      buildModuleReportDrillDownUrl({
        module: moduleKey,
        status: statusKey,
        dateFrom: appliedActivity.dateFrom,
        dateTo: appliedActivity.dateTo,
      })
    );
  };

  return (
    <div className="mx-auto max-w-7xl space-y-5 pb-8 sm:space-y-6">
      {flashInfo ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 dark:border-blue-800 dark:bg-blue-950/40 dark:text-blue-200">
          {flashInfo}
        </div>
      ) : null}

      <GreetingBanner user={user} />

      {(userCensus?.kycAwaiting ?? 0) > 0 ? (
        <div className="flex flex-col gap-3 rounded-xl border border-indigo-200 bg-indigo-50 px-4 py-3.5 dark:border-indigo-800 dark:bg-indigo-950/40 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold text-indigo-950 dark:text-indigo-200">
              {userCensus.kycAwaiting} KYC application
              {userCensus.kycAwaiting === 1 ? '' : 's'} awaiting approval
            </p>
            <p className="mt-0.5 text-sm text-indigo-800 dark:text-indigo-300">
              Users completed PAN and Aadhaar verification. Review and approve or reject them in the
              KYC queue.
              {(userCensus.kycRejected ?? 0) > 0
                ? ` ${userCensus.kycRejected} rejected application${
                    userCensus.kycRejected === 1 ? '' : 's'
                  } may also need follow-up.`
                : ''}
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/admin/kyc-approvals')}
            className="min-h-[44px] shrink-0 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Open KYC Approvals
          </button>
        </div>
      ) : null}

      {(qrStats?.pending_count ?? 0) > 0 ? (
        <div className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3.5 dark:border-amber-800 dark:bg-amber-950/40 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold text-amber-900 dark:text-amber-300">
              {qrStats.pending_count} manual QR pay-in
              {qrStats.pending_count === 1 ? '' : 's'} awaiting review
            </p>
            <p className="mt-0.5 text-sm text-amber-800 dark:text-amber-300">
              Retailers have submitted UTR proof. Approve or reject in the operations queue.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/admin/pay-in-qr-operations?status=PENDING_REVIEW')}
            className="min-h-[44px] shrink-0 rounded-lg bg-amber-600 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-700"
          >
            Open QR queue
          </button>
        </div>
      ) : null}

      {(payoutRecoveryStats?.stuck_count ?? 0) > 0 ? (
        <div className="flex flex-col gap-3 rounded-xl border border-rose-200 bg-rose-50 px-4 py-3.5 dark:border-rose-800 dark:bg-rose-950/40 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold text-rose-900 dark:text-rose-300">
              {payoutRecoveryStats.stuck_count} payout
              {payoutRecoveryStats.stuck_count === 1 ? '' : 's'} stuck pending (&gt;30 min)
            </p>
            <p className="mt-0.5 text-sm text-rose-800 dark:text-rose-300">
              Held amount{' '}
              {formatCurrency(parseFloat(payoutRecoveryStats.held_amount || 0))}. Confirm with
              Vidual/bank, then settle or release.
            </p>
          </div>
          <button
            type="button"
            onClick={() => navigate('/admin/payout-recovery')}
            className="min-h-[44px] shrink-0 rounded-lg bg-rose-600 px-4 py-2 text-sm font-semibold text-white hover:bg-rose-700"
          >
            Open payout recovery
          </button>
        </div>
      ) : null}

      {/* Wallet strip */}
      <section aria-labelledby="admin-wallets-heading">
        <h2 id="admin-wallets-heading" className={`mb-2.5 ${SECTION}`}>
          Balances
        </h2>
        {walletsLoading ? (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-[4.75rem] animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            <WalletCard
              compact
              type="main"
              amount={wallets.main}
              subtitle={
                heldBalance > 0
                  ? `Held ${formatCurrency(heldBalance)} · available shown`
                  : 'Available balance'
              }
              onClick={() => navigate('/reports/passbook')}
            />
            <WalletCard
              compact
              type="distributed"
              amount={wallets.distributed}
              subtitle={
                walletMeta?.distributed?.networkUserCount != null
                  ? `${walletMeta.distributed.networkUserCount} users · network total`
                  : userCensus
                    ? `${userCensus.total} users · network total`
                    : "All users' main wallets"
              }
              onClick={() => navigate('/wallets/distributed')}
            />
            <WalletCard
              compact
              type="commission"
              amount={wallets.earnings}
              subtitle={`${PERIOD_LABELS[earningsPeriod] || 'Today'} · credited to main`}
              period={earningsPeriod}
              onPeriodChange={changeEarningsPeriod}
              refreshing={earningsRefreshing}
              onClick={() => {
                const range = periodDateRange(earningsPeriod);
                const q = new URLSearchParams({
                  date_from: range.date_from,
                  date_to: range.date_to,
                });
                navigate(`/reports/commission?${q.toString()}`);
              }}
            />
          </div>
        )}
      </section>

      <AdminQuickActions user={user} qrStats={qrStats} kycAwaiting={userCensus?.kycAwaiting ?? 0} />

      {/* Activity (left) + Platform users (right) */}
      <div className="grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1.55fr)_minmax(17rem,0.85fr)]">
        <section
          aria-labelledby="admin-activity-heading"
          className="rounded-2xl border border-slate-200/90 bg-white shadow-sm dark:border-slate-700/90 dark:bg-slate-900"
        >
          <div className="space-y-3 border-b border-slate-100 px-3.5 py-3 dark:border-slate-800 sm:px-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="min-w-0">
                <h2 id="admin-activity-heading" className={SECTION}>
                  Platform activity
                </h2>
                <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                  Status &amp; services for{' '}
                  <span className="font-semibold text-slate-700 dark:text-slate-200">
                    {ACTIVITY_PERIOD_LABELS[activityPreset] || 'Custom range'}
                  </span>
                  <span className="text-slate-400">
                    {' '}
                    ({appliedActivity.dateFrom} → {appliedActivity.dateTo})
                  </span>
                </p>
              </div>
              {activityLoading ? (
                <span className="text-[11px] font-medium text-slate-400">Updating…</span>
              ) : null}
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {['daily', 'weekly', 'monthly'].map((preset) => (
                <button
                  key={preset}
                  type="button"
                  onClick={() => onActivityPresetChange(preset)}
                  className={`rounded-lg px-2.5 py-1.5 text-[11px] font-semibold transition ${
                    activityPreset === preset
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
                  }`}
                >
                  {ACTIVITY_PERIOD_LABELS[preset]}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setActivityPreset('custom')}
                className={`rounded-lg px-2.5 py-1.5 text-[11px] font-semibold transition ${
                  activityPreset === 'custom'
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:hover:bg-slate-700'
                }`}
              >
                Custom
              </button>
            </div>

            {activityPreset === 'custom' ? (
              <ReportDateRange
                idPrefix="admin-activity"
                compact
                showApply
                applyInline
                applyLabel="Apply"
                fromLabel="From"
                toLabel="To"
                dateFrom={activityDraft.dateFrom}
                dateTo={activityDraft.dateTo}
                onChange={({ dateFrom, dateTo }) => setActivityDraft({ dateFrom, dateTo })}
                onApply={({ dateFrom, dateTo }) => applyActivityRange({ dateFrom, dateTo }, 'custom')}
              />
            ) : null}
          </div>

          <div className="space-y-4 p-3.5 sm:p-4">
            <div>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-400">
                By status
              </p>
              <div className="grid grid-cols-3 gap-2">
                <StatusStat
                  label="Successful"
                  value={counts.SUCCESS ?? 0}
                  tone="success"
                  icon={FaCircleCheck}
                  loading={activityLoading}
                  onClick={() => drillStatus('SUCCESS')}
                />
                <StatusStat
                  label="Pending"
                  value={counts.PENDING ?? 0}
                  tone="pending"
                  icon={FaClock}
                  loading={activityLoading}
                  onClick={() => drillStatus('PENDING')}
                />
                <StatusStat
                  label="Failed"
                  value={counts.FAILED ?? 0}
                  tone="failed"
                  icon={FaCircleXmark}
                  loading={activityLoading}
                  onClick={() => drillStatus('FAILED')}
                />
              </div>
            </div>

            <div>
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-400">
                By service
              </p>
              <ul className="space-y-1.5">
                {[
                  { key: 'payin', label: 'Pay-in' },
                  { key: 'payout', label: 'Payout' },
                  { key: 'bbps', label: 'BBPS' },
                ].map((mod) => {
                  const c = byModule[mod.key] || { SUCCESS: 0, PENDING: 0, FAILED: 0 };
                  const total = (c.SUCCESS ?? 0) + (c.PENDING ?? 0) + (c.FAILED ?? 0);
                  return (
                    <li
                      key={mod.key}
                      className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-100 bg-slate-50/70 px-3 py-2 dark:border-slate-800 dark:bg-slate-950/40"
                    >
                      <button
                        type="button"
                        onClick={() => drillModule(mod.key, 'SUCCESS')}
                        className="inline-flex min-w-[5.5rem] items-center gap-1.5 text-left"
                      >
                        <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">
                          {mod.label}
                        </span>
                        <span className="rounded-md bg-white px-1.5 py-0.5 text-[10px] font-bold tabular-nums text-slate-500 ring-1 ring-slate-200 dark:bg-slate-900 dark:ring-slate-700">
                          {activityLoading ? '…' : total}
                        </span>
                      </button>
                      <div className="ml-auto flex flex-wrap items-center gap-1">
                        <button
                          type="button"
                          onClick={() => drillModule(mod.key, 'SUCCESS')}
                          className="rounded-md bg-emerald-100/90 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-emerald-700 hover:bg-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300"
                        >
                          {c.SUCCESS ?? 0} ok
                        </button>
                        <button
                          type="button"
                          onClick={() => drillModule(mod.key, 'PENDING')}
                          className="rounded-md bg-amber-100/90 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-amber-700 hover:bg-amber-200 dark:bg-amber-950/60 dark:text-amber-300"
                        >
                          {c.PENDING ?? 0} pend
                        </button>
                        <button
                          type="button"
                          onClick={() => drillModule(mod.key, 'FAILED')}
                          className="rounded-md bg-rose-100/90 px-1.5 py-0.5 text-[11px] font-semibold tabular-nums text-rose-700 hover:bg-rose-200 dark:bg-rose-950/60 dark:text-rose-300"
                        >
                          {c.FAILED ?? 0} fail
                        </button>
                        <FiChevronRight className="h-3.5 w-3.5 text-slate-300" aria-hidden />
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          </div>
        </section>

        <section
          aria-labelledby="admin-users-heading"
          className="flex h-full flex-col rounded-2xl border border-slate-200/90 bg-white p-3.5 shadow-sm dark:border-slate-700/90 dark:bg-slate-900 sm:p-4"
        >
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 id="admin-users-heading" className={`flex items-center gap-2 ${SECTION}`}>
                <FaUsers className="text-indigo-500" size={13} aria-hidden />
                Platform users
              </h2>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">Directory snapshot</p>
            </div>
            <button
              type="button"
              onClick={() => navigate('/user-management/users')}
              className="inline-flex items-center gap-1 rounded-lg border border-indigo-200 bg-indigo-50 px-2.5 py-1.5 text-[11px] font-semibold text-indigo-700 hover:bg-indigo-100 dark:border-indigo-800 dark:bg-indigo-950/50 dark:text-indigo-300"
            >
              Directory
              <FiChevronRight size={13} aria-hidden />
            </button>
          </div>
          {userCensus ? (
            <div className="flex min-h-0 flex-1 flex-col gap-3">
              <div className="grid grid-cols-2 gap-2">
                {[
                  {
                    label: 'Total',
                    value: userCensus.total,
                    status: null,
                    icon: FaUsers,
                    tone: 'from-slate-600 to-slate-800',
                    chip: 'bg-slate-50 text-slate-800 dark:bg-slate-800/80 dark:text-slate-100',
                  },
                  {
                    label: 'Active',
                    value: userCensus.active,
                    status: 'active',
                    icon: FaUserCheck,
                    tone: 'from-emerald-500 to-teal-600',
                    chip: 'bg-emerald-50 text-emerald-900 dark:bg-emerald-950/50 dark:text-emerald-200',
                  },
                  {
                    label: 'Disabled',
                    value: userCensus.disabled,
                    status: 'disabled',
                    icon: FaUserSlash,
                    tone: 'from-rose-500 to-red-600',
                    chip: 'bg-rose-50 text-rose-900 dark:bg-rose-950/50 dark:text-rose-200',
                  },
                  {
                    label: 'Restricted',
                    value: userCensus.restricted,
                    status: 'restricted',
                    icon: FaUserLock,
                    tone: 'from-amber-500 to-orange-600',
                    chip: 'bg-amber-50 text-amber-950 dark:bg-amber-950/50 dark:text-amber-200',
                  },
                ].map((card) => {
                  const Icon = card.icon;
                  return (
                    <button
                      key={card.label}
                      type="button"
                      onClick={() =>
                        navigate(
                          card.status
                            ? `/user-management/users?account_status=${card.status}`
                            : '/user-management/users',
                        )
                      }
                      className={`group flex flex-col items-start gap-2 rounded-xl border border-slate-100 p-3 text-left shadow-sm transition hover:border-indigo-200 hover:shadow-md motion-safe:hover:-translate-y-0.5 dark:border-slate-800 dark:hover:border-indigo-800 ${card.chip}`}
                    >
                      <span
                        className={`inline-flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br text-white shadow-sm transition motion-safe:group-hover:scale-105 ${card.tone}`}
                      >
                        <Icon className="h-3.5 w-3.5" aria-hidden />
                      </span>
                      <span>
                        <span className="block text-[10px] font-semibold uppercase tracking-wide opacity-75">
                          {card.label}
                        </span>
                        <span className="mt-0.5 block text-xl font-bold tabular-nums tracking-tight">
                          {card.value}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>

              <div className="mt-auto rounded-xl border border-slate-100 bg-slate-50/60 p-3 dark:border-slate-800 dark:bg-slate-950/40">
                <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.1em] text-slate-400">
                  Account mix
                </p>
                {userMixPie.length === 0 ? (
                  <p className="py-8 text-center text-xs text-slate-500">No users to chart yet.</p>
                ) : (
                  <>
                    <div className="mx-auto h-36 w-full max-w-[180px]">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={userMixPie}
                            dataKey="value"
                            nameKey="name"
                            innerRadius={38}
                            outerRadius={58}
                            paddingAngle={2}
                            onClick={(data) => {
                              const status = data?.status || data?.payload?.status;
                              if (status) {
                                navigate(`/user-management/users?account_status=${status}`);
                              }
                            }}
                            style={{ cursor: 'pointer' }}
                          >
                            {userMixPie.map((slice) => (
                              <Cell key={slice.name} fill={slice.color} />
                            ))}
                          </Pie>
                          <Tooltip
                            formatter={(v) => [v, 'Users']}
                            contentStyle={{
                              borderRadius: 10,
                              border: '1px solid #e2e8f0',
                              fontSize: 12,
                            }}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <ul className="mt-1 space-y-1">
                      {userMixPie.map((slice) => {
                        const pct =
                          userCensus.total > 0
                            ? Math.round((slice.value / userCensus.total) * 100)
                            : 0;
                        return (
                          <li key={slice.name}>
                            <button
                              type="button"
                              onClick={() =>
                                navigate(`/user-management/users?account_status=${slice.status}`)
                              }
                              className="flex w-full items-center justify-between gap-2 rounded-md px-1 py-0.5 text-left text-[11px] text-slate-600 hover:bg-white dark:text-slate-300 dark:hover:bg-slate-900"
                            >
                              <span className="inline-flex items-center gap-1.5">
                                <span
                                  className="h-2 w-2 rounded-full"
                                  style={{ background: slice.color }}
                                  aria-hidden
                                />
                                {slice.name}
                              </span>
                              <span className="tabular-nums font-semibold">
                                {slice.value} · {pct}%
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </>
                )}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="h-[5.25rem] animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
              ))}
            </div>
          )}
        </section>
      </div>

      <AdminSalesOverview />

      <TransactionConfidenceBanner />
    </div>
  );
};

export default AdminDashboardHome;
