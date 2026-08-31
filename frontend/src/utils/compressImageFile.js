/**
 * Compress a browser File to JPEG, targeting maxBytes (default 100 KB).
 * Skips re-encoding when already under the limit.
 */

const DEFAULT_MAX_BYTES = 100 * 1024;
const DEFAULT_MAX_EDGE = 1280;
const MIN_QUALITY = 0.45;

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

function canvasToJpegBlob(canvas, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (!blob) {
          reject(new Error('Could not compress image.'));
          return;
        }
        resolve(blob);
      },
      'image/jpeg',
      quality
    );
  });
}

function buildFilename(file) {
  const base = String(file.name || 'receipt').replace(/\.[^.]+$/, '') || 'receipt';
  return `${base}.jpg`;
}

/**
 * @param {File} file
 * @param {{ maxBytes?: number, maxEdge?: number }} [options]
 * @returns {Promise<File>}
 */
export async function compressImageFile(
  file,
  { maxBytes = DEFAULT_MAX_BYTES, maxEdge = DEFAULT_MAX_EDGE } = {}
) {
  if (!file || !String(file.type || '').startsWith('image/')) {
    throw new Error('Please choose a JPG, PNG, or WebP image.');
  }
  if (file.size <= maxBytes) {
    return file;
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

  let quality = 0.82;
  let blob = await canvasToJpegBlob(canvas, quality);
  while (blob.size > maxBytes && quality > MIN_QUALITY) {
    quality -= 0.08;
    blob = await canvasToJpegBlob(canvas, quality);
  }

  if (blob.size > maxBytes) {
    const smaller = document.createElement('canvas');
    const w2 = Math.max(1, Math.round(width * 0.75));
    const h2 = Math.max(1, Math.round(height * 0.75));
    smaller.width = w2;
    smaller.height = h2;
    const ctx2 = smaller.getContext('2d');
    ctx2.fillStyle = '#ffffff';
    ctx2.fillRect(0, 0, w2, h2);
    ctx2.drawImage(canvas, 0, 0, w2, h2);
    quality = 0.72;
    blob = await canvasToJpegBlob(smaller, quality);
    while (blob.size > maxBytes && quality > MIN_QUALITY) {
      quality -= 0.08;
      blob = await canvasToJpegBlob(smaller, quality);
    }
  }

  return new File([blob], buildFilename(file), { type: 'image/jpeg', lastModified: Date.now() });
}

export const RECEIPT_MAX_BYTES = DEFAULT_MAX_BYTES;
