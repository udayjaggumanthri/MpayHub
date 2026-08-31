import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import Input from '../common/Input';
import Button from '../common/Button';
import LoadingSpinner from '../common/LoadingSpinner';
import GatewayFlowStepper from './GatewayFlowStepper';
import { firstErrorMessage, packageTotalDeductionDisplay, pct } from './gatewayAdminShared';
import {
  FaPlus,
  FaPenToSquare,
  FaTrash,
  FaCalculator,
  FaChartPie,
  FaCreditCard,
  FaArrowRight,
  FaStar,
  FaXmark,
} from 'react-icons/fa6';

const PayInPackagesAdmin = () => {
  const navigate = useNavigate();
  const [packages, setPackages] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [defaultLoading, setDefaultLoading] = useState(null);
  const [slabLoading, setSlabLoading] = useState(false);
  const [payoutSlabForm, setPayoutSlabForm] = useState({
    low_max_amount: '24999',
    low_charge: '7',
    high_charge: '15',
  });

  const loadPackages = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    const res = await adminAPI.listPayInPackages({
      page,
      page_size: 20,
      search: search.trim() || undefined,
    });
    setLoading(false);
    if (res.success) {
      setPackages(res.data?.results || []);
      setTotal(res.data?.total || 0);
    } else {
      setPackages([]);
      setTotal(0);
      setLoadError(res.message || 'Could not load packages.');
    }
  }, [page, search]);

  useEffect(() => {
    loadPackages();
  }, [loadPackages]);

  useEffect(() => {
    adminAPI.getPayoutSlabConfig().then((sRes) => {
      if (sRes.success && sRes.data?.config) {
        const cfg = sRes.data.config;
        setPayoutSlabForm({
          low_max_amount: String(cfg.low_max_amount ?? '24999'),
          low_charge: String(cfg.low_charge ?? '7'),
          high_charge: String(cfg.high_charge ?? '15'),
        });
      }
    });
  }, []);

  const savePayoutSlab = async (e) => {
    e.preventDefault();
    setSlabLoading(true);
    const res = await adminAPI.updatePayoutSlabConfig({
      low_max_amount: payoutSlabForm.low_max_amount,
      low_charge: payoutSlabForm.low_charge,
      high_charge: payoutSlabForm.high_charge,
    });
    setSlabLoading(false);
    if (!res.success) {
      alert(firstErrorMessage(res, 'Could not update payout slab config'));
      return;
    }
    alert('Payout slab updated');
  };

  const handleDeletePackage = async (pkgId) => {
    if (!window.confirm('Delete this package? Existing historical transactions remain safe.')) return;
    const result = await adminAPI.deletePayInPackage(pkgId);
    if (!result.success) {
      alert(result.message || 'Delete failed');
      return;
    }
    await loadPackages();
  };

  const handleSetDefaultPackage = async (pkgId) => {
    setDefaultLoading(pkgId);
    const result = await adminAPI.setDefaultPackage(pkgId);
    setDefaultLoading(null);
    if (!result.success) {
      alert(firstErrorMessage(result, 'Could not set default package'));
      return;
    }
    await loadPackages();
  };

  const handleClearDefaultPackage = async () => {
    if (!window.confirm('Clear default package?')) return;
    setDefaultLoading('clear');
    const result = await adminAPI.clearDefaultPackage();
    setDefaultLoading(null);
    if (!result.success) {
      alert(firstErrorMessage(result, 'Could not clear default package'));
      return;
    }
    await loadPackages();
  };

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-slate-50/80 dark:to-slate-900/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <GatewayFlowStepper
          currentStep="payin-packages"
          subtitle="Step 3/3: Attach multiple gateways per package and set a default execution rail."
        />

        <header className="relative overflow-hidden rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-900 shadow-sm">
          <div className="relative px-6 py-8 sm:px-8 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100">Pay-in packages</h1>
              <p className="mt-2 text-sm text-slate-600 dark:text-slate-400 max-w-xl">
                Fee split for load money: gateway, platform admin, and upline commissions.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                to="/admin/gateways"
                className="inline-flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-300"
              >
                <FaCreditCard size={18} />
                Payment gateways
                <FaArrowRight size={14} />
              </Link>
              <Link
                to="/admin/pay-in-qr-accounts"
                className="inline-flex items-center gap-2 rounded-xl border px-4 py-3 text-sm font-semibold text-emerald-800"
              >
                QR accounts
                <FaArrowRight size={14} />
              </Link>
            </div>
          </div>
        </header>

        <section className="rounded-2xl border bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
          <div className="border-b bg-slate-50/80 dark:bg-slate-800/50 px-5 py-4 sm:px-6">
            <h3 className="text-lg font-semibold">System fallback: payout slab (two-tier)</h3>
          </div>
          <form onSubmit={savePayoutSlab} className="px-5 py-4 sm:px-6 grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
            <Input
              label="Low slab max amount"
              value={payoutSlabForm.low_max_amount}
              onChange={(e) => setPayoutSlabForm((f) => ({ ...f, low_max_amount: e.target.value }))}
            />
            <Input
              label="Charge up to low slab max"
              value={payoutSlabForm.low_charge}
              onChange={(e) => setPayoutSlabForm((f) => ({ ...f, low_charge: e.target.value }))}
            />
            <Input
              label="Charge above low slab max"
              value={payoutSlabForm.high_charge}
              onChange={(e) => setPayoutSlabForm((f) => ({ ...f, high_charge: e.target.value }))}
            />
            <Button type="submit" loading={slabLoading}>
              Save Slab
            </Button>
          </form>
        </section>

        <section className="rounded-2xl border bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
          <div className="flex flex-col gap-4 border-b bg-slate-50/80 dark:bg-slate-800/50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div className="flex items-center gap-3">
              <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-violet-600 text-white">
                <FaChartPie size={20} />
              </span>
              <div>
                <h2 className="text-lg font-bold">Commercial packages</h2>
                <p className="text-sm text-slate-600 dark:text-slate-400">{total} total</p>
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Input
                placeholder="Search name or code…"
                value={search}
                onChange={(e) => {
                  setSearch(e.target.value);
                  setPage(1);
                }}
                className="w-48"
              />
              <Button
                onClick={() => navigate('/admin/pay-in-packages/new')}
                variant="primary"
                icon={FaPlus}
                iconPosition="left"
              >
                Add package
              </Button>
            </div>
          </div>

          <div className="p-5 sm:p-6">
            {loading ? (
              <div className="flex justify-center py-12">
                <LoadingSpinner />
              </div>
            ) : loadError ? (
              <p className="text-red-600 text-sm">{loadError}</p>
            ) : packages.length === 0 ? (
              <div className="text-center py-14">
                <FaChartPie className="mx-auto text-slate-300 mb-3" size={36} />
                <p className="font-medium">No pay-in packages</p>
                <Button
                  onClick={() => navigate('/admin/pay-in-packages/new')}
                  variant="primary"
                  className="mt-5"
                  icon={FaPlus}
                >
                  Create package
                </Button>
              </div>
            ) : (
              <>
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
                  <table className="w-full text-sm">
                    <thead className="bg-slate-50 dark:bg-slate-800 text-xs uppercase text-slate-500">
                      <tr>
                        <th className="p-3 text-left">Package</th>
                        <th className="p-3 text-left">Provider</th>
                        <th className="p-3 text-center">Rails</th>
                        <th className="p-3 text-right">Max rail %</th>
                        <th className="p-3 text-right">Commission %</th>
                        <th className="p-3 text-right">Total %</th>
                        <th className="p-3 text-left">Limits</th>
                        <th className="p-3 text-center">Status</th>
                        <th className="p-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {packages.map((pkg) => (
                        <tr
                          key={pkg.id}
                          className="border-t border-slate-100 dark:border-slate-800 hover:bg-slate-50/50 dark:hover:bg-slate-800/30"
                        >
                          <td className="p-3">
                            <div className="font-semibold text-slate-900 dark:text-slate-100">{pkg.display_name}</div>
                            <code className="text-xs text-slate-500">{pkg.code}</code>
                          </td>
                          <td className="p-3 capitalize">{pkg.default_gateway_name || pkg.provider || '—'}</td>
                          <td className="p-3 text-center tabular-nums">
                            {pkg.gateway_count ?? 0}g / {pkg.qr_count ?? 0}qr
                          </td>
                          <td className="p-3 text-right tabular-nums">{pct(pkg.max_rail_gateway_fee_pct)}%</td>
                          <td className="p-3 text-right text-xs tabular-nums">
                            {pct(pkg.admin_pct)} / {pct(pkg.super_distributor_pct)} / {pct(pkg.master_distributor_pct)} /{' '}
                            {pct(pkg.distributor_pct)}
                          </td>
                          <td className="p-3 text-right font-semibold tabular-nums">
                            {packageTotalDeductionDisplay(pkg)}%
                          </td>
                          <td className="p-3 text-xs whitespace-nowrap">
                            ₹{pkg.min_amount} – ₹{pkg.max_amount_per_txn}
                          </td>
                          <td className="p-3 text-center">
                            <div className="flex flex-col items-center gap-1">
                              <span
                                className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                  pkg.is_active
                                    ? 'bg-emerald-50 text-emerald-800'
                                    : 'bg-slate-100 text-slate-600'
                                }`}
                              >
                                {pkg.is_active ? 'Active' : 'Off'}
                              </span>
                              {pkg.is_default && (
                                <span className="inline-flex items-center gap-1 text-xs text-amber-700">
                                  <FaStar size={10} />
                                  Default
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="p-3">
                            <div className="flex items-center justify-end gap-1 flex-wrap">
                              <Link
                                to={`/admin/pay-in-packages/${pkg.id}/calculation-preview`}
                                className="p-2 text-emerald-700 hover:bg-emerald-50 rounded-lg"
                                title="Calculator"
                              >
                                <FaCalculator size={14} />
                              </Link>
                              <button
                                type="button"
                                onClick={() => navigate(`/admin/pay-in-packages/${pkg.id}/edit`)}
                                className="p-2 text-indigo-700 hover:bg-indigo-50 rounded-lg"
                                title="Edit"
                              >
                                <FaPenToSquare size={14} />
                              </button>
                              {!pkg.is_default && pkg.is_active && (
                                <button
                                  type="button"
                                  onClick={() => handleSetDefaultPackage(pkg.id)}
                                  disabled={defaultLoading === pkg.id}
                                  className="p-2 text-amber-700 hover:bg-amber-50 rounded-lg disabled:opacity-50"
                                  title="Set default"
                                >
                                  <FaStar size={14} />
                                </button>
                              )}
                              {pkg.is_default && (
                                <button
                                  type="button"
                                  onClick={handleClearDefaultPackage}
                                  disabled={defaultLoading === 'clear'}
                                  className="p-2 text-slate-600 hover:bg-slate-100 rounded-lg"
                                  title="Clear default"
                                >
                                  <FaXmark size={14} />
                                </button>
                              )}
                              <button
                                type="button"
                                onClick={() => handleDeletePackage(pkg.id)}
                                className="p-2 text-red-600 hover:bg-red-50 rounded-lg"
                                title="Delete"
                              >
                                <FaTrash size={14} />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="flex items-center justify-between mt-4 text-sm">
                  <span className="text-slate-600 dark:text-slate-400">
                    Page {page} of {totalPages} ({total} packages)
                  </span>
                  <div className="flex gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={page <= 1}
                      onClick={() => setPage((p) => Math.max(1, p - 1))}
                    >
                      Previous
                    </Button>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={page >= totalPages}
                      onClick={() => setPage((p) => p + 1)}
                    >
                      Next
                    </Button>
                  </div>
                </div>
              </>
            )}
          </div>
        </section>
      </div>
    </div>
  );
};

export default PayInPackagesAdmin;
