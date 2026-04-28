import React, { useEffect, useMemo, useState } from 'react';
import { bbpsAPI, billAvenueAdminAPI } from '../../services/api';

const BbpsProviderGovernance = () => {
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [info, setInfo] = useState('');
  const [readiness, setReadiness] = useState(null);
  const [syncDiagnostics, setSyncDiagnostics] = useState(null);
  const [opsSummary, setOpsSummary] = useState(null);
  const [categories, setCategories] = useState([]);
  const [providers, setProviders] = useState([]);
  const [maps, setMaps] = useState([]);
  const [rules, setRules] = useState([]);
  const [audits, setAudits] = useState([]);
  const [billerMaster, setBillerMaster] = useState([]);

  const [categoryForm, setCategoryForm] = useState({ code: '', name: '', description: '' });
  const [providerForm, setProviderForm] = useState({
    code: '',
    name: '',
    provider_type: 'operator',
    category: '',
    priority: 0,
  });
  const [mapForm, setMapForm] = useState({ provider: '', biller_master: '', priority: 0 });
  const [ruleForm, setRuleForm] = useState({
    category: '',
    rule_code: '',
    commission_type: 'flat',
    value: '0',
    min_commission: '0',
    max_commission: '0',
    notes: '',
  });

  const mapCount = useMemo(() => maps.length, [maps]);
  const unmappedBillers = useMemo(() => {
    const mappedIds = new Set(maps.map((m) => m.biller_master));
    return billerMaster.filter((b) => !mappedIds.has(b.id));
  }, [maps, billerMaster]);

  const loadAll = async () => {
    setLoading(true);
    setError('');
    try {
      const [
        catRes,
        provRes,
        mapRes,
        ruleRes,
        auditRes,
        billerRes,
        readinessRes,
        opsRes,
      ] = await Promise.all([
        billAvenueAdminAPI.listServiceCategories(),
        billAvenueAdminAPI.listServiceProviders(),
        billAvenueAdminAPI.listProviderBillerMaps(),
        billAvenueAdminAPI.listCommissionRules(),
        billAvenueAdminAPI.listCommissionAudit(),
        billAvenueAdminAPI.listBillerMaster(),
        billAvenueAdminAPI.getSetupReadiness(),
        billAvenueAdminAPI.getGovernanceOpsSummary(),
      ]);

      setCategories(catRes.data?.categories || []);
      setProviders(provRes.data?.providers || []);
      setMaps(mapRes.data?.maps || []);
      setRules(ruleRes.data?.rules || []);
      setAudits(auditRes.data?.audits || []);
      setBillerMaster(billerRes.data?.billers || []);
      setReadiness(readinessRes.data || null);
      setOpsSummary(opsRes.data || null);
    } catch (e) {
      setError('Failed to load governance data.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, []);

  const saveCategory = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    const out = await billAvenueAdminAPI.saveServiceCategory(categoryForm);
    if (!out.success) {
      setError(out.message || 'Failed to save category');
      return;
    }
    setCategoryForm({ code: '', name: '', description: '' });
    setInfo('Category saved.');
    loadAll();
  };

  const saveProvider = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    const out = await billAvenueAdminAPI.saveServiceProvider(providerForm);
    if (!out.success) {
      setError(out.message || 'Failed to save provider');
      return;
    }
    setProviderForm({ code: '', name: '', provider_type: 'operator', category: '', priority: 0 });
    setInfo('Provider saved.');
    loadAll();
  };

  const saveMap = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    const out = await billAvenueAdminAPI.saveProviderBillerMap(mapForm);
    if (!out.success) {
      setError(out.message || 'Failed to save map');
      return;
    }
    setMapForm({ provider: '', biller_master: '', priority: 0 });
    setInfo('Provider-biller mapping saved.');
    loadAll();
  };

  const saveRule = async (e) => {
    e.preventDefault();
    setError('');
    setInfo('');
    const out = await billAvenueAdminAPI.saveCommissionRule(ruleForm);
    if (!out.success) {
      setError(out.message || 'Failed to save rule');
      return;
    }
    setRuleForm({
      category: '',
      rule_code: '',
      commission_type: 'flat',
      value: '0',
      min_commission: '0',
      max_commission: '0',
      notes: '',
    });
    setInfo('Commission rule saved.');
    loadAll();
  };

  const runSync = async () => {
    setSyncing(true);
    setError('');
    setInfo('');
    try {
      const res = await bbpsAPI.syncBillers([]);
      if (!res.success) {
        setError(res.message || 'Sync failed');
        return;
      }
      setSyncDiagnostics(res.data || null);
      setInfo('Biller sync completed.');
      await loadAll();
    } catch (e) {
      setError('Failed to sync billers.');
    } finally {
      setSyncing(false);
    }
  };

  const refreshCache = async () => {
    setError('');
    const out = await billAvenueAdminAPI.refreshProviderCache({});
    if (!out.success) {
      setError(out.message || 'Cache refresh failed');
      return;
    }
    setInfo('Provider cache refreshed.');
    loadAll();
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <h1 className="text-xl font-semibold text-gray-900">BBPS Provider Governance</h1>
        <p className="text-sm text-gray-600 mt-1">
          Manage service categories, provider master, biller mapping, and category commission rules.
        </p>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 rounded-lg p-3 text-sm">{error}</div>
      )}
      {info && (
        <div className="bg-green-50 border border-green-200 text-green-700 rounded-lg p-3 text-sm">{info}</div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-3">
        <h2 className="font-semibold">Step A: Integration Readiness</h2>
        {!readiness && <p className="text-sm text-gray-500">Loading readiness...</p>}
        {readiness && (
          <div className="space-y-2">
            <p className="text-sm">Readiness score: <strong>{readiness.score_percent}%</strong></p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {(readiness.checks || []).map((c) => (
                <div key={c.key} className={`text-xs rounded p-2 border ${c.ok ? 'bg-green-50 border-green-200 text-green-800' : 'bg-amber-50 border-amber-200 text-amber-800'}`}>
                  <strong>{c.key}</strong> - {c.message}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-3">
        <h2 className="font-semibold">Step B: Sync Billers</h2>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={runSync}
            disabled={syncing}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded disabled:opacity-50"
          >
            {syncing ? 'Running sync...' : 'Run Biller Sync'}
          </button>
          <button
            type="button"
            onClick={refreshCache}
            className="px-4 py-2 bg-slate-100 text-slate-800 text-sm rounded border border-slate-300"
          >
            Refresh Provider Cache
          </button>
        </div>
        {syncDiagnostics && (
          <pre className="text-xs bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-auto max-h-56">
            {JSON.stringify(syncDiagnostics, null, 2)}
          </pre>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form onSubmit={saveCategory} className="bg-white rounded-xl border border-gray-200 p-6 space-y-3">
          <h2 className="font-semibold">Service Category</h2>
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="code (e.g. credit-card)" value={categoryForm.code} onChange={(e) => setCategoryForm((s) => ({ ...s, code: e.target.value }))} required />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="name" value={categoryForm.name} onChange={(e) => setCategoryForm((s) => ({ ...s, name: e.target.value }))} required />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="description" value={categoryForm.description} onChange={(e) => setCategoryForm((s) => ({ ...s, description: e.target.value }))} />
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white text-sm rounded">Save category</button>
        </form>

        <form onSubmit={saveProvider} className="bg-white rounded-xl border border-gray-200 p-6 space-y-3">
          <h2 className="font-semibold">Service Provider</h2>
          <select className="w-full border rounded px-3 py-2 text-sm" value={providerForm.category} onChange={(e) => setProviderForm((s) => ({ ...s, category: e.target.value }))} required>
            <option value="">Select category</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="provider code" value={providerForm.code} onChange={(e) => setProviderForm((s) => ({ ...s, code: e.target.value }))} required />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="provider name" value={providerForm.name} onChange={(e) => setProviderForm((s) => ({ ...s, name: e.target.value }))} required />
          <select className="w-full border rounded px-3 py-2 text-sm" value={providerForm.provider_type} onChange={(e) => setProviderForm((s) => ({ ...s, provider_type: e.target.value }))}>
            <option value="operator">Operator</option>
            <option value="bank">Bank</option>
            <option value="utility">Utility</option>
            <option value="other">Other</option>
          </select>
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white text-sm rounded">Save provider</button>
        </form>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <form onSubmit={saveMap} className="bg-white rounded-xl border border-gray-200 p-6 space-y-3">
          <h2 className="font-semibold">Step D: Provider-Biller Mapping</h2>
          <select className="w-full border rounded px-3 py-2 text-sm" value={mapForm.provider} onChange={(e) => setMapForm((s) => ({ ...s, provider: e.target.value }))} required>
            <option value="">Select provider</option>
            {providers.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <select className="w-full border rounded px-3 py-2 text-sm" value={mapForm.biller_master} onChange={(e) => setMapForm((s) => ({ ...s, biller_master: e.target.value }))} required>
            <option value="">Select biller</option>
            {billerMaster.map((b) => <option key={b.id} value={b.id}>{b.biller_name} ({b.biller_id})</option>)}
          </select>
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white text-sm rounded">Save mapping</button>
          <p className="text-xs text-gray-500">Unmapped billers currently: {unmappedBillers.length}</p>
        </form>

        <form onSubmit={saveRule} className="bg-white rounded-xl border border-gray-200 p-6 space-y-3">
          <h2 className="font-semibold">Step E: Category Commission Rules</h2>
          <select className="w-full border rounded px-3 py-2 text-sm" value={ruleForm.category} onChange={(e) => setRuleForm((s) => ({ ...s, category: e.target.value }))} required>
            <option value="">Select category</option>
            {categories.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="rule code" value={ruleForm.rule_code} onChange={(e) => setRuleForm((s) => ({ ...s, rule_code: e.target.value }))} required />
          <select className="w-full border rounded px-3 py-2 text-sm" value={ruleForm.commission_type} onChange={(e) => setRuleForm((s) => ({ ...s, commission_type: e.target.value }))}>
            <option value="flat">Flat</option>
            <option value="percentage">Percentage</option>
          </select>
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="value" value={ruleForm.value} onChange={(e) => setRuleForm((s) => ({ ...s, value: e.target.value }))} required />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="min commission" value={ruleForm.min_commission} onChange={(e) => setRuleForm((s) => ({ ...s, min_commission: e.target.value }))} />
          <input className="w-full border rounded px-3 py-2 text-sm" placeholder="max commission" value={ruleForm.max_commission} onChange={(e) => setRuleForm((s) => ({ ...s, max_commission: e.target.value }))} />
          <button type="submit" className="px-4 py-2 bg-blue-600 text-white text-sm rounded">Save rule</button>
        </form>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold mb-3">Current Commission Rules</h2>
        <div className="overflow-auto max-h-72 border rounded">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left p-2">Rule</th>
                <th className="text-left p-2">Category</th>
                <th className="text-left p-2">Type</th>
                <th className="text-left p-2">Value</th>
                <th className="text-left p-2">Active</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className="border-t">
                  <td className="p-2">{r.rule_code}</td>
                  <td className="p-2">{r.category_name || r.category_code}</td>
                  <td className="p-2">{r.commission_type}</td>
                  <td className="p-2">{r.value}</td>
                  <td className="p-2">{r.is_active ? 'Yes' : 'No'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold mb-3">Commission Audit (latest)</h2>
        <pre className="text-xs bg-slate-50 border border-slate-200 rounded-lg p-3 overflow-auto max-h-72">
          {JSON.stringify(audits.slice(0, 25), null, 2)}
        </pre>
      </div>

      {opsSummary && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold mb-3">Step F: Go-live Risk Summary</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-sm">
            <div className="border rounded p-3">Stale Billers: <strong>{opsSummary.stale_billers}</strong></div>
            <div className="border rounded p-3">Unmapped Billers: <strong>{opsSummary.unmapped_billers}</strong></div>
            <div className="border rounded p-3">Inactive Categories: <strong>{opsSummary.inactive_categories}</strong></div>
            <div className="border rounded p-3">Conflicting Rules: <strong>{opsSummary.conflicting_rule_windows}</strong></div>
          </div>
        </div>
      )}

      <div className="text-xs text-gray-400">
        {loading ? 'Loading governance data...' : `Categories: ${categories.length}, Providers: ${providers.length}, Maps: ${mapCount}, Billers: ${billerMaster.length}, Unmapped: ${unmappedBillers.length}`}
      </div>
    </div>
  );
};

export default BbpsProviderGovernance;
