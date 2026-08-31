import React, { useEffect, useState } from 'react';
import aepsAPI from '../services/aepsApi';
import { captureMantraFingerprint, detectMantraRd, isMobileBrowser } from '../services/mantraRd';

const AepsDevice = ({ aepsStatus: status, refreshStatus }) => {
  const [info, setInfo] = useState(null);
  const [deviceImei, setDeviceImei] = useState(status?.merchant?.device_imei || '');
  const [scannerSerial, setScannerSerial] = useState(status?.merchant?.scanner_serial || '');
  const [msg, setMsg] = useState('');
  const [busy, setBusy] = useState(false);
  const [mobile, setMobile] = useState(false);

  useEffect(() => {
    setDeviceImei(status?.merchant?.device_imei || '');
    setScannerSerial(status?.merchant?.scanner_serial || '');
  }, [status?.merchant?.device_imei, status?.merchant?.scanner_serial]);

  useEffect(() => {
    setMobile(isMobileBrowser());
  }, []);

  const detect = async () => {
    setBusy(true);
    setMsg('');
    const r = await detectMantraRd();
    setInfo(r);
    if (r.serial) setScannerSerial(r.serial);
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
    const res = await aepsAPI.registerDevice(deviceImei, scannerSerial);
    setMsg(res.success ? 'Device saved for AEPS.' : res.message);
    await refreshStatus();
    setBusy(false);
  };

  return (
    <div className="space-y-6">
      <header>
        <h2 className="text-xl font-bold text-slate-900 dark:text-slate-100">Mantra device</h2>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Save your phone/tablet IMEI for Fingpay (deviceIMEI header) and your Mantra scanner serial for
          fingerprint capture. These are different values — eKYC Send OTP needs the phone IMEI.
        </p>
      </header>

      <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Readiness checklist</p>
        <ul className="mt-3 space-y-2 text-sm">
          <Check ok={!!scannerSerial} label="Mantra scanner serial available" />
          <Check ok={!!deviceImei} label="Phone/tablet IMEI entered" />
          <Check ok={!!status?.merchant?.device_ready} label="Device saved on AEPS merchant profile" />
        </ul>
        {!status?.merchant?.device_ready ? (
          <p className="mt-3 text-xs text-amber-800 dark:text-amber-300">
            Trade products are blocked until you save a valid phone/tablet IMEI (15 digits).
          </p>
        ) : (
          <p className="mt-3 text-xs text-emerald-700 dark:text-emerald-300">Device ready — continue to eKYC or Daily 2FA.</p>
        )}
      </section>

      {mobile ? (
        <section className="rounded-2xl border border-sky-200 dark:border-sky-800 bg-sky-50 dark:bg-sky-950/40 px-4 py-3 text-sm text-sky-950 dark:text-sky-200">
          <p className="font-semibold">Phone / Android — fixed flow (do not chase “Advanced” first)</p>
          <ol className="mt-2 list-decimal space-y-2 pl-5 text-sky-900/90 dark:text-sky-300/90">
            <li>
              Open <strong>Mantra L1 RDService</strong> and leave it open. Wait for green{' '}
              <strong>Device connected</strong> and the link{' '}
              <code className="rounded bg-sky-100 dark:bg-sky-900/40 px-1">http://127.0.0.1:11100</code>.
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
              Or type Serial No. (e.g. <code className="rounded bg-sky-100 dark:bg-sky-900/40 px-1">10888546</code>) → Save
              device. Fingerprint capture still needs Mantra running.
            </li>
          </ol>
          <p className="mt-3 text-xs text-sky-800/80 dark:text-sky-300/80">
            Note: laptop works more reliably because Windows RD stays in the tray. On Android the local
            RD port closes when Mantra is killed — keep the app open while Detect / Capture runs.
          </p>
        </section>
      ) : (
        <section className="rounded-2xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-950 dark:text-amber-200">
          <p className="font-semibold">If Detect fails while Mantra shows “Capture Success”</p>
          <ol className="mt-2 list-decimal space-y-1 pl-5 text-amber-900/90 dark:text-amber-300/90">
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

      <section className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-6 shadow-sm">
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
            className="rounded-lg border border-indigo-200 dark:border-indigo-800 bg-indigo-50 dark:bg-indigo-950/40 px-4 py-2.5 text-sm font-semibold text-indigo-900 dark:text-indigo-300 hover:bg-indigo-100 dark:hover:bg-indigo-900/60 disabled:opacity-50"
          >
            Test fingerprint capture
          </button>
          <a
            href="http://127.0.0.1:11100"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            Open RD http://127.0.0.1:11100
          </a>
          <a
            href="https://127.0.0.1:11100"
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-2.5 text-sm font-semibold text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800"
          >
            Open RD https (cert)
          </a>
        </div>
        {info ? (
          <p className={`mt-4 text-sm ${info.ready ? 'text-emerald-700 dark:text-emerald-300' : 'text-amber-800 dark:text-amber-300'}`}>
            {info.message}
            {info.baseUrl || info.endpoint ? (
              <span className="mt-1 block font-mono text-xs text-slate-500 dark:text-slate-400">
                {info.baseUrl || info.endpoint}
              </span>
            ) : null}
          </p>
        ) : null}
        <label className="mt-6 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Phone / tablet IMEI (Fingpay deviceIMEI)
          <input
            className="mt-1 w-full max-w-md rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2 font-mono text-sm"
            value={deviceImei}
            onChange={(e) => setDeviceImei(e.target.value.replace(/\D/g, '').slice(0, 16))}
            placeholder="e.g. 352801082418919"
          />
        </label>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          Dial *#06# on your phone or check Settings → About phone. Required for eKYC Send OTP.
        </p>
        <label className="mt-4 block text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
          Mantra scanner serial
          <input
            className="mt-1 w-full max-w-md rounded-lg border border-slate-200 dark:border-slate-700 px-3 py-2 font-mono text-sm"
            value={scannerSerial}
            onChange={(e) => setScannerSerial(e.target.value)}
            placeholder="From Mantra app Serial No."
          />
        </label>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          Click Detect RD Service to auto-fill, or copy Serial No. from Mantra L1 RDService.
        </p>
        <button
          type="button"
          onClick={save}
          disabled={busy || !deviceImei}
          className="mt-4 rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Save device
        </button>
        {msg ? <p className="mt-3 text-sm text-slate-700 dark:text-slate-300">{msg}</p> : null}
      </section>
    </div>
  );
};

const Check = ({ ok, label }) => (
  <li className={`flex items-center gap-2 ${ok ? 'text-emerald-800 dark:text-emerald-300' : 'text-slate-600 dark:text-slate-400'}`}>
    <span
      className={`inline-flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${
        ok ? 'bg-emerald-100 dark:bg-emerald-900/40 text-emerald-800 dark:text-emerald-300' : 'bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400'
      }`}
    >
      {ok ? '✓' : '·'}
    </span>
    {label}
  </li>
);

export default AepsDevice;
