/**
 * Mantra L1 RD Service helpers for web AEPS (desktop + Android Chrome).
 *
 * UIDAI desktop RDService: HTTP on 127.0.0.1 ports 11100–11120
 *   Discover:  method RDSERVICE  → /
 *   Info:      method DEVICEINFO → /rd/info
 *   Capture:   method CAPTURE    → /rd/capture
 *
 * Chrome/Edge treat loopback as trustworthy: an https:// site MAY call
 * http://127.0.0.1 (mixed-content exemption). Prefer HTTP first — HTTPS
 * needs a one-time self-signed cert trust and often fails on Android.
 *
 * Opening http://127.0.0.1:11100 in Chrome often shows HTTP 405 — that means
 * RD is running (GET is not allowed).
 *
 * Android note: UIDAI's native path is Intent-based. Mantra L1 RDService also
 * exposes localhost while the app is running; if the app is killed, Chrome
 * shows ERR_CONNECTION_REFUSED. Keep Mantra open / battery unrestricted.
 */

const RD_PORT_START = 11100;
const RD_PORT_END = 11120;

export function isMobileBrowser() {
  if (typeof navigator === 'undefined') return false;
  return /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent || '');
}

/**
 * Prefer HTTP on loopback first (mixed-content OK for 127.0.0.1 in Chrome).
 * HTTPS is fallback when the driver only speaks TLS or HTTP is blocked.
 */
function preferredSchemes() {
  return ['http', 'https'];
}

function preferredHosts() {
  return ['127.0.0.1', 'localhost'];
}

function xhrRequest(url, { method = 'GET', headers = {}, body = null, timeoutMs = 4000 } = {}) {
  return new Promise((resolve) => {
    try {
      const xhr = new XMLHttpRequest();
      xhr.open(method, url, true);
      Object.entries(headers || {}).forEach(([k, v]) => {
        try {
          xhr.setRequestHeader(k, v);
        } catch {
          /* ignore forbidden headers */
        }
      });
      xhr.timeout = timeoutMs;
      xhr.onload = () => {
        resolve({
          ok: xhr.status >= 200 && xhr.status < 300,
          status: xhr.status,
          text: xhr.responseText || '',
          url,
        });
      };
      xhr.onerror = () =>
        resolve({ ok: false, status: 0, text: '', url, error: new Error('network'), aborted: false });
      xhr.ontimeout = () =>
        resolve({ ok: false, status: 0, text: '', url, error: new Error('timeout'), aborted: true });
      xhr.send(body);
    } catch (e) {
      resolve({ ok: false, status: 0, text: '', url, error: e });
    }
  });
}

async function tryFetch(url, options = {}, timeoutMs = 4000) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = options.headers || {};
  const body = options.body ?? null;

  // Custom verbs (RDSERVICE/DEVICEINFO/CAPTURE): prefer XHR — more reliable on Android Chrome.
  if (!['GET', 'POST', 'HEAD', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    return xhrRequest(url, { method, headers, body, timeoutMs });
  }

  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, {
      ...options,
      signal: ctrl.signal,
      cache: 'no-store',
      mode: 'cors',
    });
    const text = await res.text();
    return { ok: res.ok || !!text, status: res.status, text: text || '', url };
  } catch (e) {
    const viaXhr = await xhrRequest(url, { method, headers, body, timeoutMs });
    if (viaXhr.text || viaXhr.status) return viaXhr;
    return {
      ok: false,
      status: 0,
      text: '',
      url,
      error: e,
      aborted: e?.name === 'AbortError',
    };
  } finally {
    clearTimeout(t);
  }
}

function parseAttr(xml, name) {
  if (!xml) return '';
  const m = xml.match(new RegExp(`${name}\\s*=\\s*["']([^"']*)["']`, 'i'));
  return m ? m[1] : '';
}

function parseTag(xml, name) {
  if (!xml) return '';
  const m = xml.match(new RegExp(`<${name}[^>]*>([\\s\\S]*?)</${name}>`, 'i'));
  return m ? m[1].trim() : '';
}

