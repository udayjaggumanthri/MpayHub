import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { bbpsAPI, billAvenueAdminAPI } from '../../services/api';

const Section = ({ title, children }) => (
  <div className="bg-white rounded-xl border border-gray-200">
    <div className="px-4 py-3 border-b border-gray-100 font-semibold text-gray-800">{title}</div>
    <div className="p-4">{children}</div>
  </div>
);

const SimpleTable = ({ columns, rows, rowClassName = null }) => (
  <div className="overflow-auto border border-gray-100 rounded-lg">
    <table className="w-full text-xs">
      <thead className="bg-gray-50">
        <tr>
          {columns.map((c) => <th key={c.key} className="text-left p-2">{c.label}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.length === 0 ? (
          <tr><td className="p-3 text-gray-500" colSpan={columns.length}>No records</td></tr>
        ) : rows.map((r, idx) => (
          <tr key={idx} className={`border-t ${rowClassName ? rowClassName(r) : ''}`}>
            {columns.map((c) => (
              <td key={c.key} className="p-2">
                {React.isValidElement(r[c.key]) ? r[c.key] : String(r[c.key] ?? '-')}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

const flattenObject = (value, prefix = '', out = []) => {
  if (value === null || value === undefined) {
    out.push({ path: prefix || '(root)', value: '-' });
    return out;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) {
      out.push({ path: prefix || '(root)', value: '[]' });
      return out;
    }
    value.forEach((item, idx) => flattenObject(item, `${prefix}[${idx}]`, out));
    return out;
  }
  if (typeof value === 'object') {
    const keys = Object.keys(value);
    if (keys.length === 0) {
      out.push({ path: prefix || '(root)', value: '{}' });
      return out;
    }
    keys.forEach((k) => {
      const next = prefix ? `${prefix}.${k}` : k;
      flattenObject(value[k], next, out);
    });
    return out;
  }
  out.push({ path: prefix || '(value)', value: String(value) });
  return out;
};

const escapeXml = (value) => String(value)
  .replace(/&/g, '&amp;')
  .replace(/</g, '&lt;')
  .replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;')
  .replace(/'/g, '&apos;');

const toXml = (obj, nodeName = 'billerInfoResponse') => {
  if (obj === null || obj === undefined) return `<${nodeName}></${nodeName}>`;
  if (Array.isArray(obj)) return obj.map((item) => toXml(item, nodeName)).join('');
  if (typeof obj === 'object') {
    const inner = Object.entries(obj).map(([k, v]) => toXml(v, k)).join('');
    return `<${nodeName}>${inner}</${nodeName}>`;
  }
  return `<${nodeName}>${escapeXml(obj)}</${nodeName}>`;
};

const BbpsBillerDetails = () => {
  const { billerPk } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [pullingPlans, setPullingPlans] = useState(false);
  const [togglingLocal, setTogglingLocal] = useState(false);
  const [error, setError] = useState('');
  const [biller, setBiller] = useState(null);
  const [catalogSummary, setCatalogSummary] = useState(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [mappingLoading, setMappingLoading] = useState(false);
  const [mappingSaving, setMappingSaving] = useState(false);
  const [mappingData, setMappingData] = useState(null);
  const [allowedChannels, setAllowedChannels] = useState([]);
  const [showFullResponse, setShowFullResponse] = useState(false);
  const [info, setInfo] = useState('');
  const [lastPlanPullResult, setLastPlanPullResult] = useState(null);
  const [changedFieldMap, setChangedFieldMap] = useState({});
  const [changedCount, setChangedCount] = useState(0);

  const loadCatalogSummary = useCallback(async (billerId) => {
    if (!billerId) {
      setCatalogSummary(null);
      return;
    }
    setCatalogLoading(true);
    const sum = await bbpsAPI.getBillerCatalogSummary(billerId);
    setCatalogLoading(false);
    if (sum.success) {
      setCatalogSummary(sum.data);
    } else {
      setCatalogSummary(null);
    }
  }, []);

  const loadPaymentMapping = useCallback(async (billerId) => {
    if (!billerId) {
      setMappingData(null);
      setAllowedChannels([]);
      return;
    }
    setMappingLoading(true);
    const res = await billAvenueAdminAPI.getBillerPaymentMapping(billerId);
    setMappingLoading(false);
    if (!res.success) {
      setMappingData(null);
      setAllowedChannels([]);
      return;
    }
    setMappingData(res.data || null);
    const matrix = Array.isArray(res.data?.matrix) ? res.data.matrix : [];
    const allowed = [...new Set(
      matrix
        .filter((r) => r.policy_action === 'allow')
        .map((r) => String(r.payment_channel || '').trim().toUpperCase())
        .filter(Boolean),
    )];
    setAllowedChannels(allowed.length ? allowed : (res.data?.mdm_channels || []));
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await billAvenueAdminAPI.getBillerMasterDetails(billerPk);
    if (!res.success) {
      setError(res.message || 'Failed to load biller details');
      setLoading(false);
      return null;
    }
    const data = res.data?.biller || null;
    setBiller(data);
    setLoading(false);
    if (data?.biller_id) {
      await loadCatalogSummary(data.biller_id);
      await loadPaymentMapping(data.biller_id);
    } else {
      setCatalogSummary(null);
      setMappingData(null);
      setAllowedChannels([]);
    }
    return data;
  }, [billerPk, loadCatalogSummary, loadPaymentMapping]);

  useEffect(() => {
    load();
  }, [load]);

  const syncThisBiller = async () => {
    if (!biller?.biller_id) return;
    const beforeRaw = biller.raw_payload || {};
    setSyncing(true);
    setError('');
    setInfo('');
    setChangedFieldMap({});
    setChangedCount(0);
    const res = await bbpsAPI.syncBillers([biller.biller_id]);
    if (!res.success) {
      setError(res.message || 'Failed to sync this biller');
      setSyncing(false);
      return;
    }
    const recommended = res.data?.plan_pull_recommended || [];
    const suggestPull = Array.isArray(recommended) && recommended.includes(String(biller.biller_id).trim());
    const updated = await load();
    const afterRaw = updated?.raw_payload || {};
    const beforeFlat = flattenObject(beforeRaw);
    const afterFlat = flattenObject(afterRaw);
    const beforeMap = Object.fromEntries(beforeFlat.map((r) => [r.path, r.value]));
    const afterMap = Object.fromEntries(afterFlat.map((r) => [r.path, r.value]));
    const allPaths = new Set([...Object.keys(beforeMap), ...Object.keys(afterMap)]);
    const changed = {};
    let totalChanged = 0;
    allPaths.forEach((path) => {
      const oldVal = beforeMap[path] ?? '(missing)';
      const newVal = afterMap[path] ?? '(missing)';
      if (oldVal !== newVal) {
        changed[path] = { old: oldVal, new: newVal };
        totalChanged += 1;
      }
    });
    setChangedFieldMap(changed);
    setChangedCount(totalChanged);
    const planNote = suggestPull
      ? ' BillAvenue indicates plan metadata may apply — use Pull plans when ready (avoids surprise quota use).'
      : '';
    setInfo(`Biller synced successfully. ${totalChanged} field(s) changed from previous snapshot.${planNote}`);
    setSyncing(false);
  };

  const pullPlansForThisBiller = async () => {
    if (!biller?.biller_id) return;
    setPullingPlans(true);
    setError('');
    setInfo('');
    const res = await bbpsAPI.pullPlans([biller.biller_id]);
    if (!res.success) {
      setError(res.message || 'Plan pull failed');
      setPullingPlans(false);
      return;
    }
    setLastPlanPullResult(res.data || null);
    await load();
    setInfo('Plan pull completed for this biller.');
    setPullingPlans(false);
  };

  const toggleLocalActive = async () => {
    if (!billerPk || !biller) return;
    setTogglingLocal(true);
    setError('');
    setInfo('');
    const res = biller.is_active_local
      ? await billAvenueAdminAPI.disableBillerMaster(billerPk)
      : await billAvenueAdminAPI.enableBillerMaster(billerPk);
    if (!res.success) {
      setError(res.message || 'Could not update local active flag');
      setTogglingLocal(false);
      return;
    }
    await load();
    setInfo(`Biller ${biller.is_active_local ? 'disabled' : 'enabled'} locally.`);
    setTogglingLocal(false);
  };

  const downloadAudit = (format) => {
    const payload = biller?.raw_payload || {};
    const ts = new Date().toISOString().replace(/[:.]/g, '-');
    const base = `${biller?.biller_id || 'biller'}-${ts}`;
    const content = format === 'xml'
      ? `<?xml version="1.0" encoding="UTF-8"?>\n${toXml(payload, 'billerInfoResponse')}`
      : JSON.stringify(payload, null, 2);
    const type = format === 'xml' ? 'application/xml' : 'application/json';
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${base}.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  const toggleAllowedChannel = (code) => {
    const ch = String(code || '').trim().toUpperCase();
    if (!ch) return;
    setAllowedChannels((prev) => (
      prev.includes(ch) ? prev.filter((x) => x !== ch) : [...prev, ch]
    ));
  };

  const savePaymentMapping = async () => {
    if (!biller?.biller_id) return;
    if (!allowedChannels.length) {
      setError('Select at least one allowed payment channel.');
      return;
    }
    setMappingSaving(true);
    setError('');
    setInfo('');
    const res = await billAvenueAdminAPI.saveBillerPaymentMapping(biller.biller_id, {
      allowed_channels: allowedChannels,
    });
    setMappingSaving(false);
    if (!res.success) {
      setError(res.message || 'Failed to save payment mapping');
      return;
    }
    await load();
    setInfo(`Payment mapping saved. Allowed channels: ${allowedChannels.join(', ')}`);
  };

  if (loading) return <div className="max-w-7xl mx-auto text-sm text-gray-500">Loading biller details...</div>;
  if (error) return <div className="max-w-7xl mx-auto text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">{error}</div>;
  if (!biller) return <div className="max-w-7xl mx-auto text-sm text-gray-500">Biller not found.</div>;
  const rawPayload = biller.raw_payload || {};
  const flattened = flattenObject(rawPayload);
  const expectedInputRows = flattened.filter(
    (row) => row.path.includes('billerInputParams') || row.path.toLowerCase().includes('paraminfo'),
  );
  const supportedChannels = [...new Set(
    ((rawPayload?.billerPaymentChannels?.paymentChannelInfo || []).map((x) => String(x?.paymentChannelName || '').trim().toUpperCase()).filter(Boolean))
  )];
  const supportedModes = [...new Set(
    ((rawPayload?.billerPaymentModes?.paymentModeInfo || []).map((x) => String(x?.paymentMode || x?.paymentModeName || '').trim()).filter(Boolean))
  )];
  const supportedPlansLite = Array.isArray(catalogSummary?.pay_ui_projection?.plans_lite)
    ? catalogSummary.pay_ui_projection.plans_lite
    : [];
  const supportedPlansAdmin = Array.isArray(biller?.plans) ? biller.plans : [];
  const supportedPlans = supportedPlansAdmin.length ? supportedPlansAdmin : supportedPlansLite;
  const planReq = String(biller?.plan_mdm_requirement || '').toUpperCase();
  const isPlanEligible = (
    planReq.includes('OPTIONAL')
    || planReq.includes('MANDATORY')
    || planReq === 'SUPPORTED'
    || ['Y', 'YES', 'TRUE', '1'].includes(planReq)
  );
  const latestPlanPull = catalogSummary?.latest_plan_pull || null;
  const planPullView = lastPlanPullResult || latestPlanPull;

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">{biller.biller_name || 'Biller Details'}</h1>
          <p className="text-sm text-gray-600">Biller ID: <span className="font-mono">{biller.biller_id}</span></p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={syncThisBiller}
            disabled={syncing}
            className="px-3 py-2 border rounded text-sm bg-blue-600 text-white disabled:opacity-50"
          >
            {syncing ? 'Syncing...' : 'Sync MDM'}
          </button>
          {isPlanEligible ? (
            <button
              type="button"
              onClick={pullPlansForThisBiller}
              disabled={pullingPlans || !biller?.biller_id}
              className="px-3 py-2 border rounded text-sm bg-emerald-700 text-white disabled:opacity-50"
            >
              {pullingPlans ? 'Pulling plans...' : 'Pull plans'}
            </button>
          ) : null}
          <button
            type="button"
            onClick={toggleLocalActive}
            disabled={togglingLocal}
            className="px-3 py-2 border rounded text-sm bg-slate-700 text-white disabled:opacity-50"
          >
            {togglingLocal ? 'Updating...' : biller.is_active_local ? 'Disable locally' : 'Enable locally'}
          </button>
          <button type="button" onClick={() => navigate(-1)} className="px-3 py-2 border rounded text-sm">Back</button>
          <Link to="/admin/bbps-governance" className="px-3 py-2 border rounded text-sm bg-slate-50">Governance</Link>
          <button
            type="button"
            onClick={() => setShowFullResponse((v) => !v)}
            className="px-3 py-2 border rounded text-sm bg-slate-50"
          >
            {showFullResponse ? 'Hide full response' : 'See full response'}
          </button>
          <button type="button" onClick={() => downloadAudit('json')} className="px-3 py-2 border rounded text-sm bg-slate-50">Download JSON</button>
          <button type="button" onClick={() => downloadAudit('xml')} className="px-3 py-2 border rounded text-sm bg-slate-50">Download XML</button>
        </div>
      </div>
      {info ? <div className="text-sm text-green-700 bg-green-50 border border-green-200 rounded p-3">{info}</div> : null}

      <Section title="Overview">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div className="border rounded p-3">Category: <strong>{biller.biller_category || '-'}</strong></div>
          <div className="border rounded p-3">Status: <strong>{biller.biller_status || '-'}</strong></div>
          <div className="border rounded p-3">Local Active: <strong>{biller.is_active_local ? 'Yes' : 'No'}</strong></div>
          <div className="border rounded p-3">Plan MDM requirement: <strong>{biller.plan_mdm_requirement || '-'}</strong></div>
          <div className="border rounded p-3">Source: <strong>{biller.source_type || '-'}</strong></div>
          <div className="border rounded p-3">Last Sync Status: <strong>{biller.last_sync_status || '-'}</strong></div>
          <div className="border rounded p-3">Version: <strong>{biller.version || 1}</strong></div>
        </div>
      </Section>

      <Section title="Plan pull details">
        {planPullView ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <div className="border rounded p-3">Run ID: <strong>{planPullView.run_id || '-'}</strong></div>
            <div className="border rounded p-3">Response code: <strong>{planPullView.response_code || '-'}</strong></div>
            <div className="border rounded p-3">Plan count: <strong>{String(planPullView.plan_count ?? 0)}</strong></div>
            <div className="border rounded p-3">Processed billers: <strong>{Array.isArray(planPullView.processed_biller_ids) ? planPullView.processed_biller_ids.join(', ') || '-' : '-'}</strong></div>
            <div className="border rounded p-3">Skipped billers: <strong>{Array.isArray(planPullView.skipped_biller_ids) ? planPullView.skipped_biller_ids.join(', ') || '-' : '-'}</strong></div>
            <div className="border rounded p-3">Created at: <strong>{planPullView.created_at || '-'}</strong></div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">No plan pull run found yet for this biller.</p>
        )}
      </Section>

      <Section title="Supported from biller response">
        <p className="text-sm text-gray-600 mb-3">
          This is taken directly from synced biller info for this biller ID, so admins can map only what the biller actually supports.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm mb-3">
          <div className="border rounded p-3">
            <div className="text-gray-500 text-xs">Accepted payment channels</div>
            <div className="font-semibold text-lg">{supportedChannels.length}</div>
            <div className="text-xs text-gray-700 mt-2">{supportedChannels.join(', ') || '-'}</div>
          </div>
          <div className="border rounded p-3">
            <div className="text-gray-500 text-xs">Accepted payment modes</div>
            <div className="font-semibold text-lg">{supportedModes.length}</div>
            <div className="text-xs text-gray-700 mt-2">{supportedModes.join(', ') || '-'}</div>
          </div>
          <div className="border rounded p-3">
            <div className="text-gray-500 text-xs">Plan support</div>
            <div className="font-semibold text-lg">{String(biller.plan_mdm_requirement || 'NOT_SUPPORTED')}</div>
            <div className="text-xs text-gray-700 mt-2">
              Plans synced: {supportedPlans.length}
              {catalogSummary?.pay_ui_projection?.plans_truncated ? ' (truncated)' : ''}
            </div>
          </div>
        </div>
        {supportedPlans.length ? (
          <SimpleTable
            columns={[
              { key: 'plan_id', label: 'Plan ID' },
              { key: 'category_type', label: 'Category' },
              { key: 'category_sub_type', label: 'Sub category' },
              { key: 'amount_in_rupees', label: 'Amount' },
              { key: 'status', label: 'Status' },
              { key: 'effective_from', label: 'Effective from' },
              { key: 'effective_to', label: 'Effective to' },
              { key: 'plan_desc', label: 'Description' },
            ]}
            rows={supportedPlans.slice(0, 25).map((p) => ({
              plan_id: p.plan_id,
              category_type: p.category_type || p.category_sub_type || '-',
              category_sub_type: p.category_sub_type || '-',
              amount_in_rupees: p.amount_in_rupees ?? '-',
              status: p.status || '-',
              effective_from: p.effective_from || '-',
              effective_to: p.effective_to || '-',
              plan_desc: p.plan_desc || '-',
            }))}
          />
        ) : (
          <p className="text-xs text-gray-500">
            No plan entries available for this biller.
            {latestPlanPull ? ` Last pull: code=${latestPlanPull.response_code || '-'}, rows=${latestPlanPull.plan_count ?? 0}.` : ''}
          </p>
        )}
      </Section>

      <Section title="Catalog summary (projections & counts)">
        <p className="text-xs text-gray-500 mb-3">
          Aggregate view of persisted catalog rows and the same pay-UI projections used for customer flows (input schema, modes/channels, additional info, plans lite).
        </p>
        {catalogLoading ? (
          <p className="text-sm text-gray-500">Loading catalog summary…</p>
        ) : catalogSummary ? (
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {Object.entries(catalogSummary.counts || {}).map(([k, v]) => (
                <div key={k} className="border rounded p-2">
                  <div className="text-[10px] uppercase text-gray-500">{k.replace(/_/g, ' ')}</div>
                  <div className="font-semibold">{String(v)}</div>
                </div>
              ))}
            </div>
            <div className="flex flex-wrap gap-3 text-xs">
              <span>
                Raw MDM payload fingerprint (SHA-256):{' '}
                <code className="bg-slate-100 px-1 rounded">{catalogSummary.raw_payload_fingerprint_sha256 || '—'}</code>
              </span>
              <span>Size: <strong>{catalogSummary.raw_payload_size_bytes ?? 0}</strong> bytes</span>
              <span>
                Suggest plan pull:{' '}
                <strong>{catalogSummary.suggest_plan_pull ? 'Yes' : 'No'}</strong>
              </span>
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">Catalog summary unavailable.</p>
        )}
      </Section>

      <Section title="Admin payment mapping (channel → mode)">
        <p className="text-sm text-gray-600 mb-3">
          Choose which payment channels are allowed for this biller. Users will only see methods that match these allowed channels.
        </p>
        {mappingLoading ? (
          <p className="text-sm text-gray-500">Loading mapping…</p>
        ) : mappingData ? (
          <div className="space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {(mappingData.mdm_channels || []).map((ch) => {
                const checked = allowedChannels.includes(String(ch).toUpperCase());
                return (
                  <button
                    key={ch}
                    type="button"
                    onClick={() => toggleAllowedChannel(ch)}
                    className={`px-3 py-2 text-sm rounded border text-left ${checked ? 'bg-blue-600 text-white border-blue-600' : 'bg-white text-gray-700 border-gray-300'}`}
                  >
                    <span className="font-semibold">{ch}</span>{' '}
                    <span className={`${checked ? 'text-blue-100' : 'text-gray-500'}`}>
                      {checked ? 'Allowed' : 'Blocked'}
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="text-xs text-gray-500">
              Allowed channels: {allowedChannels.length ? allowedChannels.join(', ') : 'None selected'}
            </div>
            <button
              type="button"
              onClick={savePaymentMapping}
              disabled={mappingSaving}
              className="px-3 py-2 border rounded text-sm bg-indigo-700 text-white disabled:opacity-50"
            >
              {mappingSaving ? 'Saving mapping...' : 'Save payment mapping'}
            </button>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {(mappingData.mdm_channels || []).map((ch) => {
                const allowedModes = (mappingData.matrix || [])
                  .filter((r) => r.payment_channel === ch && r.bbps_rule_valid)
                  .map((r) => r.payment_mode);
                return (
                  <div key={`summary-${ch}`} className="border rounded p-3 text-sm">
                    <div className="font-semibold text-gray-800">{ch}</div>
                    <div className="text-xs text-gray-500 mt-1">
                      Supported modes: {allowedModes.length}
                    </div>
                    <div className="mt-2 text-xs text-gray-700">
                      {allowedModes.length ? allowedModes.join(', ') : 'No valid modes by BBPS rules'}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <p className="text-sm text-gray-500">No mapping data available.</p>
        )}
      </Section>

      <Section title="Schema at a glance">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
          <div className="border rounded p-3">
            <div className="text-gray-500 text-xs">Input fields</div>
            <div className="font-semibold text-lg">{catalogSummary?.counts?.input_params ?? expectedInputRows.length}</div>
          </div>
          <div className="border rounded p-3">
            <div className="text-gray-500 text-xs">Payment modes</div>
            <div className="font-semibold text-lg">{catalogSummary?.counts?.payment_modes ?? 0}</div>
          </div>
          <div className="border rounded p-3">
            <div className="text-gray-500 text-xs">Payment channels</div>
            <div className="font-semibold text-lg">{catalogSummary?.counts?.payment_channels ?? 0}</div>
          </div>
        </div>
      </Section>

      {changedCount > 0 ? (
        <Section title="Changed Fields (Old vs New)">
          <SimpleTable
            columns={[
              { key: 'path', label: 'Field Path' },
              { key: 'old', label: 'Old Value' },
              { key: 'new', label: 'New Value' },
            ]}
            rows={Object.entries(changedFieldMap).map(([path, values]) => ({ path, old: values.old, new: values.new }))}
          />
        </Section>
      ) : null}

      <Section title="Raw payload details">
        {showFullResponse ? (
          <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 overflow-auto max-h-[420px]">
            {JSON.stringify(rawPayload, null, 2)}
          </pre>
        ) : (
          <p className="text-sm text-gray-600">
            Full response is hidden. Click <strong>See full response</strong> to inspect all biller info fields.
          </p>
        )}
      </Section>
    </div>
  );
};

export default BbpsBillerDetails;
