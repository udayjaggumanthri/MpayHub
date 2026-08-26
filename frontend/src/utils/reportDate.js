/**
 * Report date filters: display DD/MM/YYYY, store/send ISO YYYY-MM-DD.
 * Same rules on every device — do not rely on the browser's native date locale.
 */

export const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/;
export const DMY_DATE_RE = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/;

export function todayIsoDate() {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function isoYearBounds() {
  return { minYear: 2000, maxYear: new Date().getFullYear() };
}

export function daysInMonth(year, month) {
  return new Date(year, month, 0).getDate();
}

function pad2(n) {
  return String(n).padStart(2, '0');
}

export function isIsoDateInRange(iso) {
  const value = String(iso || '').trim();
  if (!ISO_DATE_RE.test(value)) return false;
  const [ys, ms, ds] = value.split('-');
  const y = Number(ys);
  const m = Number(ms);
  const d = Number(ds);
  const { minYear, maxYear } = isoYearBounds();
  if (y < minYear || y > maxYear) return false;
  const dt = new Date(y, m - 1, d);
  if (dt.getFullYear() !== y || dt.getMonth() !== m - 1 || dt.getDate() !== d) return false;
  return value <= todayIsoDate();
}

export function isoToDmy(iso) {
  const value = String(iso || '').trim();
  if (!ISO_DATE_RE.test(value)) return '';
  const [y, m, d] = value.split('-');
  return `${d}/${m}/${y}`;
}

function formatDmyParts(day, month, year, { trailingSlash }) {
  if (!month && !year) {
    if (trailingSlash && day.length === 2) return `${day}/`;
    return day;
  }
  if (!year) {
    if (trailingSlash && month.length === 2) return `${day}/${month}/`;
    return `${day}/${month}`;
  }
  return `${day}/${month}/${year}`;
}

/**
 * Guide typing into DD/MM/YYYY. Clamps day to 01–31 and month to 01–12 so
 * values like 55/13/2026 cannot stay in the field.
 * Pass the previous field value so Backspace can remove slashes instead of
 * having them immediately re-inserted.
 */
export function constrainDmyInput(raw, previous = '') {
  const digits = String(raw || '').replace(/\D/g, '').slice(0, 8);
  if (!digits) return '';

  const deleting = String(raw || '').length < String(previous || '').length;

  let day = digits.slice(0, 2);
  let month = digits.slice(2, 4);
  let year = digits.slice(4, 8);

  if (!deleting && day.length === 1 && Number(day) > 3) {
    return constrainDmyInput(`0${digits}`, previous);
  }
  if (day.length === 2) {
    const n = Number(day);
    if (n > 31) day = '31';
    else if (!deleting && n === 0) day = '01';
  }

  if (!deleting && month.length === 1 && Number(month) > 1) {
    month = `0${month}`;
    year = digits.slice(3, 7);
  }
  if (month.length === 2) {
    const n = Number(month);
    if (n > 12) month = '12';
    else if (!deleting && n === 0) month = '01';
  }

  return formatDmyParts(day, month, year, { trailingSlash: !deleting });
}

/**
 * @returns {{ iso: string, error: string }}
 */
export function parseUserDate(raw) {
  const trimmed = String(raw || '').trim();
  if (!trimmed) return { iso: '', error: '' };

  const match = trimmed.match(DMY_DATE_RE);
  if (!match) {
    return { iso: '', error: 'Enter the full date as DD/MM/YYYY.' };
  }

  const d = Number(match[1]);
  const m = Number(match[2]);
  const y = Number(match[3]);
  const { minYear, maxYear } = isoYearBounds();

  if (!Number.isInteger(m) || m < 1 || m > 12) {
    return { iso: '', error: 'Month must be between 01 and 12.' };
  }
  if (!Number.isInteger(d) || d < 1) {
    return { iso: '', error: 'Day must be between 01 and 31.' };
  }
  const maxDay = daysInMonth(y, m);
  if (d > maxDay) {
    if (d > 31) return { iso: '', error: 'Day must be between 01 and 31.' };
    return { iso: '', error: `That month only has ${maxDay} days.` };
  }
  if (y < minYear) {
    return { iso: '', error: `Year must be ${minYear} or later.` };
  }
  if (y > maxYear) {
    return { iso: '', error: `Year cannot be after ${maxYear}.` };
  }

  const iso = `${y}-${pad2(m)}-${pad2(d)}`;
  if (iso > todayIsoDate()) {
    return { iso: '', error: 'Date cannot be after today.' };
  }
  return { iso, error: '' };
}

export function dmyToIso(dmy) {
  return parseUserDate(dmy).iso;
}

/** Accept ISO or DD/MM/YYYY; return ISO or ''. */
export function normalizeIsoDate(value) {
  const raw = String(value || '').trim();
  if (!raw) return '';
  if (isIsoDateInRange(raw)) return raw;
  return parseUserDate(raw).iso;
}

export function rangeDateError(dateFromIso, dateToIso) {
  if (dateFromIso && dateToIso && dateFromIso > dateToIso) {
    return 'From date cannot be after To date.';
  }
  return '';
}
