import { normalizeAssetUrl } from './mediaUrl';

/** Trigger a browser download from a Blob. */
export function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = 'noopener';
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

const authHeaders = () => {
  const token = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

function filenameFromDisposition(header, fallback) {
  if (!header) return fallback;
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(header);
  if (!match?.[1]) return fallback;
  try {
    return decodeURIComponent(match[1].replace(/"/g, '').trim());
  } catch {
    return match[1].replace(/"/g, '').trim() || fallback;
  }
}

/** Fetch a URL (with JWT when needed) and download as filename. */
export async function downloadFromUrl(url, filename) {
  const normalized = normalizeAssetUrl(url);
  if (!normalized) throw new Error('Download failed');
  const response = await fetch(normalized, {
    credentials: 'same-origin',
    headers: authHeaders(),
  });
  if (!response.ok) {
    throw new Error('Download failed');
  }
  const blob = await response.blob();
  const resolvedName = filenameFromDisposition(
    response.headers.get('Content-Disposition'),
    filename
  );
  triggerBlobDownload(blob, resolvedName || filename || 'download');
}
