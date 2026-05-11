export const BBPS_CANONICAL_CATEGORIES = [
  { displayName: 'Agent Collection', primarySlug: 'agent-collection', slugAliases: [] },
  { displayName: 'Broadband Postpaid', primarySlug: 'broadband-postpaid', slugAliases: ['broadband'] },
  { displayName: 'Cable TV', primarySlug: 'cable-tv', slugAliases: ['cable'] },
  { displayName: 'Clubs and Associations', primarySlug: 'clubs-and-associations', slugAliases: ['clubs-associations'] },
  { displayName: 'Credit Card', primarySlug: 'credit-card', slugAliases: ['creditcard', 'credit-card-bill', 'cc'] },
  { displayName: 'DTH', primarySlug: 'dth', slugAliases: [] },
  { displayName: 'eChallan', primarySlug: 'echallan', slugAliases: ['e-challan'] },
  { displayName: 'Education Fees', primarySlug: 'education-fees', slugAliases: ['education'] },
  { displayName: 'Electricity', primarySlug: 'electricity', slugAliases: [] },
  { displayName: 'EV Recharge', primarySlug: 'ev-recharge', slugAliases: ['ev'] },
  { displayName: 'FASTag', primarySlug: 'fastag', slugAliases: ['fast-tag'] },
  { displayName: 'Fleet Card Recharge', primarySlug: 'fleet-card-recharge', slugAliases: ['fleet-card'] },
  { displayName: 'Gas', primarySlug: 'gas', slugAliases: [] },
  { displayName: 'Housing Society', primarySlug: 'housing-society', slugAliases: ['housing'] },
  { displayName: 'Insurance', primarySlug: 'insurance', slugAliases: [] },
  { displayName: 'Landline Postpaid', primarySlug: 'landline-postpaid', slugAliases: ['landline'] },
  { displayName: 'Loan Repayment', primarySlug: 'loan-repayment', slugAliases: ['loan-emi'] },
  { displayName: 'LPG Gas', primarySlug: 'lpg-gas', slugAliases: ['lpg'] },
  { displayName: 'Mobile Postpaid', primarySlug: 'mobile-postpaid', slugAliases: ['mobile-recharge', 'mobile'] },
  { displayName: 'Mobile Prepaid', primarySlug: 'mobile-prepaid', slugAliases: [] },
  { displayName: 'Municipal Services', primarySlug: 'municipal-services', slugAliases: ['municipal'] },
  { displayName: 'Municipal Taxes', primarySlug: 'municipal-taxes', slugAliases: ['municipal-tax'] },
  { displayName: 'National Pension System', primarySlug: 'national-pension-system', slugAliases: ['nps'] },
  { displayName: 'NCMC Recharge', primarySlug: 'ncmc-recharge', slugAliases: ['ncmc'] },
  { displayName: 'Prepaid Meter', primarySlug: 'prepaid-meter', slugAliases: ['prepaid'] },
  { displayName: 'Rental', primarySlug: 'rental', slugAliases: [] },
  { displayName: 'Subscription', primarySlug: 'subscription', slugAliases: ['subscriptions'] },
  { displayName: 'Water', primarySlug: 'water', slugAliases: [] },
];

export function normalizeCategorySlug(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[_\s]+/g, '-')
    .replace(/-+/g, '-');
}
