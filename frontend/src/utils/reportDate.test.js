import {
  constrainDmyInput,
  dmyToIso,
  isoToDmy,
  isIsoDateInRange,
  normalizeIsoDate,
  parseUserDate,
  rangeDateError,
} from './reportDate';

describe('reportDate', () => {
  test('converts ISO to DD/MM/YYYY', () => {
    expect(isoToDmy('2026-08-14')).toBe('14/08/2026');
  });

  test('parses DD/MM/YYYY to ISO', () => {
    expect(dmyToIso('14/08/2026')).toBe('2026-08-14');
    expect(dmyToIso('4/8/2026')).toBe('2026-08-04');
  });

  test('rejects invalid years like 0002 with a year message', () => {
    expect(isIsoDateInRange('0002-08-11')).toBe(false);
    expect(parseUserDate('11/08/0002').iso).toBe('');
    expect(parseUserDate('11/08/0002').error).toMatch(/2000 or later/i);
  });

  test('rejects incomplete or impossible dates with specific messages', () => {
    expect(parseUserDate('14/08').error).toMatch(/DD\/MM\/YYYY/);
    expect(parseUserDate('32/01/2026').error).toMatch(/Day must be between/i);
    expect(parseUserDate('15/13/2026').error).toMatch(/Month must be between/i);
    expect(parseUserDate('31/02/2026').error).toMatch(/only has/);
    expect(normalizeIsoDate('')).toBe('');
  });

  test('rejects future years without calling them a format error', () => {
    expect(isIsoDateInRange('2028-01-12')).toBe(false);
    expect(parseUserDate('12/01/2028').error).toMatch(/cannot be after 2026/i);
    expect(normalizeIsoDate('2028-01-12')).toBe('');
  });

  test('clamps impossible day and month while typing', () => {
    expect(constrainDmyInput('55')).toBe('31/');
    expect(constrainDmyInput('55/13/2026')).toBe('31/12/2026');
    expect(constrainDmyInput('5')).toBe('05/');
  });

  test('backspace can delete past auto-inserted slashes', () => {
    expect(constrainDmyInput('19/08', '19/08/')).toBe('19/08');
    expect(constrainDmyInput('19', '19/')).toBe('19');
    expect(constrainDmyInput('19/08/202', '19/08/2026')).toBe('19/08/202');
    expect(constrainDmyInput('', '1')).toBe('');
  });

  test('from date cannot be after to date', () => {
    expect(rangeDateError('2026-08-20', '2026-08-01')).toMatch(/cannot be after/i);
    expect(rangeDateError('2026-08-01', '2026-08-20')).toBe('');
  });
});
