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
            {columns.map((c) => <td key={c.key} className="p-2">{String(r[c.key] ?? '-')}</td>)}
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
  const [error, setError] = useState('');
  const [biller, setBiller] = useState(null);
  const [info, setInfo] = useState('');
  const [changedFieldMap, setChangedFieldMap] = useState({});
  const [changedCount, setChangedCount] = useState(0);

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
    return data;
  }, [billerPk]);

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
    setInfo(`Biller synced successfully. ${totalChanged} field(s) changed from previous snapshot.`);
    setSyncing(false);
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

  if (loading) return <div className="max-w-7xl mx-auto text-sm text-gray-500">Loading biller details...</div>;
  if (error) return <div className="max-w-7xl mx-auto text-sm text-red-700 bg-red-50 border border-red-200 rounded p-3">{error}</div>;
  if (!biller) return <div className="max-w-7xl mx-auto text-sm text-gray-500">Biller not found.</div>;
  const rawPayload = biller.raw_payload || {};
  const flattened = flattenObject(rawPayload);
  const expectedInputRows = flattened.filter(
    (row) => row.path.includes('billerInputParams') || row.path.toLowerCase().includes('paraminfo'),
  );

  return (
    <div className="max-w-7xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">{biller.biller_name || 'Biller Details'}</h1>
          <p className="text-sm text-gray-600">Biller ID: <span className="font-mono">{biller.biller_id}</span></p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={syncThisBiller}
            disabled={syncing}
            className="px-3 py-2 border rounded text-sm bg-blue-600 text-white disabled:opacity-50"
          >
            {syncing ? 'Syncing...' : 'Sync This Biller'}
          </button>
          <button type="button" onClick={() => navigate(-1)} className="px-3 py-2 border rounded text-sm">Back</button>
          <Link to="/admin/bbps-governance" className="px-3 py-2 border rounded text-sm bg-slate-50">Governance</Link>
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
          <div className="border rounded p-3">Source: <strong>{biller.source_type || '-'}</strong></div>
          <div className="border rounded p-3">Last Sync Status: <strong>{biller.last_sync_status || '-'}</strong></div>
          <div className="border rounded p-3">Version: <strong>{biller.version || 1}</strong></div>
        </div>
      </Section>

      <Section title="Payment Acceptance Matrix (Mode ↔ Channel)">
        <p className="text-xs text-gray-500 mb-3">
          Computed from synced BillAvenue biller data and BBPS channel eligibility rules for this biller.
        </p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs mb-3">
          <div className="border rounded p-3">
            <p className="text-gray-500">Payment Modes (from biller sync)</p>
            <p className="font-medium text-gray-900">
              {(biller.payment_acceptance_matrix?.payment_modes_supported || []).join(', ') || 'None'}
            </p>
          </div>
          <div className="border rounded p-3">
            <p className="text-gray-500">Payment Channels (from biller sync)</p>
            <p className="font-medium text-gray-900">
              {(biller.payment_acceptance_matrix?.payment_channels_supported || []).join(', ') || 'None'}
            </p>
          </div>
        </div>
        <SimpleTable
          columns={[
            { key: 'payment_channel', label: 'Payment Channel' },
            { key: 'accepted_payment_modes', label: 'Accepted Payment Modes' },
            { key: 'accepted_payment_modes_count', label: 'Count' },
          ]}
          rows={(biller.payment_acceptance_matrix?.channel_to_modes || []).map((row) => ({
            payment_channel: row.payment_channel,
            accepted_payment_modes: (row.accepted_payment_modes || []).join(', ') || '-',
            accepted_payment_modes_count: row.accepted_payment_modes_count ?? 0,
          }))}
        />
        <div className="mt-4">
          <SimpleTable
            columns={[
              { key: 'payment_mode', label: 'Payment Mode' },
              { key: 'eligible_payment_channels', label: 'Eligible Payment Channels' },
              { key: 'eligible_payment_channels_count', label: 'Count' },
            ]}
            rows={(biller.payment_acceptance_matrix?.mode_to_channels || []).map((row) => ({
              payment_mode: row.payment_mode,
              eligible_payment_channels: (row.eligible_payment_channels || []).join(', ') || '-',
              eligible_payment_channels_count: row.eligible_payment_channels_count ?? 0,
            }))}
          />
        </div>
      </Section>

      <Section title="Expected Input Keys (From Live API Response)">
        <p className="text-xs text-gray-500 mb-3">
          This is not static. It is extracted directly from BillAvenue billerInfo response paths for this biller.
        </p>
        <SimpleTable
          columns={[
            { key: 'path', label: 'Field Path' },
            { key: 'value', label: 'Value' },
          ]}
          rows={expectedInputRows}
        />
      </Section>

      <Section title="All Synced Fields (Dynamic)">
        <p className="text-xs text-gray-500 mb-3">
          This section shows every field stored from BillAvenue billerInfo response for this biller, including biller-specific dynamic fields.
        </p>
        {changedCount > 0 ? (
          <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-3">
            Highlighted rows are changed fields from last sync. Total changed: <strong>{changedCount}</strong>
          </div>
        ) : null}
        <SimpleTable
          columns={[
            { key: 'path', label: 'Field Path' },
            { key: 'value', label: 'Value' },
          ]}
          rows={flattened}
          rowClassName={(row) => (changedFieldMap[row.path] ? 'bg-yellow-50' : '')}
        />
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

      <Section title="Raw BillAvenue Payload">
        <pre className="text-xs bg-slate-50 border border-slate-200 rounded p-3 overflow-auto max-h-[420px]">
          {JSON.stringify(rawPayload, null, 2)}
        </pre>
      </Section>
    </div>
  );
};

export default BbpsBillerDetails;
