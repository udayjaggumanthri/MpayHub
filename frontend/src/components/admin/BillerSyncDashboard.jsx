import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { bbpsAPI, billAvenueAdminAPI } from '../../services/api';

const BillerSyncDashboard = () => {
  const [billerIds, setBillerIds] = useState('');
  const [result, setResult] = useState(null);
  const [health, setHealth] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [loading, setLoading] = useState(false);

  const runSync = async () => {
    setLoading(true);
    setResult(null);
    const ids = billerIds.split(',').map((x) => x.trim()).filter(Boolean);
    const res = await bbpsAPI.syncBillers(ids);
    setResult(res);
    setLoading(false);
  };

  const runHealthCheck = async () => {
    setLoading(true);
    const res = await billAvenueAdminAPI.getIntegrationHealth();
    setHealth(res?.data || null);
    setLoading(false);
  };

  const runReadiness = async () => {
    setLoading(true);
    const res = await billAvenueAdminAPI.getUatReadiness();
    setReadiness(res?.data || null);
    setLoading(false);
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-950">
        <p className="font-semibold mb-1">Prerequisites</p>
        <p>
          Complete{' '}
          <Link to="/admin/billavenue-settings" className="text-blue-700 font-medium underline">
            BillAvenue Settings
          </Link>
          : base URL, access code, institute ID, <strong>working key + IV</strong>, enable + active config, and add an{' '}
          <strong>agent profile</strong> with the correct Agent ID. Then run sync here to pull the biller master (catalogue) from
          BillAvenue into your system.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-gray-900 mb-1">Biller sync dashboard</h1>
        <p className="text-sm text-gray-600 mb-4">
          Calls BillAvenue Biller Info (MDM) and updates local biller cache. Leave the list empty for a full sync if your UAT
          account allows it; otherwise enter specific biller IDs (comma‑separated).
        </p>
        <label className="block text-xs font-medium text-gray-600 mb-1">Optional: biller IDs</label>
        <textarea
          className="w-full border border-gray-300 rounded-lg p-3 h-24 text-sm"
          placeholder="e.g. BILLERID1, BILLERID2 (or leave empty)"
          value={billerIds}
          onChange={(e) => setBillerIds(e.target.value)}
        />
        <button
          type="button"
          disabled={loading}
          className="mt-3 px-5 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
          onClick={runSync}
        >
          {loading ? 'Running…' : 'Run sync'}
        </button>
        <button
          type="button"
          disabled={loading}
          className="mt-3 ml-2 px-5 py-2.5 bg-slate-100 text-slate-900 text-sm font-medium rounded-lg border border-slate-300 hover:bg-slate-200 disabled:opacity-50"
          onClick={runHealthCheck}
        >
          Check prerequisites
        </button>
        <button
          type="button"
          disabled={loading}
          className="mt-3 ml-2 px-5 py-2.5 bg-emerald-50 text-emerald-900 text-sm font-medium rounded-lg border border-emerald-300 hover:bg-emerald-100 disabled:opacity-50"
          onClick={runReadiness}
        >
          UAT readiness
        </button>
        {health && (
          <div className="mt-4 text-sm space-y-2">
            <p className={`font-medium ${health.go_live_blocked ? 'text-amber-800' : 'text-green-700'}`}>
              {health.go_live_blocked ? 'Go-live blocked' : 'Prerequisites look good'}
            </p>
            {health.entitlement_probe_ok === false && (
              <p className="text-red-800 bg-red-50 border border-red-200 rounded p-2">
                Entitlement probe failed: {health.entitlement_probe_message || 'BillAvenue denied access to MDM endpoint.'}
              </p>
            )}
            {Array.isArray(health.blockers) && health.blockers.length > 0 && (
              <p className="text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
                Blockers: {health.blockers.join(', ')}. Complete BillAvenue Settings and Agent Profile first.
              </p>
            )}
            {!!health.entitlement_issue && (
              <p className="text-red-800 bg-red-50 border border-red-200 rounded p-2">
                Entitlement issue: {health.entitlement_issue}
              </p>
            )}
          </div>
        )}
        {readiness && (
          <div className="mt-4 text-sm space-y-2">
            <p className={`font-medium ${readiness.go_live_blocked ? 'text-amber-800' : 'text-green-700'}`}>
              {readiness.go_live_blocked ? 'UAT checklist has blockers' : 'UAT checklist looks good'}
            </p>
            {Array.isArray(readiness.blockers) && readiness.blockers.length > 0 && (
              <p className="text-amber-800 bg-amber-50 border border-amber-200 rounded p-2">
                Checklist blockers: {readiness.blockers.join(', ')}
              </p>
            )}
            {!!readiness.latest_probe_message && (
              <p className="text-red-800 bg-red-50 border border-red-200 rounded p-2">
                Latest probe: {readiness.latest_probe_message}
              </p>
            )}
          </div>
        )}
        {result && (
          <div className="mt-4">
            <p className="text-sm font-medium text-gray-800 mb-2">Response</p>
            <pre className="text-xs bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-auto max-h-96">
              {JSON.stringify(result, null, 2)}
            </pre>
            {result.success && result.data && (
              <div className="mt-2 space-y-2 text-sm">
                {result.data.biller_count > 0 && (
                  <p className="text-green-700">
                    Billers are stored — your agents can use bill fetch / pay flows for synced biller IDs.
                  </p>
                )}
                {result.data.biller_count === 0 && !result.data.agent_id_used && (
                  <p className="text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-2">
                    No <strong>agent ID</strong> was sent. Add an enabled agent profile (with the correct BillAvenue
                    UAT/PROD agent ID) under{' '}
                    <Link to="/admin/billavenue-settings" className="text-blue-700 font-medium underline">
                      BillAvenue Settings
                    </Link>
                    , then run sync again. If the API response shows <code className="text-xs">mdm_root_keys</code>, the
                    MDM payload shape may not match; check BBPS API audit logs for the last biller_info call.
                  </p>
                )}
                {result.data.biller_count === 0 && result.data.agent_id_used && (
                  <p className="text-amber-800">
                    Counts are zero with agent <code className="text-xs bg-slate-100 px-1 rounded">{result.data.agent_id_used}</code> — the
                    upstream MDM may have returned an empty set for this UAT account, or the response used an unexpected
                    format (see <code className="text-xs">mdm_root_keys</code> in the JSON if present).
                  </p>
                )}
                {String(result.data.upstream_status_code || '') === '205' && (
                  <p className="text-red-800 bg-red-50 border border-red-200 rounded-lg p-2">
                    BillAvenue returned <strong>response code 205</strong> for MDM. This usually indicates institute/agent
                    entitlement mismatch for biller info. Confirm with BillAvenue support using the latest request ID from audit logs.
                  </p>
                )}
                {result.data.retry_without_agent_used && (
                  <p className="text-blue-800 bg-blue-50 border border-blue-200 rounded-lg p-2">
                    Sync retried without <code className="text-xs">agentId</code> after upstream rejection; verify whether your
                    institute requires agent ID for MDM on this environment.
                  </p>
                )}
              </div>
            )}
            {result.success === false && (
              <div className="text-sm text-red-700 mt-2 space-y-1">
                <p>Check server logs and BillAvenue credentials, then try again.</p>
                {result.data?.hint && <p className="text-red-900 bg-red-50 border border-red-200 rounded p-2">{result.data.hint}</p>}
                {(result.status === 422 || result.status === 502) && !result.data?.hint && (
                  <p className="text-red-900 bg-red-50 border border-red-200 rounded p-2">
                    Upstream BillAvenue returned an error (HTTP {result.status} from API). For MDM entitlement issues the
                    API now uses 422 with a JSON body; if you still see this generic message, check the Network tab for
                    the real response. Otherwise this is usually an institute/agent mismatch — contact BillAvenue with
                    your institute ID, agent ID, and server egress IP.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default BillerSyncDashboard;
