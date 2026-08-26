/**
 * AEPS onboarding KYC images: convert file → compact JPEG base64 in the browser.
 * Only the base64 string is stored/sent (no JPG file upload to disk).
 */

export const AEPS_IMAGE_MAX_B64_CHARS = 180000; // ~135KB binary — keeps Fingpay POST fast
export const AEPS_IMAGE_MAX_EDGE = 960;
export const AEPS_IMAGE_JPEG_QUALITY = 0.72;

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(new Error('Could not read image file.'));
    reader.readAsDataURL(file);
  });
}

function loadImage(dataUrl) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error('Invalid image file.'));
    img.src = dataUrl;
  });
}

function canvasToJpegBase64(canvas, quality) {
  const dataUrl = canvas.toDataURL('image/jpeg', quality);
  const comma = dataUrl.indexOf(',');
  return comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl;
}

/**
 * Compress a browser File to raw JPEG base64 (no data: prefix).
 * Retries at lower quality until under maxChars.
 */
export async function fileToCompactJpegBase64(
  file,
  {
    maxEdge = AEPS_IMAGE_MAX_EDGE,
    maxChars = AEPS_IMAGE_MAX_B64_CHARS,
    quality = AEPS_IMAGE_JPEG_QUALITY,
  } = {}
) {
  if (!file || !String(file.type || '').startsWith('image/')) {
    throw new Error('Please choose a JPG or PNG image.');
  }
  const dataUrl = await readFileAsDataUrl(file);
  const img = await loadImage(dataUrl);
  const scale = Math.min(1, maxEdge / Math.max(img.width || 1, img.height || 1));
  const width = Math.max(1, Math.round((img.width || 1) * scale));
  const height = Math.max(1, Math.round((img.height || 1) * scale));

  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('Could not process image in this browser.');
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(img, 0, 0, width, height);

  let q = quality;
  let b64 = canvasToJpegBase64(canvas, q);
  while (b64.length > maxChars && q > 0.35) {
    q -= 0.08;
    b64 = canvasToJpegBase64(canvas, q);
  }
  if (b64.length > maxChars) {
    // Second pass: smaller edge
    const canvas2 = document.createElement('canvas');
    const w2 = Math.max(1, Math.round(width * 0.7));
    const h2 = Math.max(1, Math.round(height * 0.7));
    canvas2.width = w2;
    canvas2.height = h2;
    const ctx2 = canvas2.getContext('2d');
    ctx2.fillStyle = '#ffffff';
    ctx2.fillRect(0, 0, w2, h2);
    ctx2.drawImage(canvas, 0, 0, w2, h2);
    b64 = canvasToJpegBase64(canvas2, 0.55);
  }
  if (b64.length > maxChars) {
    throw new Error(
      `Image is still too large after compression (${Math.round(b64.length / 1024)} KB base64). Use a simpler photo under ~200KB.`
    );
  }
  return {
    base64: b64,
    bytesApprox: Math.round((b64.length * 3) / 4),
    width,
    height,
  };
}

export function base64ToDataUrl(base64, mime = 'image/jpeg') {
  const raw = String(base64 || '').trim();
  if (!raw) return '';
  if (raw.startsWith('data:')) return raw;
  return `data:${mime};base64,${raw}`;
}

/** Trigger a JPEG download from stored base64 (decode in browser). */
export function downloadBase64AsJpeg(base64, filename = 'aeps-kyc.jpg') {
  const dataUrl = base64ToDataUrl(base64);
  if (!dataUrl) return;
  const a = document.createElement('a');
  a.href = dataUrl;
  a.download = filename.endsWith('.jpg') || filename.endsWith('.jpeg') ? filename : `${filename}.jpg`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}
