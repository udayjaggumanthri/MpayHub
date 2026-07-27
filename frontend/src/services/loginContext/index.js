/**
 * Login client context orchestrator — loosely coupled from Login UI.
 * Start capture on page mount; read a snapshot at submit (short wait if geo pending).
 */

import { collectDeviceInfo } from './deviceInfo';
import { emptyBrowserGeo, requestBrowserGeolocation } from './geolocation';

const SUBMIT_GEO_WAIT_MS = 2000;

/** @type {import('./geolocation').BrowserGeo} */
let browserGeo = emptyBrowserGeo('pending');
/** @type {Promise<import('./geolocation').BrowserGeo>|null} */
let geoPromise = null;
let captureStarted = false;

/**
 * Begin geolocation + warm device parse. Safe to call multiple times.
 */
export function startLoginContextCapture() {
  if (captureStarted) return;
  captureStarted = true;
  browserGeo = emptyBrowserGeo('pending');
  geoPromise = requestBrowserGeolocation().then((geo) => {
    browserGeo = geo;
    return geo;
  });
}

/**
 * @param {number} ms
 * @returns {Promise<void>}
 */
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Snapshot for the login POST body. Never throws.
 * Waits briefly for in-flight geo so Allow clicks near submit are not lost.
 * @returns {Promise<{
 *   browser_geo: import('./geolocation').BrowserGeo,
 *   device: Record<string, string>,
 *   captured_at: string,
 * }>}
 */
export async function getLoginClientContext() {
  if (!captureStarted) {
    startLoginContextCapture();
  }

  if (geoPromise && browserGeo.status === 'pending') {
    await Promise.race([geoPromise, sleep(SUBMIT_GEO_WAIT_MS)]);
  }

  const geo =
    browserGeo.status === 'pending'
      ? emptyBrowserGeo('unavailable')
      : { ...browserGeo };

  return {
    browser_geo: geo,
    device: collectDeviceInfo(),
    captured_at: new Date().toISOString(),
  };
}

/** Test / storybook helper */
export function __resetLoginContextForTests() {
  browserGeo = emptyBrowserGeo('pending');
  geoPromise = null;
  captureStarted = false;
}
