import {
  buildAllModulesDrillDownUrl,
  buildModuleReportDrillDownUrl,
  parseDrillDownSearchParams,
  statusForReportApi,
  statusForReportFilter,
} from './dashboardDrillDown';

describe('dashboardDrillDown', () => {
  test('buildModuleReportDrillDownUrl encodes platform scope and dates', () => {
    const url = buildModuleReportDrillDownUrl({
      module: 'bbps',
      status: 'SUCCESS',
      dateFrom: '2026-06-01',
      dateTo: '2026-06-01',
    });
    expect(url).toContain('/reports/bbps?');
    expect(url).toContain('scope=platform');
    expect(url).toContain('from=dashboard');
    expect(url).toContain('date_from=2026-06-01');
    expect(url).toContain('status=SUCCESS');
  });

  test('buildAllModulesDrillDownUrl sets module=all', () => {
    const url = buildAllModulesDrillDownUrl({
      status: 'FAILED',
      dateFrom: '2026-06-01',
      dateTo: '2026-06-01',
    });
    expect(url).toContain('module=all');
    expect(url).toContain('status=FAILURE');
  });

  test('parseDrillDownSearchParams maps FAILURE filter', () => {
    const parsed = parseDrillDownSearchParams(
      'from=dashboard&scope=platform&status=FAILURE&date_from=2026-06-01&date_to=2026-06-01'
    );
    expect(parsed.fromDashboard).toBe(true);
    expect(parsed.scope).toBe('platform');
    expect(parsed.filters.status).toBe('FAILURE');
    expect(parsed.filters.dateFrom).toBe('2026-06-01');
  });

  test('status mapping for report API', () => {
    expect(statusForReportFilter('FAILED')).toBe('FAILURE');
    expect(statusForReportApi('FAILURE')).toBe('FAILED');
  });
});
