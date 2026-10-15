import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import Input from '../common/Input';
import Button from '../common/Button';
import LoadingSpinner from '../common/LoadingSpinner';
import GatewayFlowStepper from './GatewayFlowStepper';
import { firstErrorMessage, packageTotalDeductionDisplay, pct } from './gatewayAdminShared';
import { formatDecimalInput } from '../../utils/formatters';
import {
  FaPlus,
  FaPenToSquare,
  FaTrash,
  FaCalculator,
  FaChartPie,
  FaCreditCard,
  FaArrowRight,
  FaStar,
} from 'react-icons/fa6';

const PROVIDER_LABELS = {
  toucan: 'Toucan',
  razorpay: 'Razorpay',
  payu: 'PayU',
  mock: 'Mock',
};

const PayInPackagesAdmin = () => {
  const navigate = useNavigate();
  const [packages, setPackages] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [defaultLoading, setDefaultLoading] = useState(null);

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

  const handleDeletePackage = async (pkgId) => {
    if (!window.confirm('Delete this package? Existing historical transactions remain safe.')) return;
    const result = await adminAPI.deletePayInPackage(pkgId);
    if (!result.success) {
      alert(result.message || 'Delete failed');
      return;
    }
    await loadPackages();
  };

  const handleSetDefaultPackage = async (pkg) => {
    const message = `${pkg.display_name} will apply to everyone who does not have a special package. Other packages already marked for everyone stay available. Users who already have a package assigned stay on it.`;
    if (!window.confirm(message)) return;
    setDefaultLoading(pkg.id);
    const result = await adminAPI.setDefaultPackage(pkg.id);
    setDefaultLoading(null);
    if (!result.success) {
      alert(firstErrorMessage(result, 'Could not set default package'));
      return;
    }
    await loadPackages();
  };

  const handleClearDefaultPackage = async (pkg) => {
    if (!window.confirm(`${pkg.display_name} will stop applying to everyone. Other packages marked for everyone stay available. Users with a special package assigned are not changed.`)) return;
    setDefaultLoading(pkg.id);
    const result = await adminAPI.clearDefaultPackage(pkg.id);
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
            <div className="flex flex-wrap items-center gap-2">
              <Link
                to="/admin/gateways"
                className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-slate-200 px-4 text-sm font-semibold text-slate-700 dark:border-slate-600 dark:text-slate-200"
              >
                <FaCreditCard size={16} />
                Payment gateways
                <FaArrowRight size={12} />
              </Link>
              <Link
                to="/admin/pay-in-qr-accounts"
                className="inline-flex h-11 items-center gap-2 whitespace-nowrap rounded-xl border border-emerald-200 px-4 text-sm font-semibold text-emerald-800 dark:border-emerald-800 dark:text-emerald-200"
              >
                QR accounts
                <FaArrowRight size={12} />
              </Link>
            </div>
          </div>
        </header>

        <section className="rounded-2xl border bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
          <div className="flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <h3 className="text-lg font-semibold">Payout slabs</h3>
              <p className="text-sm text-slate-600 dark:text-slate-400">
                Charge + Commission bands are configured platform-wide (not per package).
              </p>
            </div>
            <Link
              to="/admin/payout-slabs"
              className="inline-flex h-11 shrink-0 items-center gap-2 whitespace-nowrap rounded-xl border border-amber-300 bg-amber-50 px-4 text-sm font-semibold text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-100"
            >
              Open payout slabs
              <FaArrowRight size={14} />
            </Link>
          </div>
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
                className="whitespace-nowrap"
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
                <p className="mb-3 text-xs leading-5 text-slate-500 dark:text-slate-400">
                  Checkout provider is stored on the package. Open Edit to change it. Several packages can apply to everyone at the same time. A user with a special assignment still sees only that assignment.
                </p>
                <div className="overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700">
                  <table className="w-full min-w-[1080px] border-separate border-spacing-0 text-sm">
                    <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:bg-slate-800">
                      <tr>
                        <th className="whitespace-nowrap px-4 py-3">Package</th>
                        <th className="whitespace-nowrap px-4 py-3">Provider</th>
                        <th className="whitespace-nowrap px-4 py-3">Rails</th>
                        <th className="whitespace-nowrap px-4 py-3 text-right">Max rail</th>
                        <th className="whitespace-nowrap px-4 py-3">Commission</th>
                        <th className="whitespace-nowrap px-4 py-3 text-right">Total</th>
                        <th className="whitespace-nowrap px-4 py-3">Limits</th>
                        <th className="whitespace-nowrap px-4 py-3">Status</th>
                        <th className="whitespace-nowrap px-4 py-3">For everyone</th>
                        <th className="whitespace-nowrap px-4 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {packages.map((pkg) => (
                        <tr key={pkg.id} className="hover:bg-slate-50/70 dark:hover:bg-slate-800/40">
                          <td className="border-t border-slate-100 px-4 py-3 align-middle dark:border-slate-800">
                            <div className="whitespace-nowrap font-semibold text-slate-900 dark:text-slate-100">{pkg.display_name}</div>
                            <div className="whitespace-nowrap font-mono text-xs text-slate-500">{pkg.code}</div>
                          </td>
                          <td className="border-t border-slate-100 px-4 py-3 align-middle dark:border-slate-800">
                            <span className="inline-flex whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-800 dark:bg-slate-800 dark:text-slate-100">
                              {PROVIDER_LABELS[pkg.provider] || pkg.provider || '—'}
                            </span>
                          </td>
                          <td className="border-t border-slate-100 px-4 py-3 align-middle dark:border-slate-800">
                            <div className="whitespace-nowrap text-sm text-slate-800 dark:text-slate-100">
                              {pkg.rails_label || 'No rail linked'}
                            </div>
                            <div className="whitespace-nowrap text-xs text-slate-500">
                              {pkg.gateway_count ?? 0} gateway · {pkg.qr_count ?? 0} QR
                            </div>
                          </td>
                          <td className="border-t border-slate-100 px-4 py-3 text-right align-middle tabular-nums dark:border-slate-800">
                            {pct(pkg.max_rail_gateway_fee_pct)}%
                          </td>
                          <td className="border-t border-slate-100 px-4 py-3 align-middle dark:border-slate-800">
                            <div className="whitespace-nowrap text-xs leading-5 tabular-nums text-slate-700 dark:text-slate-200">
                              Admin {pct(pkg.admin_pct)}% · SD {pct(pkg.super_distributor_pct)}% · MD {pct(pkg.master_distributor_pct)}% · D {pct(pkg.distributor_pct)}%
                            </div>
                          </td>
                          <td className="border-t border-slate-100 px-4 py-3 text-right align-middle font-semibold tabular-nums dark:border-slate-800">
                            {packageTotalDeductionDisplay(pkg)}%
                          </td>
                          <td className="whitespace-nowrap border-t border-slate-100 px-4 py-3 align-middle text-xs tabular-nums dark:border-slate-800">
                            ₹{formatDecimalInput(pkg.min_amount) || '0.00'} – ₹{formatDecimalInput(pkg.max_amount_per_txn) || '0.00'}
                          </td>
                          <td className="border-t border-slate-100 px-4 py-3 align-middle dark:border-slate-800">
                            <span
                              className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-semibold ${
                                pkg.is_active
                                  ? 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-200'
                                  : 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300'
                              }`}
                            >
                              {pkg.is_active ? 'Active' : 'Off'}
                            </span>
                          </td>
                          <td className="border-t border-slate-100 px-4 py-3 align-middle dark:border-slate-800">
                            {pkg.is_default ? (
                              <button
                                type="button"
                                onClick={() => handleClearDefaultPackage(pkg)}
                                disabled={defaultLoading === pkg.id}
                                className="inline-flex h-8 items-center gap-1 whitespace-nowrap rounded-full bg-amber-100 px-3 text-xs font-semibold text-amber-900 disabled:opacity-50 dark:bg-amber-950/50 dark:text-amber-100"
                              >
                                <FaStar size={10} />
                                On
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => handleSetDefaultPackage(pkg)}
                                disabled={defaultLoading === pkg.id || !pkg.is_active}
                                className="inline-flex h-8 items-center whitespace-nowrap rounded-full border border-slate-200 px-3 text-xs font-semibold text-slate-600 disabled:opacity-50 dark:border-slate-600 dark:text-slate-300"
                              >
                                Off
                              </button>
                            )}
                          </td>
                          <td className="border-t border-slate-100 px-4 py-3 align-middle dark:border-slate-800">
                            <div className="flex items-center justify-end gap-1 whitespace-nowrap">
                              <Link
                                to={`/admin/pay-in-packages/${pkg.id}/calculation-preview`}
                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-emerald-700 hover:bg-emerald-50 dark:text-emerald-300 dark:hover:bg-emerald-950/40"
                                title="Calculator"
                              >
                                <FaCalculator size={14} />
                              </Link>
                              <button
                                type="button"
                                onClick={() => navigate(`/admin/pay-in-packages/${pkg.id}/edit`)}
                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-indigo-700 hover:bg-indigo-50 dark:text-indigo-300 dark:hover:bg-indigo-950/40"
                                title="Edit"
                              >
                                <FaPenToSquare size={14} />
                              </button>
                              <button
                                type="button"
                                onClick={() => handleDeletePackage(pkg.id)}
                                className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40"
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