function parseXmlDeviceSerial(xml) {
  if (!xml) return '';
  const patterns = [
    /name\s*=\s*["']srno["'][^>]*value\s*=\s*["']([^"']+)["']/i,
    /value\s*=\s*["']([^"']+)["'][^>]*name\s*=\s*["']srno["']/i,
    /srno\s*=\s*["']([^"']+)["']/i,
    /serialNumber\s*=\s*["']([^"']+)["']/i,
    /<serial[^>]*>([^<]+)</i,
    /deviceId\s*=\s*["']([^"']+)["']/i,
  ];
  for (const re of patterns) {
    const m = xml.match(re);
    if (m?.[1]) return m[1].trim();
  }
  return '';
}

function parseRdStatus(xml) {
  const status = (parseAttr(xml, 'status') || '').toUpperCase();
  const info = parseAttr(xml, 'info') || '';
  return { status, info };
}

function looksLikeRdServiceXml(text) {
  return !!text && (/RDService/i.test(text) || /status\s*=/i.test(text));
}

function trustHint({ connectionRefused = false } = {}) {
  const mobile = isMobileBrowser();
  if (mobile) {
    if (connectionRefused) {
      return (
        ' Mantra L1 RDService is not listening on this phone (Connection refused). ' +
        'Open Mantra, wait for green Device connected and http://127.0.0.1:11100, set Battery → Unrestricted, ' +
        'then open http://127.0.0.1:11100 in Chrome — HTTP 405 means RD is up. Retry Detect while Mantra stays open. ' +
        '“Advanced” only appears for HTTPS certificate warnings, not for Connection refused.'
      );
    }
    return (
      ' Keep Mantra L1 RDService open. First open http://127.0.0.1:11100 in Chrome (HTTP 405 = OK). ' +
      'Only if Detect still fails, try https://127.0.0.1:11100 → Advanced → Proceed. ' +
      'Fix “Management server not reachable” if shown. You can also type Serial No. and Save device.'
    );
  }
  return (
    ' Keep Mantra RD running. Prefer http://127.0.0.1:11100 (405 = OK). ' +
    'If only HTTPS works, open https://127.0.0.1:11100 once → Advanced → Proceed, then retry Detect.'
  );
}

/**
 * Quick liveness: GET often returns 405 when Mantra RD is up.
 */
async function probeRdAlive(base) {
  const r = await tryFetch(base, { method: 'GET' }, 2000);
  if (r.status === 405 || r.status === 404 || (r.status >= 200 && r.status < 500)) {
    return { alive: true, status: r.status, url: base };
  }
  return { alive: false, status: r.status, url: base, error: r.error };
}

function interpretRdServiceResult(r) {
  if (!r?.text || !looksLikeRdServiceXml(r.text)) return null;
  const { status, info } = parseRdStatus(r.text);
  if (status === 'READY' || status === 'USED') {
    return {
      ready: true,
      baseUrl: r.url.replace(/\/$/, ''),
      status,
      infoXml: r.text,
      message:
        status === 'READY'
          ? 'Mantra RD Service detected and READY'
          : 'Mantra RD Service detected (USED — close other capture apps and retry)',
    };
  }
  if (status === 'NOTREADY' || status === 'NOT READY') {
    return {
      ready: false,
      baseUrl: r.url.replace(/\/$/, ''),
      status,
      infoXml: r.text,
      message:
        info ||
        'Mantra RD is running but NOTREADY. In Mantra L1 RDService, fix “Management server not reachable”, keep device connected, then retry.',
    };
  }
  return null;
}

async function probeRdService(base, timeoutMs) {
  return tryFetch(base, { method: 'RDSERVICE', headers: { 'Content-Type': 'text/xml' } }, timeoutMs);
}

/**
 * Discover active Mantra RD port via RDSERVICE method.
 * Fast-path: common http://127.0.0.1:11100 before full scan.
 */
export async function discoverMantraRd() {
  const schemes = preferredSchemes();
  const hosts = preferredHosts();
  const timeoutMs = isMobileBrowser() ? 6000 : 2500;

  // Fast path — Mantra almost always uses 11100 over HTTP.
  const fastBases = [
    'http://127.0.0.1:11100',
    'http://localhost:11100',
    'https://127.0.0.1:11100',
    'https://localhost:11100',
  ];

  let sawTlsOrNetworkFailure = false;
  let sawAnyLivePort = false;
  let sawAliveButNoRdXmlLocal = null;
  let notReady = null;

  for (const base of fastBases) {
    const r = await probeRdService(base, timeoutMs);
    const hit = interpretRdServiceResult(r);
    if (hit?.ready) return hit;
    if (hit && !hit.ready) notReady = hit;
    if (r.text || r.status) sawAnyLivePort = true;
    if (!r.text && r.status === 0) {
      if (r.error && !r.aborted) sawTlsOrNetworkFailure = true;
      const alive = await probeRdAlive(base);
      if (alive.alive) {
        sawAliveButNoRdXmlLocal = alive;
        sawAnyLivePort = true;
      }
    }
    if (r.status === 405 && !looksLikeRdServiceXml(r.text)) {
      sawAliveButNoRdXmlLocal = { alive: true, status: 405, url: base };
      sawAnyLivePort = true;
    }
  }

  const ports = [];
  for (let p = RD_PORT_START; p <= RD_PORT_END; p += 1) ports.push(p);

  const candidates = [];
  for (const scheme of schemes) {
    for (const host of hosts) {
      for (const port of ports) {
        const base = `${scheme}://${host}:${port}`;
        if (!fastBases.includes(base)) candidates.push(base);
      }
    }
  }

  const batchSize = isMobileBrowser() ? 3 : 8;
  for (let i = 0; i < candidates.length; i += batchSize) {
    const batch = candidates.slice(i, i + batchSize);
    const results = await Promise.all(batch.map((base) => probeRdService(base, timeoutMs)));

    for (const r of results) {
      const hit = interpretRdServiceResult(r);
      if (hit?.ready) return hit;
      if (hit && !hit.ready) notReady = hit;

      if (!r.text) {
        if (r.error && !r.aborted) sawTlsOrNetworkFailure = true;
        if (r.status === 0) {
          const alive = await probeRdAlive(r.url);
          if (alive.alive) {
            sawAliveButNoRdXmlLocal = alive;
            sawAnyLivePort = true;
          }
        }
        continue;
      }
      sawAnyLivePort = true;
      if (!looksLikeRdServiceXml(r.text) && r.status === 405) {
        sawAliveButNoRdXmlLocal = { alive: true, status: 405, url: r.url };
      }
    }
  }

  if (notReady) return notReady;

  if (sawAliveButNoRdXmlLocal?.alive) {
    return {
      ready: false,
      baseUrl: (sawAliveButNoRdXmlLocal.url || '').replace(/\/$/, ''),
      status: 'ALIVE_NO_API',
      infoXml: '',
      message:
        `Mantra RD port is open (browser got HTTP ${sawAliveButNoRdXmlLocal.status || 405}), but mPayHub could not call RDSERVICE.` +
        trustHint() +
        ' You can still type the Serial No. from the Mantra app and Save device.',
    };
  }

  if (!sawAnyLivePort) {
    return {
      ready: false,
      baseUrl: '',
      status: 'CONNECTION_REFUSED',
      infoXml: '',
      message: `Mantra RD is not running on this device (browser: connection refused on 127.0.0.1:11100).${trustHint({
        connectionRefused: true,
      })}`,
    };
  }

  return {
    ready: false,
    baseUrl: '',
    status: '',
    infoXml: '',
    message: sawTlsOrNetworkFailure
      ? `Mantra RD Service not reachable from the browser.${trustHint()}`
      : `Mantra RD Service not detected on ports ${RD_PORT_START}–${RD_PORT_END}. Open Mantra L1 RDService, keep scanner connected, then retry.${trustHint()}`,
  };
}

export async function detectMantraRd() {
  const disc = await discoverMantraRd();
  if (!disc.ready || !disc.baseUrl) {
    return {
      ready: false,
      serial: '',
      message: disc.message,
      infoXml: disc.infoXml || '',
      endpoint: disc.baseUrl || null,
      status: disc.status || '',
      mobile: isMobileBrowser(),
    };
  }

  const infoUrl = `${disc.baseUrl}/rd/info`;
  const infoRes = await tryFetch(
    infoUrl,
    { method: 'DEVICEINFO', headers: { 'Content-Type': 'text/xml' } },
    isMobileBrowser() ? 8000 : 5000
  );

  let serial = parseXmlDeviceSerial(infoRes.text);
  if (!serial) serial = parseXmlDeviceSerial(disc.infoXml);

  return {
    ready: true,
    serial,
    message: serial
      ? `Mantra RD ready — serial ${serial}`
      : disc.message || 'Mantra RD Service detected',
    infoXml: infoRes.text || disc.infoXml,
    endpoint: infoUrl,
    baseUrl: disc.baseUrl,
    status: disc.status,
    mobile: isMobileBrowser(),
  };
}

// Fingpay Simple API eKYC PidOptions.
// Live Fingpay returns 10031 "Only FMR FIR based transaction are allowed" unless fType=2.
// WADH is the e-KYC value from SIMPLE API FOR E-KYC doc.
const EKYC_WADH = 'E0jzJ/P8UopUHAieZn8CKqS4WPMi5ZSYXgfnlfkWjrc=';

function buildPidOptions({ fCount = 1, timeout = 20000, purpose = 'aeps' } = {}) {
  // env="P" is required by several drivers (incl. Mantra) even on UAT.
  if (purpose === 'ekyc') {
    return (
      `<?xml version="1.0"?>` +
      `<PidOptions ver="1.0">` +
      `<Opts env="P" fCount="${fCount}" fType="2" iCount="0" pCount="0" format="0" pidVer="2.0" ` +
      `timeout="${timeout}" wadh="${EKYC_WADH}" posh="UNKNOWN" />` +
      `</PidOptions>`
    );
  }
  // Mini Statement / 2FA sample captureResponse uses fType=0 (FMR). eKYC stays fType=2 above.
  return (
    `<?xml version="1.0"?>` +
    `<PidOptions ver="1.0">` +
    `<Opts fCount="${fCount}" fType="0" iCount="0" pCount="0" format="0" pidVer="2.0" ` +
    `timeout="${timeout}" otp="" wadh="" posh="UNKNOWN" env="P" />` +
    `</PidOptions>`
  );
}

export async function captureMantraFingerprint({ fCount = 1, timeout = 20000, purpose = 'aeps' } = {}) {
  const disc = await discoverMantraRd();
  if (!disc.ready || !disc.baseUrl) {
    return {
      success: false,
      message: disc.message || 'Mantra RD Service not ready for capture.',
    };
  }

  const captureUrl = `${disc.baseUrl}/rd/capture`;
  const result = await tryFetch(
    captureUrl,
    {
      method: 'CAPTURE',
      headers: { 'Content-Type': 'text/xml' },
      body: buildPidOptions({ fCount, timeout, purpose }),
    },
    Math.max(timeout + 5000, 25000)
  );

  if (!result.text) {
    return {
      success: false,
      message:
        result.error?.message ||
        'Unable to reach Mantra RD capture endpoint.' + trustHint(),
    };
  }

  const errCode = parseAttr(result.text, 'errCode');
  if (errCode && errCode !== '0') {
    const errInfo = parseAttr(result.text, 'errInfo') || 'Fingerprint capture failed';
    return {
      success: false,
      message: `${errInfo} (errCode ${errCode})`,
      rawXml: result.text,
    };
  }

  if (
    /NOTREADY|device not connected|Please connect/i.test(result.text) &&
    !/<Data[\s>]/i.test(result.text)
  ) {
    return {
      success: false,
      message:
        'Please connect the fingerprint device, then retry. If Mantra shows “Management server not reachable”, fix internet access to Mantra servers first.',
      rawXml: result.text,
    };
  }

  return {
    success: true,
    captureResponse: xmlToCaptureResponse(result.text),
    rawXml: result.text,
    baseUrl: disc.baseUrl,
  };
}

function xmlToCaptureResponse(xml) {
  const dataOpen = xml.match(/<Data\b[^>]*>/i)?.[0] || '';
  const pidData = parseTag(xml, 'Data') || '';
  return {
    errCode: parseAttr(xml, 'errCode') || '0',
    errInfo: parseAttr(xml, 'errInfo') || 'Success',
    fCount: parseAttr(xml, 'fCount') || '1',
    fType: parseAttr(xml, 'fType') || '0',
    iCount: parseAttr(xml, 'iCount') || '0',
    iType: parseAttr(xml, 'iType') || '',
    pCount: parseAttr(xml, 'pCount') || '0',
    pType: parseAttr(xml, 'pType') || '',
    nmPoints: parseAttr(xml, 'nmPoints') || '',
    qScore: parseAttr(xml, 'qScore') || '',
    dpID: parseAttr(xml, 'dpId') || parseAttr(xml, 'dpID') || '',
    rdsID: parseAttr(xml, 'rdsId') || parseAttr(xml, 'rdsID') || '',
    rdsVer: parseAttr(xml, 'rdsVer') || '',
    dc: parseAttr(xml, 'dc') || '',
    mi: parseAttr(xml, 'mi') || '',
    mc: parseAttr(xml, 'mc') || '',
    ci: parseAttr(xml, 'ci') || parseAttr(dataOpen || xml, 'ci') || '',
    sessionKey: parseTag(xml, 'Skey') || parseAttr(xml, 'sessionKey') || '',
    hmac: parseTag(xml, 'Hmac') || parseAttr(xml, 'hmac') || '',
    PidDatatype: parseAttr(dataOpen || xml, 'type') || 'X',
    Piddata: pidData || xml,
  };
}

export async function getBrowserGeo() {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve({ status: 'denied', latitude: null, longitude: null });
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          status: 'granted',
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }),
      () => resolve({ status: 'denied', latitude: null, longitude: null }),
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 60000 }
    );
  });
}
