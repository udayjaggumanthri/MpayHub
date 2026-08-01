/**
 * Mantra RD Service helpers for web AEPS (captureResponse passthrough).
 * RD typically listens on localhost HTTPS ports; paths vary by RD version.
 */
const RD_CANDIDATES = [
  'https://localhost:11100/rd/capture',
  'https://127.0.0.1:11100/rd/capture',
  'https://localhost:11100/capture',
  'http://127.0.0.1:11100/rd/capture',
];

const INFO_CANDIDATES = [
  'https://localhost:11100/rd/info',
  'https://127.0.0.1:11100/rd/info',
  'https://localhost:11100/getDeviceInfo',
];

async function tryFetch(url, options) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 4000);
  try {
    const res = await fetch(url, { ...options, signal: ctrl.signal });
    const text = await res.text();
    return { ok: res.ok, text, url };
  } catch (e) {
    return { ok: false, error: e, url };
  } finally {
    clearTimeout(t);
  }
}

function parseXmlDeviceSerial(xml) {
  if (!xml) return '';
  const m =
    xml.match(/srno=["']([^"']+)["']/i) ||
    xml.match(/<serial[^>]*>([^<]+)</i) ||
    xml.match(/deviceId=["']([^"']+)["']/i);
  return m ? m[1] : '';
}

/**
 * Best-effort RD detection. Returns { ready, serial, message, infoXml }.
 */
export async function detectMantraRd() {
  for (const url of INFO_CANDIDATES) {
    const r = await tryFetch(url, { method: 'GET' });
    if (r.ok && r.text) {
      const serial = parseXmlDeviceSerial(r.text);
      return {
        ready: true,
        serial,
        message: serial ? `Mantra RD detected (${serial})` : 'Mantra RD Service detected',
        infoXml: r.text,
        endpoint: url,
      };
    }
  }
  return {
    ready: false,
    serial: '',
    message:
      'Mantra RD Service not detected. Install/start Mantra RD Service and plug in the fingerprint device, then retry.',
    infoXml: '',
    endpoint: null,
  };
}

/**
 * Capture fingerprint via RD. Returns opaque captureResponse object/string for Fingpay.
 * Pid options follow common Mantra RD PID OPTIONS XML.
 */
export async function captureMantraFingerprint({ fCount = 1, timeout = 20000 } = {}) {
  const pidOptions = `<?xml version="1.0"?>` +
    `<PidOptions ver="1.0">` +
    `<Opts fCount="${fCount}" fType="2" iCount="0" pCount="0" format="0" pidVer="2.0" timeout="${timeout}" otp="" wadh="" posh="UNKNOWN" />` +
    `</PidOptions>`;

  let lastError = 'Capture failed';
  for (const url of RD_CANDIDATES) {
    const r = await tryFetch(url, {
      method: 'CAPTURE',
      headers: { 'Content-Type': 'text/xml' },
      body: pidOptions,
    });
    // Some RD builds only accept POST
    const result =
      r.ok && r.text
        ? r
        : await tryFetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'text/xml' },
            body: pidOptions,
          });
    if (result.ok && result.text) {
      // Parse common RD XML into Fingpay captureResponse shape when possible;
      // otherwise send raw XML under Piddata-compatible envelope.
      const captureResponse = xmlToCaptureResponse(result.text);
      return { success: true, captureResponse, rawXml: result.text };
    }
    lastError = result.error?.message || lastError;
  }
  return {
    success: false,
    message: lastError || 'Unable to reach Mantra RD Service for capture.',
  };
}

function attr(xml, name) {
  const m = xml.match(new RegExp(`${name}=["']([^"']*)["']`, 'i'));
  return m ? m[1] : '';
}

function tag(xml, name) {
  const m = xml.match(new RegExp(`<${name}[^>]*>([\\s\\S]*?)</${name}>`, 'i'));
  return m ? m[1].trim() : '';
}

function xmlToCaptureResponse(xml) {
  // Prefer structured fields Fingpay expects; keep Piddata as-is.
  const pidData = tag(xml, 'Data') || attr(xml, 'Piddata') || '';
  return {
    errCode: attr(xml, 'errCode') || '0',
    errInfo: attr(xml, 'errInfo') || 'Image Capture Success',
    fCount: attr(xml, 'fCount') || '1',
    fType: attr(xml, 'fType') || '0',
    iCount: attr(xml, 'iCount') || '0',
    iType: attr(xml, 'iType') || '',
    pCount: attr(xml, 'pCount') || '0',
    pType: attr(xml, 'pType') || '',
    nmPoints: attr(xml, 'nmPoints') || '',
    qScore: attr(xml, 'qScore') || '',
    dpID: attr(xml, 'dpId') || attr(xml, 'dpID') || '',
    rdsID: attr(xml, 'rdsId') || attr(xml, 'rdsID') || '',
    rdsVer: attr(xml, 'rdsVer') || '',
    dc: attr(xml, 'dc') || '',
    mi: attr(xml, 'mi') || '',
    mc: attr(xml, 'mc') || '',
    ci: attr(xml, 'ci') || '',
    sessionKey: tag(xml, 'Skey') || attr(xml, 'sessionKey') || '',
    hmac: tag(xml, 'Hmac') || attr(xml, 'hmac') || '',
    PidDatatype: attr(xml, 'type') || 'X',
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
