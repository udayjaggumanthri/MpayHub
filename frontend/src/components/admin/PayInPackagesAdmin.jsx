import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import {
  FaPlus,
  FaPenToSquare,
  FaTrash,
  FaXmark,
  FaCalculator,
  FaChartPie,
  FaCreditCard,
  FaArrowRight,
  FaStar,
} from 'react-icons/fa6';
import {
  parseList,
  roleFields,
  firstErrorMessage,
  pct,
  packageCommissionStrip,
  packageTotalDeductionDisplay,
} from './gatewayAdminShared';

const PayInPackagesAdmin = () => {
  const [gateways, setGateways] = useState([]);
  const [packages, setPackages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showPackageModal, setShowPackageModal] = useState(false);
  const [editingPackage, setEditingPackage] = useState(null);
  const [showPreviewModal, setShowPreviewModal] = useState(false);
  const [previewPackage, setPreviewPackage] = useState(null);
  const [previewAmount, setPreviewAmount] = useState('100000');
  const [previewResult, setPreviewResult] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [slabLoading, setSlabLoading] = useState(false);
  const [defaultLoading, setDefaultLoading] = useState(null);
  const [payoutSlabForm, setPayoutSlabForm] = useState({
    low_max_amount: '24999',
    low_charge: '7',
    high_charge: '15',
  });
  const [packageForm, setPackageForm] = useState({
    code: '',
    display_name: '',
    provider: 'razorpay',
    payment_gateway_id: '',
    min_amount: '1',
    max_amount_per_txn: '200000',
    gateway_fee_pct: '1',
    admin_pct: '0.24',
    super_distributor_pct: '0.01',
    master_distributor_pct: '0.02',
    distributor_pct: '0.03',
    is_active: true,
    sort_order: '0',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    const [gRes, pRes, sRes] = await Promise.all([
      adminAPI.listPaymentGateways(),
      adminAPI.listPayInPackages(),
      adminAPI.getPayoutSlabConfig(),
    ]);
    if (gRes.success) setGateways(parseList(gRes));
    if (pRes.success) setPackages(parseList(pRes));
    if (sRes.success && sRes.data?.config) {
      const cfg = sRes.data.config;
      setPayoutSlabForm({
        low_max_amount: String(cfg.low_max_amount ?? '24999'),
        low_charge: String(cfg.low_charge ?? '7'),
        high_charge: String(cfg.high_charge ?? '15'),
      });
    }
  };

  const savePayoutSlab = async (e) => {
    e.preventDefault();
    setSlabLoading(true);
    const payload = {
      low_max_amount: payoutSlabForm.low_max_amount,
      low_charge: payoutSlabForm.low_charge,
      high_charge: payoutSlabForm.high_charge,
    };
    const res = await adminAPI.updatePayoutSlabConfig(payload);
    setSlabLoading(false);
    if (!res.success) {
      alert(firstErrorMessage(res, 'Could not update payout slab config'));
      return;
    }
    alert('Payout slab updated');
    await loadData();
  };

  const openAddPackage = () => {
    const defaultGatewayId = gateways.length > 0 ? String(gateways[0].id) : '';
    setEditingPackage(null);
    setPackageForm({
      code: '',
      display_name: '',
      provider: 'razorpay',
      payment_gateway_id: defaultGatewayId,
      min_amount: '1',
      max_amount_per_txn: '200000',
      gateway_fee_pct: '1',
      admin_pct: '0.24',
      super_distributor_pct: '0.01',
      master_distributor_pct: '0.02',
      distributor_pct: '0.03',
      is_active: true,
      sort_order: '0',
    });
    setShowPackageModal(true);
  };

  const openEditPackage = (pkg) => {
    setEditingPackage(pkg);
    setPackageForm({
      code: pkg.code || '',
      display_name: pkg.display_name || '',
      provider: pkg.provider || 'razorpay',
      payment_gateway_id: pkg.payment_gateway?.id ? String(pkg.payment_gateway.id) : '',
      min_amount: pkg.min_amount?.toString?.() || '1',
      max_amount_per_txn: pkg.max_amount_per_txn?.toString?.() || '200000',
      gateway_fee_pct: pkg.gateway_fee_pct?.toString?.() || '0',
      admin_pct: pkg.admin_pct?.toString?.() || '0',
      super_distributor_pct: pkg.super_distributor_pct?.toString?.() || '0',
      master_distributor_pct: pkg.master_distributor_pct?.toString?.() || '0',
      distributor_pct: pkg.distributor_pct?.toString?.() || '0',
      is_active: Boolean(pkg.is_active),
      sort_order: pkg.sort_order?.toString?.() || '0',
    });
    setShowPackageModal(true);
  };

  const handleSavePackage = async (e) => {
    e.preventDefault();
    if (!packageForm.code || !packageForm.display_name) {
      alert('Code and Display Name are required');
      return;
    }
    if (!packageForm.payment_gateway_id) {
      alert('Please select a Payment Gateway.');
      return;
    }
    setLoading(true);
    const payload = {
      code: packageForm.code.trim(),
      display_name: packageForm.display_name.trim(),
      provider: packageForm.provider,
      payment_gateway_id: packageForm.payment_gateway_id ? Number(packageForm.payment_gateway_id) : null,
      min_amount: packageForm.min_amount,
      max_amount_per_txn: packageForm.max_amount_per_txn,
      gateway_fee_pct: packageForm.gateway_fee_pct,
      admin_pct: packageForm.admin_pct,
      super_distributor_pct: packageForm.super_distributor_pct,
      master_distributor_pct: packageForm.master_distributor_pct,
      distributor_pct: packageForm.distributor_pct,
      is_active: packageForm.is_active,
      sort_order: Number(packageForm.sort_order || 0),
    };
    let result;
    if (editingPackage) {
      result = await adminAPI.updatePayInPackage(editingPackage.id, payload);
    } else {
      result = await adminAPI.createPayInPackage(payload);
    }
    setLoading(false);
    if (!result.success) {
      alert(firstErrorMessage(result, 'Could not save pay-in package'));
      return;
    }
    setShowPackageModal(false);
    setEditingPackage(null);
    await loadData();
  };

  const handleDeletePackage = async (pkgId) => {
    if (!window.confirm('Delete this package? Existing historical transactions remain safe.')) return;
    const result = await adminAPI.deletePayInPackage(pkgId);
    if (!result.success) {
      alert(result.message || 'Delete failed');
      return;
    }
    await loadData();
  };

  const handleSetDefaultPackage = async (pkgId) => {
    setDefaultLoading(pkgId);
    const result = await adminAPI.setDefaultPackage(pkgId);
    setDefaultLoading(null);
    if (!result.success) {
      alert(firstErrorMessage(result, 'Could not set default package'));
      return;
    }
    await loadData();
  };

  const handleClearDefaultPackage = async () => {
    if (!window.confirm('Clear default package? New users will not have any package auto-assigned.')) return;
    setDefaultLoading('clear');
    const result = await adminAPI.clearDefaultPackage();
    setDefaultLoading(null);
    if (!result.success) {
      alert(firstErrorMessage(result, 'Could not clear default package'));
      return;
    }
    await loadData();
  };

  const openPreview = (pkg) => {
    setPreviewPackage(pkg);
    setPreviewAmount('100000');
    setPreviewResult(null);
    setShowPreviewModal(true);
  };

  const runPreview = async () => {
    if (!previewPackage?.id || !previewAmount) return;
    setPreviewLoading(true);
    const result = await adminAPI.previewPayInPackage(previewPackage.id, previewAmount);
    setPreviewLoading(false);
    if (result.success) {
      setPreviewResult(result.data);
      return;
    }
    alert(result.message || 'Could not generate preview');
  };

  const totalDeductionPct = (
    parseFloat(packageForm.gateway_fee_pct || 0) +
    parseFloat(packageForm.admin_pct || 0) +
    parseFloat(packageForm.super_distributor_pct || 0) +
    parseFloat(packageForm.master_distributor_pct || 0) +
    parseFloat(packageForm.distributor_pct || 0)
  ).toFixed(4);

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 via-white to-slate-50/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <header className="relative overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-br from-violet-500/[0.07] via-transparent to-indigo-500/[0.06] pointer-events-none" />
          <div className="relative px-6 py-8 sm:px-8 sm:py-9 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-violet-600 mb-2">
                Admin · Pay-in
              </p>
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">Pay-in packages</h1>
              <p className="mt-2 text-sm sm:text-base text-slate-600 max-w-xl leading-relaxed">
                Fee split for load money: gateway, platform admin, and upline commissions (SD / MD / D). Use
                Preview to sanity-check amounts.
              </p>
            </div>
            <Link
              to="/admin/gateways"
              className="inline-flex items-center gap-2 self-start rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm hover:border-indigo-200 hover:bg-indigo-50/50 hover:text-indigo-800 transition-colors"
            >
              <FaCreditCard className="text-indigo-600" size={18} />
              Payment gateways
              <FaArrowRight size={14} className="text-slate-400" />
            </Link>
          </div>
        </header>

        <section className="rounded-2xl border border-slate-200/90 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-slate-100 bg-slate-50/80 px-5 py-4 sm:px-6">
            <h3 className="text-lg font-semibold text-slate-900">Payout slab configuration (add-on mode)</h3>
            <p className="text-sm text-slate-600 mt-1">
              Wallet debit = transfer amount + slab charge. Configure thresholds and flat charges below.
            </p>
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

        <section className="rounded-2xl border border-slate-200/90 bg-white shadow-sm overflow-hidden">
          <div className="flex flex-col gap-4 border-b border-slate-100 bg-slate-50/80 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-violet-600 text-white shadow-md shadow-violet-600/20">
                <FaChartPie size={20} />
              </span>
              <div>
                <h2 className="text-lg font-bold text-slate-900">Packages</h2>
                <p className="text-sm text-slate-600 mt-0.5">
                  Each package drives quotes and settlement for load money.
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
                {packages.length} {packages.length === 1 ? 'package' : 'packages'}
              </span>
              <Button onClick={openAddPackage} variant="primary" size="md" icon={FaPlus} iconPosition="left">
                Add package
              </Button>
            </div>
          </div>

          <div className="p-5 sm:p-6">
            {packages.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 px-6 py-14 text-center">
                <FaChartPie className="mx-auto text-slate-300 mb-3" size={36} />
                <p className="text-slate-700 font-medium">No pay-in packages</p>
                <p className="text-sm text-slate-500 mt-1 max-w-md mx-auto">
                  Add a package after you have at least one payment gateway for live providers.
                </p>
                <Button onClick={openAddPackage} variant="primary" size="md" icon={FaPlus} iconPosition="left" className="mt-5">
                  Create package
                </Button>
              </div>
            ) : (
              <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
                {packages.map((pkg) => {
                  const strip = packageCommissionStrip(pkg);
                  const stripSum = strip.reduce((s, x) => s + parseFloat(x.v || 0), 0) || 1;
                  return (
                    <li
                      key={pkg.id}
                      className="group flex flex-col rounded-2xl border border-slate-200/90 bg-white p-5 shadow-sm ring-1 ring-transparent hover:ring-indigo-200/60 hover:shadow-md transition-all"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <h3 className="font-bold text-slate-900 truncate text-base leading-snug">{pkg.display_name}</h3>
                            {pkg.is_default && (
                              <span className="shrink-0 inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-semibold text-amber-700 ring-1 ring-amber-200">
                                <FaStar size={10} />
                                Default
                              </span>
                            )}
                          </div>
                          <code className="mt-1 inline-block text-xs text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md font-mono">
                            {pkg.code}
                          </code>
                        </div>
                        <span
                          className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold ${
                            pkg.is_active
                              ? 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-100'
                              : 'bg-slate-100 text-slate-600 ring-1 ring-slate-200'
                          }`}
                        >
                          {pkg.is_active ? 'Active' : 'Off'}
                        </span>
                      </div>

                      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
                        <span className="rounded-md bg-violet-50 text-violet-800 px-2 py-1 font-semibold capitalize ring-1 ring-violet-100">
                          {pkg.provider}
                        </span>
                        <span className="text-slate-500">
                          ₹{pkg.min_amount} – ₹{pkg.max_amount_per_txn}
                        </span>
                      </div>

                      <div className="mt-4">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
                          Split (%) · Gw / Adm / SD / MD / D
                        </p>
                        <div className="flex h-2 w-full overflow-hidden rounded-full bg-slate-100 ring-1 ring-slate-200/80">
                          {strip.map((seg) => {
                            const w = Math.max(2, (parseFloat(seg.v || 0) / stripSum) * 100);
                            return (
                              <div
                                key={seg.k}
                                title={`${seg.k}: ${pct(seg.v)}%`}
                                className={`${seg.c} first:rounded-l-full last:rounded-r-full opacity-90 hover:opacity-100 transition-opacity`}
                                style={{ width: `${w}%` }}
                              />
                            );
                          })}
                        </div>
                        <div className="mt-2 grid grid-cols-3 sm:grid-cols-6 gap-2 text-[11px] leading-tight">
                          {strip.map((seg) => (
                            <div key={seg.k} className="text-slate-600">
                              <span className="text-slate-400">{seg.k}</span>
                              <div className="font-semibold tabular-nums text-slate-800">{pct(seg.v)}%</div>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="mt-4 flex items-baseline justify-between border-t border-slate-100 pt-4">
                        <div>
                          <p className="text-xs text-slate-500">Total fee % (from gross)</p>
                          <p className="text-lg font-bold tabular-nums text-slate-900">
                            {packageTotalDeductionDisplay(pkg)}%
                          </p>
                        </div>
                      </div>

                      <div className="mt-4 flex items-center justify-end gap-1 border-t border-slate-50 pt-3 flex-wrap">
                        {!pkg.is_default && pkg.is_active && (
                          <button
                            type="button"
                            onClick={() => handleSetDefaultPackage(pkg.id)}
                            disabled={defaultLoading === pkg.id}
                            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-amber-700 hover:bg-amber-50 transition-colors disabled:opacity-50"
                          >
                            <FaStar size={14} />
                            {defaultLoading === pkg.id ? 'Setting...' : 'Set Default'}
                          </button>
                        )}
                        {pkg.is_default && (
                          <button
                            type="button"
                            onClick={handleClearDefaultPackage}
                            disabled={defaultLoading === 'clear'}
                            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors disabled:opacity-50"
                          >
                            <FaXmark size={14} />
                            {defaultLoading === 'clear' ? 'Clearing...' : 'Clear Default'}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={() => openPreview(pkg)}
                          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-emerald-700 hover:bg-emerald-50 transition-colors"
                        >
                          <FaCalculator size={14} />
                          Preview
                        </button>
                        <button
                          type="button"
                          onClick={() => openEditPackage(pkg)}
                          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-indigo-700 hover:bg-indigo-50 transition-colors"
                        >
                          <FaPenToSquare size={14} />
                          Edit
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeletePackage(pkg.id)}
                          className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold text-red-600 hover:bg-red-50 transition-colors"
                        >
                          <FaTrash size={14} />
                          Delete
                        </button>
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </section>
      </div>

      {showPackageModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-4xl w-full border-2 border-blue-200 my-auto" padding="lg" shadow="xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900">
                {editingPackage ? 'Edit Pay-in Package' : 'Add Pay-in Package'}
              </h2>
              <button
                type="button"
                onClick={() => {
                  setShowPackageModal(false);
                  setEditingPackage(null);
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <FaXmark size={24} />
              </button>
            </div>

            <form onSubmit={handleSavePackage} className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="md:col-span-1">
                  <Input
                    label="Package Code *"
                    value={packageForm.code}
                    onChange={(e) => setPackageForm((p) => ({ ...p, code: e.target.value }))}
                    placeholder="slpe_gold_travel_lite"
                    required
                  />
                  <p className="text-xs text-gray-500 mt-1">Lowercase, underscores or hyphens.</p>
                </div>
                <Input
                  label="Display Name *"
                  value={packageForm.display_name}
                  onChange={(e) => setPackageForm((p) => ({ ...p, display_name: e.target.value }))}
                  placeholder="SLPE Gold Travel - Lite"
                  required
                />
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Provider</label>
                  <select
                    value={packageForm.provider}
                    onChange={(e) =>
                      setPackageForm((p) => {
                        const nextProvider = e.target.value;
                        const nextGateway = p.payment_gateway_id || (gateways.length ? String(gateways[0].id) : '');
                        return {
                          ...p,
                          provider: nextProvider,
                          payment_gateway_id: nextGateway,
                        };
                      })
                    }
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                  >
                    <option value="razorpay">Razorpay</option>
                    <option value="payu">PayU</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Linked Payment Gateway <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={packageForm.payment_gateway_id}
                    onChange={(e) => setPackageForm((p) => ({ ...p, payment_gateway_id: e.target.value }))}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                    required
                  >
                    <option value="">-- Select Gateway --</option>
                    {gateways.map((g) => (
                      <option key={g.id} value={g.id}>
                        {g.name}
                      </option>
                    ))}
                  </select>
                  {!packageForm.payment_gateway_id && (
                    <p className="mt-1 text-xs text-red-600">Please select a payment gateway.</p>
                  )}
                </div>
                <div className="flex items-end">
                  <label className="inline-flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={packageForm.is_active}
                      onChange={(e) => setPackageForm((p) => ({ ...p, is_active: e.target.checked }))}
                    />
                    <span className="text-sm text-gray-700">Active package</span>
                  </label>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  label="Min Amount"
                  value={packageForm.min_amount}
                  onChange={(e) => setPackageForm((p) => ({ ...p, min_amount: e.target.value }))}
                />
                <Input
                  type="number"
                  step="0.01"
                  min="0"
                  label="Max Amount / Txn"
                  value={packageForm.max_amount_per_txn}
                  onChange={(e) => setPackageForm((p) => ({ ...p, max_amount_per_txn: e.target.value }))}
                />
                <Input
                  type="number"
                  step="1"
                  min="0"
                  label="Sort Order"
                  value={packageForm.sort_order}
                  onChange={(e) => setPackageForm((p) => ({ ...p, sort_order: e.target.value }))}
                />
              </div>

              <div className="border border-gray-200 rounded-xl p-4">
                <h3 className="font-semibold text-gray-900 mb-3">Role-wise commission percentages</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {roleFields.map((f) => (
                    <div key={f.key}>
                      <Input
                        type="number"
                        step="0.0001"
                        min="0"
                        label={f.label}
                        value={packageForm[f.key]}
                        onChange={(e) => setPackageForm((p) => ({ ...p, [f.key]: e.target.value }))}
                      />
                      <p className="text-xs text-gray-500 mt-1">{f.help}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-3 p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm">
                  <span className="font-semibold text-slate-900">
                    Sum (gateway + admin + SD + MD + D): {totalDeductionPct}%
                  </span>
                  <p className="text-slate-600 mt-1 text-xs leading-relaxed">
                    Total deduction includes gateway fee, admin share, and upline commissions (SD, MD, D).
                    The remainder is credited to the user's main wallet.
                  </p>
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  onClick={() => {
                    setShowPackageModal(false);
                    setEditingPackage(null);
                  }}
                  variant="outline"
                  fullWidth
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" fullWidth loading={loading}>
                  {editingPackage ? 'Update Package' : 'Add Package'}
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {showPreviewModal && previewPackage && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-2xl w-full border-2 border-emerald-200 my-auto" padding="lg" shadow="xl">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-gray-900">
                Calculation Preview: {previewPackage.display_name}
              </h2>
              <button type="button" onClick={() => setShowPreviewModal(false)} className="text-gray-400 hover:text-gray-700">
                <FaXmark size={24} />
              </button>
            </div>
            <div className="space-y-4">
              <Input
                label="Test Amount (INR)"
                type="number"
                step="0.01"
                min="0.01"
                value={previewAmount}
                onChange={(e) => setPreviewAmount(e.target.value)}
              />
              <Button onClick={runPreview} loading={previewLoading} icon={FaCalculator} iconPosition="left">
                Run Preview
              </Button>
              {previewResult && (
                <div className="border border-gray-200 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-gray-100">
                      <tr>
                        <th className="p-2 text-left">Line</th>
                        <th className="p-2 text-right">%</th>
                        <th className="p-2 text-right">Amount</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(previewResult.lines || []).map((line) => (
                        <tr key={line.key} className="border-t">
                          <td className="p-2">{line.label}</td>
                          <td className="p-2 text-right">{line.pct}</td>
                          <td className="p-2 text-right">₹{line.amount}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <div className="p-3 bg-blue-50 border-t border-blue-100 text-sm space-y-1">
                    <div className="flex justify-between">
                      <span>Total Deduction</span>
                      <span className="font-semibold">₹{previewResult.total_deduction}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Net Credit</span>
                      <span className="font-bold text-blue-700">₹{previewResult.net_credit}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
};

export default PayInPackagesAdmin;
