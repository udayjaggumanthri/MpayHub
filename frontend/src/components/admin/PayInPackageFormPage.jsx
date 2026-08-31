import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import LoadingSpinner from '../common/LoadingSpinner';
import GatewayFlowStepper from './GatewayFlowStepper';
import SelectField from '../common/SelectField';
import {
  packageCommissionFields,
  firstErrorMessage,
  parseList,
} from './gatewayAdminShared';
import {
  defaultPackageForm,
  linkedGatewaysFromPackage,
  linkedQrFromPackage,
  maxRailFeeFromForm,
  packageFormFromPkg,
  slabsFromPackage,
  slugifyCode,
} from './payInPackageFormShared';
import {
  FaArrowLeft,
  FaCreditCard,
  FaPlus,
  FaStar,
  FaXmark,
} from 'react-icons/fa6';

const PayInPackageFormPage = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);
  const [gateways, setGateways] = useState([]);
  const [qrAccounts, setQrAccounts] = useState([]);
  const [editingPackage, setEditingPackage] = useState(null);
  const [pageLoading, setPageLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [gatewayPickerId, setGatewayPickerId] = useState('');
  const [qrPickerId, setQrPickerId] = useState('');
  const [packagePayoutSlabs, setPackagePayoutSlabs] = useState([]);
  const [payoutSlabForm, setPayoutSlabForm] = useState({
    low_max_amount: '24999',
    low_charge: '7',
    high_charge: '15',
  });
  const [packageForm, setPackageForm] = useState(defaultPackageForm());

  const buildDefaultPayoutSlabsFromGlobal = () => {
    const lowMax = payoutSlabForm.low_max_amount || '24999';
    const lowC = payoutSlabForm.low_charge || '7';
    const highC = payoutSlabForm.high_charge || '15';
    const nextMin = (parseFloat(lowMax, 10) + 0.0001).toFixed(4);
    return [
      { sort_order: 0, min_amount: '0', max_amount: String(lowMax), flat_charge: String(lowC) },
      { sort_order: 1, min_amount: nextMin, max_amount: '', flat_charge: String(highC) },
    ];
  };

  useEffect(() => {
    const load = async () => {
      setPageLoading(true);
      const [gRes, qrRes, sRes] = await Promise.all([
        adminAPI.listPaymentGateways(),
        adminAPI.listPayInQrAccounts({ page_size: 100 }),
        adminAPI.getPayoutSlabConfig(),
      ]);
      const gwList = gRes.success ? parseList(gRes) : [];
      setGateways(gwList);
      if (qrRes.success) setQrAccounts(qrRes.data?.results || []);
      if (sRes.success && sRes.data?.config) {
        const cfg = sRes.data.config;
        setPayoutSlabForm({
          low_max_amount: String(cfg.low_max_amount ?? '24999'),
          low_charge: String(cfg.low_charge ?? '7'),
          high_charge: String(cfg.high_charge ?? '15'),
        });
      }

      if (isEdit) {
        const res = await adminAPI.getPayInPackage(id);
        if (res.success && res.data) {
          setEditingPackage(res.data);
          setPackageForm(packageFormFromPkg(res.data, gwList, qrRes.data?.results || []));
          setPackagePayoutSlabs(
            slabsFromPackage(res.data) || buildDefaultPayoutSlabsFromGlobal()
          );
        }
      } else {
        setPackageForm(defaultPackageForm(gwList));
        setPackagePayoutSlabs(buildDefaultPayoutSlabsFromGlobal());
      }
      setPageLoading(false);
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, isEdit]);

  const defaultRailFee = (floorPct) => {
    const floor = parseFloat(floorPct || 0);
    return String(Math.max(floor, floor > 0 ? floor : 0));
  };

  const selectedGatewayRows = packageForm.payment_gateway_ids.map((gid) => {
    const fromCatalog = gateways.find((g) => String(g.id) === String(gid));
    const fromPkg = editingPackage ? linkedGatewaysFromPackage(editingPackage, gateways) : [];
    const fromPkgRow = fromPkg.find((g) => g.id === String(gid));
    const chargeRate = fromCatalog?.charge_rate ?? fromPkgRow?.charge_rate ?? '0';
    return {
      id: String(gid),
      name: fromCatalog?.name || fromPkgRow?.name || `Gateway #${gid}`,
      status: fromCatalog?.status || fromPkgRow?.status || 'active',
      charge_rate: chargeRate,
      gateway_fee_pct:
        packageForm.gateway_fees?.[String(gid)] ??
        (fromPkgRow?.gateway_fee_pct != null
          ? String(fromPkgRow.gateway_fee_pct)
          : defaultRailFee(chargeRate)),
    };
  });

  const selectedQrRows = packageForm.qr_account_ids.map((qid) => {
    const fromCatalog = qrAccounts.find((q) => String(q.id) === String(qid));
    const fromPkg = editingPackage ? linkedQrFromPackage(editingPackage, qrAccounts) : [];
    const fromPkgRow = fromPkg.find((q) => q.id === String(qid));
    const chargeRate = fromCatalog?.charge_rate ?? fromPkgRow?.charge_rate ?? '0';
    return {
      id: String(qid),
      name: fromCatalog?.display_name || fromPkgRow?.name || `QR #${qid}`,
      status: fromCatalog?.status || fromPkgRow?.status || 'active',
      charge_rate: chargeRate,
      gateway_fee_pct:
        packageForm.qr_fees?.[String(qid)] ??
        (fromPkgRow?.gateway_fee_pct != null
          ? String(fromPkgRow.gateway_fee_pct)
          : defaultRailFee(chargeRate)),
    };
  });

  const availableGatewaysToAdd = gateways.filter(
    (g) => !packageForm.payment_gateway_ids.includes(String(g.id))
  );
  const availableQrToAdd = qrAccounts.filter(
    (q) => !packageForm.qr_account_ids.includes(String(q.id))
  );

  const totalDeductionPct = useMemo(() => {
    const maxGw = maxRailFeeFromForm(selectedGatewayRows, selectedQrRows);
    return (
      maxGw +
      parseFloat(packageForm.admin_pct || 0) +
      parseFloat(packageForm.super_distributor_pct || 0) +
      parseFloat(packageForm.master_distributor_pct || 0) +
      parseFloat(packageForm.distributor_pct || 0)
    ).toFixed(4);
  }, [packageForm, selectedGatewayRows, selectedQrRows]);

  const addGatewayFromPicker = () => {
    if (!gatewayPickerId) return;
    const gid = String(gatewayPickerId);
    const gw = gateways.find((g) => String(g.id) === gid);
    setPackageForm((prev) => {
      if (prev.payment_gateway_ids.includes(gid)) return prev;
      const nextIds = [...prev.payment_gateway_ids, gid];
      const fee = defaultRailFee(gw?.charge_rate);
      return {
        ...prev,
        payment_gateway_ids: nextIds,
        default_payment_gateway_id: prev.default_payment_gateway_id || gid,
        gateway_fees: { ...prev.gateway_fees, [gid]: fee },
      };
    });
    setGatewayPickerId('');
  };

  const setGatewayFee = (gatewayId, value) => {
    const gid = String(gatewayId);
    setPackageForm((prev) => ({
      ...prev,
      gateway_fees: { ...prev.gateway_fees, [gid]: value },
    }));
  };

  const removePackageGateway = (gatewayId) => {
    const gid = String(gatewayId);
    setPackageForm((prev) => {
      const nextIds = prev.payment_gateway_ids.filter((id) => id !== gid);
      let nextDefault = prev.default_payment_gateway_id;
      if (nextDefault === gid) nextDefault = nextIds[0] || '';
      const nextFees = { ...prev.gateway_fees };
      delete nextFees[gid];
      return {
        ...prev,
        payment_gateway_ids: nextIds,
        default_payment_gateway_id: nextDefault,
        gateway_fees: nextFees,
      };
    });
  };

  const addQrFromPicker = () => {
    if (!qrPickerId) return;
    const qid = String(qrPickerId);
    const qr = qrAccounts.find((q) => String(q.id) === qid);
    setPackageForm((prev) => {
      if (prev.qr_account_ids.includes(qid)) return prev;
      const nextIds = [...prev.qr_account_ids, qid];
      const fee = defaultRailFee(qr?.charge_rate);
      return {
        ...prev,
        qr_account_ids: nextIds,
        default_qr_account_id: prev.default_qr_account_id || qid,
        qr_fees: { ...prev.qr_fees, [qid]: fee },
      };
    });
    setQrPickerId('');
  };

  const setQrFee = (qrId, value) => {
    const qid = String(qrId);
    setPackageForm((prev) => ({
      ...prev,
      qr_fees: { ...prev.qr_fees, [qid]: value },
    }));
  };

  const removePackageQr = (qrId) => {
    const qid = String(qrId);
    setPackageForm((prev) => {
      const nextIds = prev.qr_account_ids.filter((id) => id !== qid);
      let nextDefault = prev.default_qr_account_id;
      if (nextDefault === qid) nextDefault = nextIds[0] || '';
      const nextFees = { ...prev.qr_fees };
      delete nextFees[qid];
      return {
        ...prev,
        qr_account_ids: nextIds,
        default_qr_account_id: nextDefault,
        qr_fees: nextFees,
      };
    });
  };

  const addPayoutSlabRow = () => {
    setPackagePayoutSlabs((rows) => {
      const next = [...rows];
      const lastMax = next.length ? next[next.length - 1].max_amount : '0';
      const minStart =
        lastMax === '' || lastMax == null ? '0' : (parseFloat(lastMax, 10) + 0.0001).toFixed(4);
      next.push({ sort_order: next.length, min_amount: minStart, max_amount: '', flat_charge: '7' });
      return next;
    });
  };

  const removePayoutSlabRow = (index) => {
    setPackagePayoutSlabs((rows) => rows.filter((_, i) => i !== index));
  };

  const updatePayoutSlabRow = (index, field, value) => {
    setPackagePayoutSlabs((rows) => {
      const next = [...rows];
      next[index] = { ...next[index], [field]: value };
      return next;
    });
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!packageForm.code || !packageForm.display_name) {
      alert('Code and Display Name are required');
      return;
    }
    if (!packageForm.payment_gateway_ids?.length) {
      alert('Select at least one payment gateway for this package.');
      return;
    }
    const defaultGw = packageForm.default_payment_gateway_id || packageForm.payment_gateway_ids[0];
    setSaving(true);
    const payout_slabs = packagePayoutSlabs.map((row, i) => ({
      sort_order: i,
      min_amount: row.min_amount,
      max_amount: row.max_amount === '' || row.max_amount == null ? null : row.max_amount,
      flat_charge: row.flat_charge,
    }));

    const payload = {
      code: packageForm.code.trim(),
      display_name: packageForm.display_name.trim(),
      payment_gateway_ids: packageForm.payment_gateway_ids.map((gid) => Number(gid)),
      default_payment_gateway_id: Number(defaultGw),
      payment_gateway_id: Number(defaultGw),
      package_gateways: selectedGatewayRows.map((g) => ({
        id: Number(g.id),
        payment_gateway_id: Number(g.id),
        gateway_fee_pct: g.gateway_fee_pct,
      })),
      qr_account_ids: (packageForm.qr_account_ids || []).map((qid) => Number(qid)),
      default_qr_account_id: packageForm.default_qr_account_id
        ? Number(packageForm.default_qr_account_id)
        : null,
      package_qr_accounts: selectedQrRows.map((q) => ({
        id: Number(q.id),
        qr_account_id: Number(q.id),
        gateway_fee_pct: q.gateway_fee_pct,
      })),
      min_amount: packageForm.min_amount,
      max_amount_per_txn: packageForm.max_amount_per_txn,
      admin_pct: packageForm.admin_pct,
      retailer_commission_pct: '0',
      super_distributor_pct: packageForm.super_distributor_pct,
      master_distributor_pct: packageForm.master_distributor_pct,
      distributor_pct: packageForm.distributor_pct,
      is_active: packageForm.is_active,
      sort_order: Number(packageForm.sort_order || 0),
      is_default: editingPackage ? !!editingPackage.is_default : false,
      payout_slabs,
    };

    const result = isEdit
      ? await adminAPI.updatePayInPackage(id, payload)
      : await adminAPI.createPayInPackage(payload);
    setSaving(false);
    if (!result.success) {
      alert(firstErrorMessage(result, 'Could not save pay-in package'));
      return;
    }
    navigate('/admin/pay-in-packages');
  };

  if (pageLoading) {
    return (
      <div className="flex justify-center py-20">
        <LoadingSpinner />
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-slate-50/80 dark:to-slate-900/80">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <GatewayFlowStepper
          currentStep="payin-packages"
          subtitle={isEdit ? 'Edit package configuration' : 'Create a new commercial package'}
        />

        <div className="flex items-center gap-3">
          <Link
            to="/admin/pay-in-packages"
            className="inline-flex items-center gap-2 text-sm font-semibold text-indigo-700 dark:text-indigo-300 hover:underline"
          >
            <FaArrowLeft size={14} />
            Back to packages
          </Link>
        </div>

        <header>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">
            {isEdit ? `Edit: ${editingPackage?.display_name || 'Package'}` : 'New commercial package'}
          </h1>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Set per-gateway and per-QR fees, commission splits, and payout slabs.
          </p>
        </header>

        <form onSubmit={handleSave} className="space-y-6 pb-24">
          <Card shadow="sm" padding="lg">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <Input
                  label="Package Code *"
                  value={packageForm.code}
                  onChange={(e) => setPackageForm((p) => ({ ...p, code: e.target.value }))}
                  onBlur={(e) =>
                    setPackageForm((p) => ({ ...p, code: slugifyCode(e.target.value) || p.code }))
                  }
                  placeholder="qr-test"
                  required
                />
                <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">
                  Saved as: <span className="font-mono">{slugifyCode(packageForm.code) || '—'}</span>
                </p>
              </div>
              <Input
                label="Display Name *"
                value={packageForm.display_name}
                onChange={(e) => setPackageForm((p) => ({ ...p, display_name: e.target.value }))}
                required
              />
            </div>

            <label className="inline-flex items-center gap-2 cursor-pointer mt-4">
              <input
                type="checkbox"
                checked={packageForm.is_active}
                onChange={(e) => setPackageForm((p) => ({ ...p, is_active: e.target.checked }))}
              />
              <span className="text-sm text-gray-700 dark:text-slate-300">Active package</span>
            </label>
          </Card>

          <Card shadow="sm" padding="lg" title="Payment gateways">
            <p className="text-xs text-slate-600 dark:text-slate-400 mb-4">
              Set gateway fee % per rail. Minimum fee comes from Payment Gateways admin.
            </p>
            {selectedGatewayRows.length === 0 ? (
              <p className="text-sm text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 rounded-lg px-3 py-2 mb-4">
                No gateway linked. Add one below — at least one is required before saving.
              </p>
            ) : (
              <ul className="space-y-2 mb-4">
                {selectedGatewayRows.map((g) => {
                  const isDefault = packageForm.default_payment_gateway_id === g.id;
                  return (
                    <li
                      key={g.id}
                      className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2.5 bg-white dark:bg-slate-900"
                    >
                      <span className="font-medium text-sm flex-1 min-w-[120px]">{g.name}</span>
                      <label className="text-xs shrink-0">
                        Fee %
                        <input
                          type="number"
                          step="0.0001"
                          min={g.charge_rate || 0}
                          className="ml-1 w-20 rounded border px-2 py-1 text-sm"
                          value={g.gateway_fee_pct}
                          onChange={(e) => setGatewayFee(g.id, e.target.value)}
                        />
                        <span className="block text-[10px] text-slate-500">Min {g.charge_rate ?? 0}%</span>
                      </label>
                      <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                        <input
                          type="radio"
                          name="default_payin_gateway"
                          checked={isDefault}
                          onChange={() =>
                            setPackageForm((p) => ({ ...p, default_payment_gateway_id: g.id }))
                          }
                        />
                        <FaStar className={isDefault ? 'text-amber-500' : 'text-gray-300'} size={12} />
                        {isDefault ? 'Default' : 'Set default'}
                      </label>
                      <button
                        type="button"
                        onClick={() => removePackageGateway(g.id)}
                        className="text-xs font-semibold text-red-700 hover:underline"
                        title="Remove this gateway from the package"
                      >
                        Remove
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {availableGatewaysToAdd.length > 0 && (
              <div className="flex flex-col sm:flex-row gap-2">
                <SelectField
                  value={gatewayPickerId}
                  onChange={(val) => setGatewayPickerId(val)}
                  options={availableGatewaysToAdd}
                  getOptionLabel={(g) => g.name}
                  getOptionValue={(g) => g.id}
                  placeholder="Choose gateway…"
                  className="flex-1"
                />
                <Button type="button" onClick={addGatewayFromPicker} disabled={!gatewayPickerId}>
                  Add gateway
                </Button>
              </div>
            )}
          </Card>

          <Card shadow="sm" padding="lg" title="Linked QR accounts (optional)">
            {selectedQrRows.length === 0 ? (
              <p className="text-sm text-slate-500">No QR accounts linked.</p>
            ) : (
              <ul className="space-y-2 mb-4">
                {selectedQrRows.map((q) => {
                  const isDefault = packageForm.default_qr_account_id === q.id;
                  return (
                    <li key={q.id} className="flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2.5">
                      <span className="font-medium text-sm flex-1">{q.name}</span>
                      <label className="text-xs shrink-0">
                        Fee %
                        <input
                          type="number"
                          step="0.0001"
                          min={q.charge_rate || 0}
                          className="ml-1 w-20 rounded border px-2 py-1 text-sm"
                          value={q.gateway_fee_pct}
                          onChange={(e) => setQrFee(q.id, e.target.value)}
                        />
                        <span className="block text-[10px] text-slate-500">Min {q.charge_rate ?? 0}%</span>
                      </label>
                      <label className="inline-flex items-center gap-1.5 text-xs cursor-pointer">
                        <input
                          type="radio"
                          name="default_payin_qr"
                          checked={isDefault}
                          onChange={() =>
                            setPackageForm((p) => ({ ...p, default_qr_account_id: q.id }))
                          }
                        />
                        {isDefault ? 'Default' : 'Set default'}
                      </label>
                      <button
                        type="button"
                        onClick={() => removePackageQr(q.id)}
                        className="text-xs font-semibold text-red-700"
                      >
                        Remove
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {availableQrToAdd.length > 0 && (
              <div className="flex flex-col sm:flex-row gap-2">
                <SelectField
                  value={qrPickerId}
                  onChange={(val) => setQrPickerId(val)}
                  options={availableQrToAdd}
                  getOptionLabel={(q) => q.display_name}
                  getOptionValue={(q) => q.id}
                  placeholder="Choose QR account…"
                  className="flex-1"
                />
                <Button type="button" onClick={addQrFromPicker} disabled={!qrPickerId}>
                  Add QR
                </Button>
              </div>
            )}
          </Card>

          <Card shadow="sm" padding="lg">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Input
                type="number"
                label="Min Amount"
                value={packageForm.min_amount}
                onChange={(e) => setPackageForm((p) => ({ ...p, min_amount: e.target.value }))}
              />
              <Input
                type="number"
                label="Max Amount / Txn"
                value={packageForm.max_amount_per_txn}
                onChange={(e) => setPackageForm((p) => ({ ...p, max_amount_per_txn: e.target.value }))}
              />
              <Input
                type="number"
                label="Sort Order"
                value={packageForm.sort_order}
                onChange={(e) => setPackageForm((p) => ({ ...p, sort_order: e.target.value }))}
              />
            </div>
          </Card>

          <Card shadow="sm" padding="lg" title="Role-wise commission percentages">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {packageCommissionFields.map((f) => (
                <div key={f.key}>
                  <Input
                    type="number"
                    step="0.0001"
                    min="0"
                    label={f.label}
                    value={packageForm[f.key]}
                    onChange={(e) => setPackageForm((p) => ({ ...p, [f.key]: e.target.value }))}
                  />
                  <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">{f.help}</p>
                </div>
              ))}
            </div>
            <div className="mt-3 p-3 bg-slate-50 dark:bg-slate-800/50 border rounded-xl text-sm">
              <span className="font-semibold">
                Sum (max rail fee + admin + SD + MD + D): {totalDeductionPct}%
              </span>
              <p className="text-slate-600 dark:text-slate-400 mt-1 text-xs">
                Gateway fee is set per gateway/QR above — not added again here.
              </p>
            </div>
          </Card>

          <Card shadow="sm" padding="lg" title="Payout slabs (this package)">
            <div className="flex justify-between items-center mb-3">
              <p className="text-xs text-slate-600 dark:text-slate-400">
                Bands must start at 0 and be contiguous. Last row may leave max empty.
              </p>
              <Button type="button" variant="outline" size="sm" icon={FaPlus} onClick={addPayoutSlabRow}>
                Add tier
              </Button>
            </div>
            <div className="space-y-2">
              {packagePayoutSlabs.map((row, idx) => (
                <div
                  key={`slab-${idx}`}
                  className="grid grid-cols-1 sm:grid-cols-12 gap-2 items-end border rounded-lg p-3"
                >
                  <div className="sm:col-span-3">
                    <label className="block text-xs font-medium mb-1">Min amount</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border rounded-lg text-sm"
                      value={row.min_amount}
                      onChange={(e) => updatePayoutSlabRow(idx, 'min_amount', e.target.value)}
                    />
                  </div>
                  <div className="sm:col-span-3">
                    <label className="block text-xs font-medium mb-1">Max (blank = ∞)</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border rounded-lg text-sm"
                      value={row.max_amount}
                      onChange={(e) => updatePayoutSlabRow(idx, 'max_amount', e.target.value)}
                    />
                  </div>
                  <div className="sm:col-span-3">
                    <label className="block text-xs font-medium mb-1">Flat charge (₹)</label>
                    <input
                      type="text"
                      className="w-full px-3 py-2 border rounded-lg text-sm"
                      value={row.flat_charge}
                      onChange={(e) => updatePayoutSlabRow(idx, 'flat_charge', e.target.value)}
                    />
                  </div>
                  <div className="sm:col-span-3 flex justify-end">
                    {packagePayoutSlabs.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removePayoutSlabRow(idx)}
                        className="text-sm font-semibold text-red-600"
                      >
                        Remove
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <div className="fixed bottom-0 left-0 right-0 z-40 border-t bg-white/95 dark:bg-slate-900/95 backdrop-blur px-4 py-3">
            <div className="max-w-5xl mx-auto flex gap-3">
              <Button type="button" variant="outline" fullWidth onClick={() => navigate('/admin/pay-in-packages')}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" fullWidth loading={saving}>
                {isEdit ? 'Update package' : 'Create package'}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
};

export default PayInPackageFormPage;
