/** Shared helpers for pay-in package form and list. */

import { formatDecimalInput } from '../../utils/formatters';

export const normalizeGatewayId = (value) => {
  if (value == null || value === '') return null;
  if (typeof value === 'object' && value.id != null) return String(value.id);
  return String(value);
};

export const slugifyCode = (value) =>
  String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

export const linkedGatewaysFromPackage = (pkg, allGateways = []) => {
  if (!pkg) return [];
  if (Array.isArray(pkg.package_gateways) && pkg.package_gateways.length > 0) {
    return pkg.package_gateways.map((g) => ({
      id: String(g.id),
      name: g.name || allGateways.find((x) => String(x.id) === String(g.id))?.name || `Gateway #${g.id}`,
      is_default: Boolean(g.is_default),
      status: g.status || 'active',
      gateway_fee_pct: g.gateway_fee_pct ?? g.effective_gateway_fee_pct ?? '',
      charge_rate: g.charge_rate ?? allGateways.find((x) => String(x.id) === String(g.id))?.charge_rate,
    }));
  }
  const legacyId = normalizeGatewayId(pkg.payment_gateway) || normalizeGatewayId(pkg.payment_gateway_id);
  if (legacyId) {
    const fromObj = typeof pkg.payment_gateway === 'object' ? pkg.payment_gateway : null;
    const name =
      fromObj?.name || allGateways.find((x) => String(x.id) === legacyId)?.name || `Gateway #${legacyId}`;
    return [{ id: legacyId, name, is_default: true, status: fromObj?.status || 'active' }];
  }
  return [];
};

export const linkedQrFromPackage = (pkg, allQr = []) => {
  if (!pkg) return [];
  if (Array.isArray(pkg.package_qr_accounts) && pkg.package_qr_accounts.length > 0) {
    return pkg.package_qr_accounts.map((q) => ({
      id: String(q.id),
      name: q.name || allQr.find((x) => String(x.id) === String(q.id))?.display_name || `QR #${q.id}`,
      is_default: Boolean(q.is_default),
      status: q.status || 'active',
      gateway_fee_pct: q.gateway_fee_pct ?? q.effective_gateway_fee_pct ?? '',
      charge_rate: q.charge_rate ?? allQr.find((x) => String(x.id) === String(q.id))?.charge_rate,
    }));
  }
  return [];
};

export const gatewayIdsFromPackage = (pkg, gateways) =>
  linkedGatewaysFromPackage(pkg, gateways).map((g) => g.id);

export const qrIdsFromPackage = (pkg, qrAccounts) =>
  linkedQrFromPackage(pkg, qrAccounts).map((q) => q.id);

export const defaultGatewayIdFromPackage = (pkg, gateways, ids) => {
  const linked = linkedGatewaysFromPackage(pkg, gateways);
  const def = linked.find((g) => g.is_default);
  if (def) return def.id;
  return ids[0] || '';
};

export const defaultQrIdFromPackage = (pkg, qrAccounts, ids) => {
  const linked = linkedQrFromPackage(pkg, qrAccounts);
  const def = linked.find((q) => q.is_default);
  if (def) return def.id;
  return ids[0] || '';
};

export const defaultPackageForm = (gateways = []) => {
  const defaultGatewayId = gateways.length > 0 ? String(gateways[0].id) : '';
  const gw = gateways.find((g) => String(g.id) === defaultGatewayId);
  const defaultFee = String(Math.max(1, parseFloat(gw?.charge_rate || 0)));
  return {
    code: '',
    display_name: '',
    payment_gateway_ids: defaultGatewayId ? [defaultGatewayId] : [],
    default_payment_gateway_id: defaultGatewayId,
    gateway_fees: defaultGatewayId ? { [defaultGatewayId]: defaultFee } : {},
    qr_account_ids: [],
    default_qr_account_id: '',
    qr_fees: {},
    min_amount: '1',
    max_amount_per_txn: '200000',
    admin_pct: '0.24',
    retailer_commission_pct: '0',
    super_distributor_pct: '0.01',
    master_distributor_pct: '0.02',
    distributor_pct: '0.03',
    is_active: true,
    sort_order: '0',
  };
};

export const packageFormFromPkg = (pkg, gateways, qrAccounts) => {
  const gwIds = gatewayIdsFromPackage(pkg, gateways);
  const qrIds = qrIdsFromPackage(pkg, qrAccounts);
  const gwLinked = linkedGatewaysFromPackage(pkg, gateways);
  const qrLinked = linkedQrFromPackage(pkg, qrAccounts);
  const gateway_fees = {};
  gwLinked.forEach((g) => {
    gateway_fees[g.id] =
      g.gateway_fee_pct != null && g.gateway_fee_pct !== ''
        ? formatDecimalInput(g.gateway_fee_pct)
        : '';
  });
  const qr_fees = {};
  qrLinked.forEach((q) => {
    qr_fees[q.id] =
      q.gateway_fee_pct != null && q.gateway_fee_pct !== ''
        ? formatDecimalInput(q.gateway_fee_pct)
        : '';
  });
  return {
    code: pkg.code || '',
    display_name: pkg.display_name || '',
    payment_gateway_ids: gwIds,
    default_payment_gateway_id: defaultGatewayIdFromPackage(pkg, gateways, gwIds),
    gateway_fees,
    qr_account_ids: qrIds,
    default_qr_account_id: defaultQrIdFromPackage(pkg, qrAccounts, qrIds),
    qr_fees,
    min_amount: formatDecimalInput(pkg.min_amount) || '1.00',
    max_amount_per_txn: formatDecimalInput(pkg.max_amount_per_txn) || '200000.00',
    admin_pct: formatDecimalInput(pkg.admin_pct) || '0.00',
    retailer_commission_pct: '0.00',
    super_distributor_pct: formatDecimalInput(pkg.super_distributor_pct) || '0.00',
    master_distributor_pct: formatDecimalInput(pkg.master_distributor_pct) || '0.00',
    distributor_pct: formatDecimalInput(pkg.distributor_pct) || '0.00',
    is_active: Boolean(pkg.is_active),
    sort_order: pkg.sort_order?.toString?.() || '0',
  };
};

export const slabsFromPackage = (pkg) => {
  const tiers = pkg?.payout_slabs;
  if (!tiers || tiers.length === 0) return null;
  if (typeof tiers === 'number') return null;
  return tiers.map((t, i) => ({
    sort_order: t.sort_order ?? i,
    min_amount: t.min_amount != null ? String(t.min_amount) : '0',
    max_amount: t.max_amount == null || t.max_amount === '' ? '' : String(t.max_amount),
    flat_charge: t.flat_charge != null ? String(t.flat_charge) : '0',
  }));
};

export const maxRailFeeFromForm = (selectedGatewayRows, selectedQrRows) => {
  const fees = [];
  selectedGatewayRows.forEach((g) => {
    const n = parseFloat(g.gateway_fee_pct);
    if (!Number.isNaN(n)) fees.push(n);
  });
  selectedQrRows.forEach((q) => {
    const n = parseFloat(q.gateway_fee_pct);
    if (!Number.isNaN(n)) fees.push(n);
  });
  return fees.length ? Math.max(...fees) : 0;
};
