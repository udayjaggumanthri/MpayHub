/**
 * Inclusive local-date ranges for report summary period toggles.
 * Periods: day (default) | week | month | 2months | year
 */

function isoDate(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function localTodayNoon() {
  const d = new Date();
  d.setHours(12, 0, 0, 0);
  return d;
}

export const REPORT_PERIODS = ['day', 'week', 'month', '2months', 'year'];

export const REPORT_PERIOD_LABELS = {
  day: 'Day',
  week: 'Week',
  month: 'Month',
  '2months': '2 months',
  year: 'Year',
};

export const REPORT_PERIOD_SUBTITLES = {
  day: 'Today',
  week: 'Last 7 days',
  month: 'This month',
  '2months': 'Last 2 months',
  year: 'This year',
};

/**
 * @param {'day'|'week'|'month'|'2months'|'year'} period
 * @returns {{ date_from: string, date_to: string }}
 */
export function reportPeriodDateRange(period) {
  const today = localTodayNoon();
  const to = isoDate(today);
  const p = REPORT_PERIODS.includes(period) ? period : 'day';

  if (p === 'week') {
    const from = new Date(today);
    from.setDate(from.getDate() - 6);
    return { date_from: isoDate(from), date_to: to };
  }
  if (p === 'month') {
    const from = new Date(today.getFullYear(), today.getMonth(), 1);
    return { date_from: isoDate(from), date_to: to };
  }
  if (p === '2months') {
    const from = new Date(today.getFullYear(), today.getMonth() - 1, 1);
    return { date_from: isoDate(from), date_to: to };
  }
  if (p === 'year') {
    const from = new Date(today.getFullYear(), 0, 1);
    return { date_from: isoDate(from), date_to: to };
  }
  return { date_from: to, date_to: to };
}

/** Convenience for filter state objects using dateFrom / dateTo. */
export function reportPeriodFilterDates(period) {
  const r = reportPeriodDateRange(period);
  return { dateFrom: r.date_from, dateTo: r.date_to };
}
