/**
 * Lightweight device / browser context for login audit (no third-party SDK).
 */

/**
 * @param {string} ua
 * @returns {{ browser_name: string, browser_version: string }}
 */
export function parseBrowser(ua = '') {
  const s = String(ua || '');
  const rules = [
    { name: 'Edge', re: /Edg(?:e|A|iOS)?\/([\d.]+)/ },
    { name: 'Opera', re: /OPR\/([\d.]+)/ },
    { name: 'Chrome', re: /Chrome\/([\d.]+)/ },
    { name: 'Firefox', re: /Firefox\/([\d.]+)/ },
    { name: 'Safari', re: /Version\/([\d.]+).*Safari/ },
    { name: 'Samsung Internet', re: /SamsungBrowser\/([\d.]+)/ },
  ];
  for (const rule of rules) {
    const m = s.match(rule.re);
    if (m) {
      return { browser_name: rule.name, browser_version: (m[1] || '').split('.')[0] || m[1] || '' };
    }
  }
  return { browser_name: 'Unknown', browser_version: '' };
}

/**
 * @param {string} ua
 * @returns {string}
 */
export function parseOs(ua = '') {
  const s = String(ua || '');
  if (/Windows NT 10/i.test(s)) return 'Windows';
  if (/Windows NT 6\.3/i.test(s)) return 'Windows 8.1';
  if (/Windows NT 6\.1/i.test(s)) return 'Windows 7';
  if (/Windows/i.test(s)) return 'Windows';
  if (/Android/i.test(s)) return 'Android';
  if (/iPhone|iPad|iPod/i.test(s)) return 'iOS';
  if (/Mac OS X/i.test(s)) return 'macOS';
  if (/CrOS/i.test(s)) return 'Chrome OS';
  if (/Linux/i.test(s)) return 'Linux';
  return 'Unknown';
}

/**
 * @param {string} ua
 * @returns {'desktop'|'mobile'|'tablet'}
 */
export function parseDeviceType(ua = '') {
  const s = String(ua || '');
  if (/iPad|Tablet|PlayBook/i.test(s) || (/Android/i.test(s) && !/Mobile/i.test(s))) {
    return 'tablet';
  }
  if (/Mobi|iPhone|iPod|Android.*Mobile|webOS|BlackBerry|IEMobile/i.test(s)) {
    return 'mobile';
  }
  return 'desktop';
}

/**
 * Collect device facts available in the browser. Never throws.
 * @returns {Record<string, string>}
 */
export function collectDeviceInfo() {
  try {
    const ua = typeof navigator !== 'undefined' ? navigator.userAgent || '' : '';
    const { browser_name, browser_version } = parseBrowser(ua);
    let timezone = '';
    try {
      timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || '';
    } catch {
      timezone = '';
    }
    let screen = '';
    if (typeof window !== 'undefined' && window.screen) {
      const w = window.screen.width;
      const h = window.screen.height;
      if (w && h) screen = `${w}x${h}`;
    }
    return {
      browser_name,
      browser_version: String(browser_version || ''),
      os: parseOs(ua),
      device_type: parseDeviceType(ua),
      screen,
      timezone,
      language: (typeof navigator !== 'undefined' && (navigator.language || '')) || '',
      user_agent: String(ua).slice(0, 2000),
    };
  } catch {
    return {
      browser_name: 'Unknown',
      browser_version: '',
      os: 'Unknown',
      device_type: 'desktop',
      screen: '',
      timezone: '',
      language: '',
      user_agent: '',
    };
  }
}
