import { balanceFromRow, formatReportBalance } from './reportBalanceDisplay';

describe('reportBalanceDisplay', () => {
  test('formatReportBalance shows em dash when empty', () => {
    expect(formatReportBalance('')).toBe('—');
    expect(formatReportBalance(null)).toBe('—');
  });

  test('formatReportBalance formats numeric strings', () => {
    expect(formatReportBalance('100.50')).toContain('100.50');
  });

  test('balanceFromRow normalizes snake and camel case', () => {
    expect(balanceFromRow({ opening_balance: '10', closing_balance: '20' })).toEqual({
      opening: '10',
      closing: '20',
    });
    expect(balanceFromRow({ openingBalance: '1', closingBalance: '2' })).toEqual({
      opening: '1',
      closing: '2',
    });
  });
});
