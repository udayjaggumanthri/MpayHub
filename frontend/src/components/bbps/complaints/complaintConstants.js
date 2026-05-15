/** Official disposition labels per BillAvenue BBPS complaint API (must match provider list). */
export const COMPLAINT_DISPOSITIONS = [
  'Transaction Successful, Amount Debited but services not received',
  'Transaction Successful, Amount Debited but Service Disconnected or Service Stopped',
  'Transaction Successful, Amount Debited but Late Payment Surcharge Charges add in next bill',
  'Erroneously paid in wrong account',
  'Duplicate Payment',
  'Erroneously paid the wrong amount',
  'Payment information not received from Biller or Delay in receiving payment information from the Biller.',
  // viii) BillAvenue XML sample uses this exact line (no trailing period).
  'Bill Paid but Amount not adjusted or still showing due amount',
];

export const COMPLAINT_TYPES = [{ value: 'Transaction', label: 'Transaction' }];
