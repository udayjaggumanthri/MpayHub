import React, { useEffect, useState } from 'react';
import aepsAPI from '../services/aepsApi';
import { captureMantraFingerprint, detectMantraRd, isMobileBrowser } from '../services/mantraRd';

const AepsDevice = ({ aepsStatus: status, refreshStatus }) => {
  const [info, setInfo] = useState(null);
  const [serial, setSerial] = useState(status?.merchant?.device_imei || '');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [mobile, setMobile] = useState(false);

  useEffect(() => {
    setMobile(isMobileBrowser());
  }, []);

  const detect = async () => {
    setBusy(true);
    setMsg('');
    const r = await detectMantraRd();
    setInfo(r);
    if (r.serial) setSerial(r.serial);
    setBusy(false);
  };

  const testCapture = async () => {
    setBusy(true);
    setMsg('');
    const cap = await captureMantraFingerprint();
    if (cap.success) {
      setMsg('Fingerprint capture OK — Mantra RD is working with this browser.');
      setInfo((prev) => ({
        ...(prev || {}),
        ready: true,
        message: prev?.message || 'Mantra RD ready',
        baseUrl: cap.baseUrl || prev?.baseUrl,
      }));
    } else {
      setMsg(cap.message || 'Capture failed');
    }
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
          Start Mantra L1 RD Service, connect the scanner, then register the serial used as deviceIMEI
          for Fingpay. Trade stays blocked until the serial is saved.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Readiness checklist</p>
        <ul className="mt-3 space-y-2 text-sm">
          <Check ok={!!info?.ready} label="Mantra RD Service detected" />
          <Check ok={!!serial} label="Scanner serial available" />
          <Check ok={!!status?.merchant?.device_ready} label="Serial saved on AEPS merchant profile" />
        </ul>
        {!status?.merchant?.device_ready ? (
          <p className="mt-3 text-xs text-amber-800">
            Trade products are blocked until you click Save device with a valid serial.
          </p>
        ) : (
          <p className="mt-3 text-xs text-emerald-700">Device ready — continue to eKYC or Daily 2FA.</p>
        )}
      </section>

      {mobile ? (
        <section className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-950">
          <p className="font-semibold">Phone / Android — fixed flow (do not chase “Advanced” first)</p>
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-sky-900/90">
            <li>
              Open <strong>Mantra L1 RDService</strong> and leave it open. Wait for green{' '}
              <strong>Device connected</strong> and the link{' '}
              <code className="rounded bg-sky-100 px-1">http://127.0.0.1:11100</code>.
            </li>
            <li>
              Settings → Apps → Mantra L1 RDService → Battery → <strong>Unrestricted</strong> (otherwise
              Chrome shows Connection refused).
            </li>
            <li>
              In Chrome open{' '}
              <a
                className="font-semibold underline"
                href="http://127.0.0.1:11100"
                target="_blank"
                rel="noreferrer"
              >
                http://127.0.0.1:11100
              </a>{' '}
              (use <strong>http</strong>, not https).
              <ul className="mt-1 list-disc space-y-1 pl-5">
                <li>
                  <strong>HTTP ERROR 405</strong> → RD is running. Come back here and Detect. No Advanced
                  needed.
                </li>
                <li>
                  <strong>Connection refused</strong> → Mantra is not listening. Fix steps 1–2. There is
                  no Advanced on this screen.
                </li>
              </ul>
            </li>
            <li>
              Only if Detect still fails after 405: open{' '}
              <a
                className="font-semibold underline"
                href="https://127.0.0.1:11100"
                target="_blank"
                rel="noreferrer"
              >
                https://127.0.0.1:11100
              </a>{' '}
              → if you see “not private”, tap <strong>Advanced</strong> → Proceed.
            </li>
            <li>
              Or type Serial No. (e.g. <code className="rounded bg-sky-100 px-1">10888546</code>) → Save
              device. Fingerprint capture still needs Mantra running.
            </li>
          </ol>
          <p className="mt-3 text-xs text-sky-800/80">
            Note: laptop works more reliably because Windows RD stays in the tray. On Android the local
            RD port closes when Mantra is killed — keep the app open while Detect / Capture runs.
          </p>
        </section>
      ) : (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950">
          <p className="font-semibold">If Detect fails while Mantra shows “Capture Success”</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-amber-900/90">
            <li>
              Keep <strong>Mantra L1 RD Service / AVDM</strong> running in the system tray.
            </li>
            <li>
              Prefer{' '}
              <a
                className="font-semibold underline"
                href="http://127.0.0.1:11100"
                target="_blank"
                rel="noreferrer"
              >
                http://127.0.0.1:11100
              </a>{' '}
              (HTTP 405 = RD running). If needed, also trust{' '}
              <a
                className="font-semibold underline"
                href="https://127.0.0.1:11100"
                target="_blank"
                rel="noreferrer"
              >
                https://127.0.0.1:11100
              </a>{' '}
              → Advanced → Proceed.
            </li>
            <li>Return here and click Detect RD Service again.</li>
            <li>
              Optional: in Mantra “Configure” set Certificate Format if capture from the website still
              fails (often <strong>X.509</strong>).
            </li>
          </ol>
        </section>
      )}

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={detect}
            disabled={busy}
            className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            Detect RD Service
          </button>
          <button
            type="button"
            onClick={testCapture}
            disabled={busy}
            className="rounded-lg border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-sm font-semibold text-indigo-900 hover:bg-indigo-100 disabled:opacity-50"
          >
            Test fingerprint capture
          </button>
          <a
            href="http://127.0.0.1:11100"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Open RD http://127.0.0.1:11100
          </a>
          <a
            href="https://127.0.0.1:11100"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center rounded-lg border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Open RD https (cert)
          </a>
        </div>
        {info ? (
          <p className={`mt-4 text-sm ${info.ready ? 'text-emerald-700' : 'text-amber-800'}`}>
            {info.message}
            {info.baseUrl || info.endpoint ? (
              <span className="mt-1 block font-mono text-xs text-slate-500">
                {info.baseUrl || info.endpoint}
              </span>
            ) : null}
          </p>
        ) : null}
        <label className="mt-6 block text-xs font-semibold uppercase tracking-wide text-slate-500">
          Scanner serial / deviceIMEI
          <input
            className="mt-1 w-full max-w-md rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={serial}
            onChange={(e) => setSerial(e.target.value)}
            placeholder="From Mantra app Serial No."
          />
        </label>
        <p className="mt-1 text-xs text-slate-400">
          Tip: copy Serial No. from Mantra L1 RDService if Detect cannot fill it automatically.
        </p>
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

const Check = ({ ok, label }) => (
  <li className={`flex items-center gap-2 ${ok ? 'text-emerald-800' : 'text-slate-600'}`}>
    <span
      className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
        ok ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-500'
      }`}
    >
      {ok ? '✓' : '·'}
    </span>
    {label}
  </li>
);

export default AepsDevice;
