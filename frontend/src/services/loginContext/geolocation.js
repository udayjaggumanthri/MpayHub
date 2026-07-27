/**
 * HTML5 Geolocation capture for login (non-blocking).
 * Native browser prompt; Allow/Never is remembered by the browser.
 */

const GEO_TIMEOUT_MS = 8000;
const GEO_MAXIMUM_AGE_MS = 60_000;

/**
 * @typedef {'granted'|'denied'|'unavailable'|'timeout'|'pending'} GeoStatus
 * @typedef {{
 *   status: GeoStatus,
 *   latitude?: number|null,
 *   longitude?: number|null,
 *   accuracy?: number|null,
 * }} BrowserGeo
 */

/** @returns {BrowserGeo} */
export function emptyBrowserGeo(status = 'unavailable') {
  return {
    status,
    latitude: null,
    longitude: null,
    accuracy: null,
  };
}

/**
 * Request current position once. Never throws.
 * @returns {Promise<BrowserGeo>}
 */
export function requestBrowserGeolocation() {
  if (typeof navigator === 'undefined' || !navigator.geolocation) {
    return Promise.resolve(emptyBrowserGeo('unavailable'));
  }

  // Geolocation requires a secure context (HTTPS or localhost)
  if (typeof window !== 'undefined' && window.isSecureContext === false) {
    return Promise.resolve(emptyBrowserGeo('unavailable'));
  }

  return new Promise((resolve) => {
    try {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const coords = pos?.coords;
          const lat = coords?.latitude;
          const lng = coords?.longitude;
          if (typeof lat !== 'number' || typeof lng !== 'number' || Number.isNaN(lat) || Number.isNaN(lng)) {
            resolve(emptyBrowserGeo('unavailable'));
            return;
          }
          resolve({
            status: 'granted',
            latitude: lat,
            longitude: lng,
            accuracy: typeof coords.accuracy === 'number' ? coords.accuracy : null,
          });
        },
        (err) => {
          const code = err?.code;
          if (code === 1) {
            resolve(emptyBrowserGeo('denied'));
          } else if (code === 3) {
            resolve(emptyBrowserGeo('timeout'));
          } else {
            resolve(emptyBrowserGeo('unavailable'));
          }
        },
        {
          enableHighAccuracy: false,
          timeout: GEO_TIMEOUT_MS,
          maximumAge: GEO_MAXIMUM_AGE_MS,
        }
      );
    } catch {
      resolve(emptyBrowserGeo('unavailable'));
    }
  });
}
