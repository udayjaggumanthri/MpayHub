/** Inclusive GST split + line shares + coupons (mirrors Partner backend). */

function money(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return 0;
  return Math.round((n + Number.EPSILON) * 100) / 100;
}

const BELOW = [
  '', 'One', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten',
  'Eleven', 'Twelve', 'Thirteen', 'Fourteen', 'Fifteen', 'Sixteen', 'Seventeen', 'Eighteen', 'Nineteen',
];
const TENS = ['', '', 'Twenty', 'Thirty', 'Forty', 'Fifty', 'Sixty', 'Seventy', 'Eighty', 'Ninety'];

function twoDigits(value) {
  if (value < 20) return BELOW[value];
  const ten = Math.floor(value / 10);
  const one = value % 10;
  return one === 0 ? TENS[ten] : `${TENS[ten]} ${BELOW[one]}`;
}

function indianGroup(value) {
  if (value === 0) return '';
  const hundred = Math.floor(value / 100);
  const rest = value % 100;
  const parts = [];
  if (hundred) parts.push(`${BELOW[hundred]} Hundred`);
  if (rest) parts.push(twoDigits(rest));
  return parts.join(' ');
}

export function amountInWords(amount) {
  const total = money(amount);
  const rupees = Math.floor(total);
  const paise = Math.round((total - rupees) * 100);
  if (rupees === 0 && paise === 0) return 'Zero Rupees Only';
  let rest = rupees;
  const crore = Math.floor(rest / 10000000);
  rest %= 10000000;
  const lakh = Math.floor(rest / 100000);
  rest %= 100000;
  const thousand = Math.floor(rest / 1000);
  rest %= 1000;
  const parts = [];
  if (crore) parts.push(`${indianGroup(crore)} Crore`);
  if (lakh) parts.push(`${indianGroup(lakh)} Lakh`);
  if (thousand) parts.push(`${indianGroup(thousand)} Thousand`);
  if (rest) parts.push(indianGroup(rest));
  const words = parts.filter(Boolean).join(' ').trim() || 'Zero';
  if (paise) return `${words} Rupees and ${twoDigits(paise)} Paise Only`;
  return `${words} Rupees Only`;
}

export function taxBreakdown(total, gstRatePercent) {
  const paid = money(total);
  const rate = Number(gstRatePercent) || 0;
  if (rate <= 0) {
    return { taxable: paid, cgst: 0, sgst: 0, roundOff: 0, total: paid, cgstRate: 0, sgstRate: 0 };
  }
  const taxable = money(paid / (1 + rate / 100));
  const gst = money(paid - taxable);
  const cgst = money(gst / 2);
  const sgst = money(gst - cgst);
  const half = money(rate / 2);
  return { taxable, cgst, sgst, roundOff: 0, total: paid, cgstRate: half, sgstRate: half };
}

function lineListAmount(row) {
  if (row.listAmount != null && String(row.listAmount).trim() !== '') {
    return money(row.listAmount);
  }
  const qty = Math.max(parseInt(row.quantity, 10) || 1, 1);
  const unit = money(row.price || 0);
  if (unit <= 0 && row.amount != null) return money(row.amount);
  return money(unit * qty);
}

function lineShares(lines, taxable) {
  const weights = lines.map((row) => lineListAmount(row));
  const gross = weights.reduce((a, b) => a + b, 0);
  let allocated = 0;
  return lines.map((row, index) => {
    const qty = Math.max(parseInt(row.quantity, 10) || 1, 1);
    const title = String(row.title || '').trim() || `Item ${index + 1}`;
    const listAmount = weights[index];
    let amount;
    if (index === lines.length - 1) {
      amount = money(taxable - allocated);
    } else if (gross > 0) {
      amount = money((taxable * listAmount) / gross);
      allocated = money(allocated + amount);
    } else {
      amount = 0;
    }
    const unit = qty ? money(amount / qty) : amount;
    return {
      title,
      quantity: qty,
      price: String(unit),
      amount: String(amount),
      listAmount: String(listAmount),
    };
  });
}

function normalizeCoupons(raw) {
  return (Array.isArray(raw) ? raw : [])
    .map((row, index) => {
      const name = String(row?.name || row?.title || '').trim();
      const amount = money(row?.amount || 0);
      if (!name && amount <= 0) return null;
      return { name: name || `Coupon ${index + 1}`, amount: String(amount) };
    })
    .filter(Boolean);
}

export function recomputeInvoice(invoice) {
  const data = { ...(invoice || {}) };
  const company = { ...(data.company || {}) };
  const customer = { ...(data.customer || {}) };
  let linesIn = Array.isArray(data.lines) && data.lines.length
    ? data.lines.map((row) => ({ ...row }))
    : [{ title: data.courseTitle || 'Pay In', quantity: 1, price: data.transactionAmount || data.total || '0' }];

  const coupons = normalizeCoupons(data.coupons);
  const linesGross = money(linesIn.reduce((sum, row) => sum + lineListAmount(row), 0));
  const couponTotal = money(coupons.reduce((sum, row) => sum + money(row.amount), 0));
  let total = money(linesGross - couponTotal);
  if (total < 0) total = 0;

  const breakdown = taxBreakdown(total, company.gstRatePercent ?? 18);
  const lines = lineShares(linesIn, breakdown.taxable);
  const quantity = lines.reduce((sum, row) => sum + row.quantity, 0) || lines.length || 1;
  // Keep summary course title independent from purchased line-item names.
  const courseTitle = String(data.courseTitle || '').trim();
  const transactionAmount = money(data.transactionAmount || total);

  return {
    ...data,
    company,
    customer: {
      name: String(customer.name || '').trim(),
      email: String(customer.email || '').trim(),
      phone: String(customer.phone || '').trim(),
      address: String(customer.address || '').trim(),
    },
    courseTitle,
    paymentMethod: String(data.paymentMethod || 'Online').trim() || 'Online',
    lines,
    coupons,
    linesGross: String(linesGross),
    couponTotal: String(couponTotal),
    quantity,
    taxable: String(breakdown.taxable),
    cgstRate: String(breakdown.cgstRate),
    cgst: String(breakdown.cgst),
    sgstRate: String(breakdown.sgstRate),
    sgst: String(breakdown.sgst),
    roundOff: String(breakdown.roundOff),
    total: String(breakdown.total),
    amountInWords: amountInWords(breakdown.total),
    transactionId: String(data.transactionId || '').trim(),
    rrn: String(data.rrn || '').trim(),
    utr: String(data.utr || '').trim(),
    gatewayTransactionId: String(data.gatewayTransactionId || '').trim(),
    providerOrderId: String(data.providerOrderId || '').trim(),
    transactionAmount: String(transactionAmount),
    amountMatchesTransaction: money(breakdown.total) === transactionAmount,
  };
}
