import React, { useState } from 'react';
import aepsAPI from '../services/aepsApi';
import { detectMantraRd } from '../services/mantraRd';

const AepsDevice = ({ aepsStatus: status, refreshStatus }) => {
  const [info, setInfo] = useState(null);
  const [serial, setSerial] = useState(status?.merchant?.device_imei || '');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);

  const detect = async () => {
    setBusy(true);
    const r = await detectMantraRd();
    setInfo(r);
    if (r.serial) setSerial(r.serial);
    setBusy(false);
  };

  const save = async () => {
    setBusy(true);
    const res = await aepsAPI.registerDevice(serial);
    setMsg(res.success ? 'Device registered for AEPS.' : res.message);
    await refreshStatus();
    setBusy(false);
  };

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-bold text-slate-900">Mantra device</h2>
        <p className="text-sm text-slate-500">
          Start Mantra RD Service, connect the fingerprint scanner, then register the serial used as
          deviceIMEI for Fingpay.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <button
          type="button"
          onClick={detect}
          disabled={busy}
          className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          Detect RD Service
        </button>
        {info ? (
          <p className={`mt-4 text-sm ${info.ready ? 'text-emerald-700' : 'text-amber-800'}`}>{info.message}</p>
        ) : null}
        <label className="mt-6 block text-xs font-semibold uppercase tracking-wide text-slate-500">
          Scanner serial / deviceIMEI
          <input
            className="mt-1 w-full max-w-md rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={serial}
            onChange={(e) => setSerial(e.target.value)}
          />
        </label>
        <button
          type="button"
          onClick={save}
          disabled={busy || !serial}
          className="mt-4 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Save device
        </button>
        {msg ? <p className="mt-3 text-sm text-slate-700">{msg}</p> : null}
      </section>
    </div>
  );
};

export default AepsDevice;
