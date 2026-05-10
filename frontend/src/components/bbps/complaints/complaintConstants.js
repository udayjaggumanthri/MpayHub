/** Reference-aligned disposition labels (BillAvenue accepts free text; keep stable for duplicate detection). */
export const COMPLAINT_DISPOSITIONS = [
  'Transaction successful, Amount Debited but services not received',
  'Transaction successful, Amount Debited but service disconnected or stopped',
  'Transaction successful, Amount Debited but Late Payment Surcharge Charges added',
  'Erroneously paid in wrong account',
  'Duplicate Payment',
  'Erroneously paid wrong amount',
  'Payment info not received / delayed from biller',
  'Bill Paid but still showing due amount',
];

export const COMPLAINT_TYPES = [{ value: 'Transaction', label: 'Transaction' }];
