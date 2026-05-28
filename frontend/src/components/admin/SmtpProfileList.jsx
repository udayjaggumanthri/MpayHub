import React, { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import { providerLabel } from './smtpPresets';
import {
  FaPlus,
  FaPenToSquare,
  FaTrash,
  FaCircleCheck,
  FaEnvelope,
  FaServer,
} from 'react-icons/fa6';

const SmtpProfileList = () => {
  const navigate = useNavigate();
  const [configs, setConfigs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState(null);
  const [msg, setMsg] = useState({ type: '', text: '' });

  const setBanner = (type, text) => setMsg({ type, text });

  const load = useCallback(async () => {
    setLoading(true);
    const res = await adminAPI.listSmtpConfigs();
    if (res.success) {
      setConfigs(res.data?.configs || []);
    } else {
      setBanner('error', res.message || 'Failed to load SMTP profiles');
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
    if (!cfg.has_password) {
      setBanner('error', 'Set an SMTP password on this profile before activating.');
      return;
    }
    runAction(cfg.id, adminAPI.activateSmtpConfig, 'Profile activated');
  };

  const handleDeactivate = (cfg) => {
    if (
      !window.confirm(
        `Deactivate "${cfg.name}"? Password-reset OTP emails will not send until another profile is active.`
      )
    ) {
      return;
    }
    runAction(cfg.id, adminAPI.deactivateSmtpConfig, 'Profile deactivated');
  };

  const handleDelete = async (cfg) => {
    const extra = cfg.is_active
      ? ' This is the active profile; another profile will be activated automatically if available.'
      : '';
    if (!window.confirm(`Delete SMTP profile "${cfg.name}"?${extra} This cannot be undone.`)) {
      return;
    }
    setActionId(cfg.id);
    const res = await adminAPI.deleteSmtpConfig(cfg.id);
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
          <h1 className="text-2xl font-semibold text-gray-900">SMTP Settings</h1>
          <p className="text-sm text-gray-500 mt-1">
            Manage multiple SMTP profiles. Only one profile can be active for password-reset OTP email.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/admin/email-notifications"
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg border border-gray-300 text-sm font-medium hover:bg-gray-50"
          >
            Email notifications
          </Link>
          <Link
            to="/admin/smtp-settings/new"
            className="inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 shadow-sm"
          >
            <FaPlus className="w-4 h-4" />
            New SMTP
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

      <div className="bg-blue-50 border border-blue-200 rounded-xl p-4 text-sm text-blue-950">
        <p className="font-semibold mb-1">Multiple SMTP servers</p>
        <p>
          Save Gmail, Zoho, Outlook, or custom SMTP profiles. Only <strong>one</strong> can be{' '}
          <strong>active</strong> at a time — that profile sends password-reset OTP emails.
        </p>
      </div>

      {loading ? (
        <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-500">
          Loading SMTP profiles...
        </div>
      ) : configs.length === 0 ? (
        <div className="bg-white rounded-xl border border-dashed border-gray-300 p-12 text-center">
          <FaEnvelope className="w-10 h-10 text-gray-300 mx-auto mb-3" />
          <p className="text-gray-600 font-medium">No SMTP profiles yet</p>
          <p className="text-sm text-gray-500 mt-1 mb-4">
            Add your first profile to send password-reset OTP emails from the admin panel.
          </p>
          <Link
            to="/admin/smtp-settings/new"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700"
          >
            <FaPlus /> New SMTP
          </Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="min-w-full text-sm">
            <thead className="bg-gray-50 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide">
              <tr>
                <th className="px-4 py-3">Profile</th>
                <th className="px-4 py-3">Server</th>
                <th className="px-4 py-3">From</th>
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
                      <div className="text-xs text-gray-500">{providerLabel(cfg)}</div>
                    </td>
                    <td className="px-4 py-4 text-gray-700">
                      <div className="flex items-center gap-1.5">
                        <FaServer className="w-3.5 h-3.5 text-gray-400" />
                        {cfg.host || '—'}:{cfg.port}
                      </div>
                      <div className="text-xs text-gray-500">
                        {cfg.use_ssl ? 'SSL' : cfg.use_tls ? 'TLS' : 'Plain'}
                        {!cfg.has_password && ' · No password'}
                      </div>
                    </td>
                    <td className="px-4 py-4 text-gray-700">{cfg.from_email || '—'}</td>
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
                          onClick={() => navigate(`/admin/smtp-settings/${cfg.id}/edit`)}
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

export default SmtpProfileList;
