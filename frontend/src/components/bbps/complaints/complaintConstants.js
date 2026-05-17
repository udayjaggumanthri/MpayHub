/**
 * Official BillAvenue / NPCI complaint disposition strings (must match provider list exactly).
 * Display order and labels align with Bharat Connect complaint registration requirements.
 */
/** `code` is an internal key only; UI shows `value` without roman numerals. */
export const COMPLAINT_DISPOSITION_OPTIONS = [
  {
    code: 'i',
    value: 'Transaction Successful, Amount Debited but services not received',
  },
  {
    code: 'ii',
    value: 'Transaction Successful, Amount Debited but Service Disconnected or Service Stopped',
  },
  {
    code: 'iii',
    value: 'Transaction Successful, Amount Debited but Late Payment Surcharge Charges add in next bill',
  },
  {
    code: 'iv',
    value: 'Erroneously paid in wrong account',
  },
  {
    code: 'v',
    value: 'Duplicate Payment',
  },
  {
    code: 'vi',
    value: 'Erroneously paid the wrong amount',
  },
  {
    code: 'vii',
    value:
      'Payment information not received from Biller or Delay in receiving payment information from the Biller.',
  },
  {
    code: 'viii',
    value: 'Bill Paid but Amount not adjusted or still showing due amount',
  },
];

/** Plain string list (API payload values) — kept for compatibility. */
export const COMPLAINT_DISPOSITIONS = COMPLAINT_DISPOSITION_OPTIONS.map((o) => o.value);

export const COMPLAINT_TYPES = [{ value: 'Transaction', label: 'Transaction' }];
