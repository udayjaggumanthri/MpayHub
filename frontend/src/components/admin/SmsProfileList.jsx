import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import { providerLabel } from './smsUtils';
import {
  FaPlus,
  FaPenToSquare,
  FaTrash,
  FaCircleCheck,
  FaCommentSms,
  FaListUl,
} from 'react-icons/fa6';

const SmsProfileList = () => {
  const navigate = useNavigate();
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState(null);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const setBanner = (type, text) => setMsg({ type, text });

  const load = useCallback(async () => {
    setLoading(true);
    const res = await adminAPI.listSmsConfigs();
    if (res.success) {
      setConfigs(res.data?.configs || []);
    } else {
      setBanner('error', res.message || 'Failed to load SMS profiles');
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const runAction = async (id, fn, successMsg) => {
    setActionId(id);
    setBanner('info', 'Please wait...');
    const res = await fn(id);
    if (res.success) {
      setBanner('success', res.message || successMsg);
      await load();
    } else {
      setBanner('error', res.message || 'Action failed');
    }
    setActionId(null);
  };

  const handleActivate = (cfg) => {
    if (!cfg.enabled) {
      setBanner('error', 'Enable the profile in Edit before activating.');
      return;
    }
    if (!cfg.has_auth_key && cfg.provider === 'msg91') {
      setBanner('error', 'Set an MSG91 auth key on this profile before activating.');
      return;
    }
    runAction(cfg.id, adminAPI.activateSmsConfig, 'Profile activated');
  };

  const handleDeactivate = (cfg) => {
    if (
      !window.confirm(
        `Deactivate "${cfg.name}"? OTP and payment SMS will not send until another profile is active.`
      )
    ) {
      return;
    }
    runAction(cfg.id, adminAPI.deactivateSmsConfig, 'Profile deactivated');
  };

  const handleDelete = async (cfg) => {
    const extra = cfg.is_active
      ? ' This is the active profile; another will be activated automatically if available.'
      : '';
    if (!window.confirm(`Delete SMS profile "${cfg.name}"?${extra} This cannot be undone.`)) {
      return;
    }
    setActionId(cfg.id);
    const res = await adminAPI.deleteSmsConfig(cfg.id);
    if (res.success) {
      setBanner('success', res.message || 'Profile deleted');
      await load();
    } else {
      setBanner('error', res.message || 'Failed to delete profile');
    }
    setActionId(null);
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">SMS Settings</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage MSG91 accounts. Only one profile is active for OTP, pay-in, payout, and BBPS SMS.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 justify-end">
          <Link
            to="/admin/sms-settings/templates"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <FaListUl className="w-4 h-4" />
            Event templates
          </Link>
          <Link
            to="/admin/sms-settings/new"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 shadow-sm"
          >
            <FaPlus className="w-4 h-4" />
            New SMS
          </Link>
        </div>
      </div>

      {msg.text && (
        <div
          className={`text-sm border rounded-lg px-4 py-3 ${
            msg.type === 'success'
              ? 'bg-green-50 border-green-200 text-green-800'
              : msg.type === 'error'
                ? 'bg-red-50 border-red-200 text-red-800'
                : 'bg-blue-50 border-blue-200 text-blue-800'
          }`}
        >
          {msg.text}
        </div>
      )}

      <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-sm text-amber-950">
        <p className="font-semibold mb-1">Multiple MSG91 profiles</p>
        <p>
          Store separate MSG91 credentials (e.g. production vs staging). Only <strong>one</strong> profile is{' '}
          <strong>active</strong> at a time. Map DLT template IDs under{' '}
          <Link to="/admin/sms-settings/templates" className="underline font-medium">
            Event templates
          </Link>
          .
        </p>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-500">
          Loading SMS profiles...
        </div>
      ) : configs.length === 0 ? (
        <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center">
          <FaCommentSms className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No SMS profiles yet</p>
          <p className="text-sm text-gray-500 mt-1 mb-4">
            Add your first MSG91 profile, then configure event templates.
          </p>
          <Link
            to="/admin/sms-settings/new"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
          >
            <FaPlus /> New SMS
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3">Profile</th>
                <th className="px-4 py-3">Provider</th>
                <th className="px-4 py-3">Sender ID</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {configs.map((cfg) => {
                const busy = actionId === cfg.id;
                return (
                  <tr key={cfg.id} className="hover:bg-gray-50/80">
                    <td className="px-4 py-4">
                      <div className="font-medium text-gray-900">{cfg.name}</div>
                      <div className="text-xs text-gray-500">
                        {cfg.api_base_url?.replace(/^https?:\/\//, '') || '—'}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-gray-700">{providerLabel(cfg)}</td>
                    <td className="px-4 py-4 text-gray-700">
                      {cfg.sender_id || '—'}
                      <div className="text-xs text-gray-500">
                        +{cfg.country_code || '91'}
                        {!cfg.has_auth_key && cfg.provider === 'msg91' ? ' · No auth key' : ''}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-1.5">
                        {cfg.is_active && (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-800">
                            <FaCircleCheck className="w-3 h-3" /> Active
                          </span>
                        )}
                        {cfg.enabled ? (
                          <span className="px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-700">
                            Enabled
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-800">
                            Disabled
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap justify-end gap-2">
                        {!cfg.is_active ? (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => handleActivate(cfg)}
                            className="px-2.5 py-1.5 rounded-md text-xs font-medium bg-green-600 text-white hover:bg-green-700 disabled:opacity-50"
                          >
                            Activate
                          </button>
                        ) : (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => handleDeactivate(cfg)}
                            className="px-2.5 py-1.5 rounded-md text-xs font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                          >
                            Deactivate
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => navigate(`/admin/sms-settings/${cfg.id}/edit`)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                        >
                          <FaPenToSquare className="w-3 h-3" /> Edit
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => handleDelete(cfg)}
                          className="inline-flex items-center gap-1 px-2.5 py-1.5 rounded-md text-xs font-medium border border-red-200 text-red-700 hover:bg-red-50 disabled:opacity-50"
                        >
                          <FaTrash className="w-3 h-3" /> Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default SmsProfileList;
