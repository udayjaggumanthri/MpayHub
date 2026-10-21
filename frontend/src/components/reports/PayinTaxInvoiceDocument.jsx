import React from 'react';
import { normalizeAssetUrl } from '../../utils/mediaUrl';

function inr(value) {
  const amount = Number(value);
  if (Number.isNaN(amount)) return '0.00';
  return amount.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function rateLabel(value) {
  const amount = Number(value);
  if (Number.isNaN(amount)) return value;
  return Number.isInteger(amount) ? String(amount) : String(amount);
}

/**
 * LMS-style A4 tax invoice preview (Prajnadhara layout).
 */
const PayinTaxInvoiceDocument = ({ invoice }) => {
  if (!invoice) return null;
  const company = invoice.company || {};
  const customer = invoice.customer || {};
  const lines = Array.isArray(invoice.lines) ? invoice.lines : [];
  const coupons = Array.isArray(invoice.coupons) ? invoice.coupons : [];
  const signature = normalizeAssetUrl(company.signatureUrl);
  const stamp = normalizeAssetUrl(company.stampUrl);
  const contact = [company.phone, company.email].filter(Boolean).join(' | ');
  const band = '#d9ebfb';
  const line = '#b7d4f2';
  const rrn = invoice.rrn || invoice.utr || '';

  return (
    <article
      className="tax-invoice-sheet mx-auto flex w-full max-w-[190mm] flex-col bg-white px-1 text-[13px] leading-5 text-slate-900"
      style={{ fontFamily: '"Segoe UI", Calibri, "Plus Jakarta Sans", sans-serif', minHeight: '270mm' }}
    >
      <div className="text-center">
        <div className="flex items-end justify-center gap-2">
          <div style={{ fontFamily: 'Nunito, Outfit, sans-serif', fontWeight: 800, fontSize: '42px', lineHeight: 1, color: '#1d4ed8' }}>
            {company.legalName || 'Prajnadhara'}
          </div>
          <div className="pb-1 text-[15px] font-semibold" style={{ color: '#3b82f6' }}>{company.companyLine}</div>
        </div>
        {company.address ? (
          <p className="mx-auto mt-1 max-w-[165mm] text-[12px] leading-4 text-slate-800">{company.address}</p>
        ) : null}
        {contact ? <p className="text-[12px] text-slate-800">{contact}</p> : null}
        <div className="mt-1 text-[16px] font-bold text-slate-900">Tax Invoice</div>
        <div className="mt-1 flex items-start justify-between text-[13px]">
          <div className="text-left">
            <div>Invoice No: {invoice.invoiceNumber || '—'}</div>
            {company.gstNumber ? <div>GST No : {company.gstNumber}</div> : null}
            {invoice.transactionId ? <div>Txn ID : {invoice.transactionId}</div> : null}
            {rrn ? <div>RRN : {rrn}</div> : null}
          </div>
          <div>Date: {invoice.date}</div>
        </div>
      </div>

      <section className="mt-4 grid grid-cols-2 gap-6 text-sm">
        <div>
          <h3 className="font-bold">Customer Details</h3>
          <p><span className="font-semibold">Name :</span> {customer.name || '—'}</p>
          <p><span className="font-semibold">Mail ID :</span> {customer.email || '—'}</p>
          <p><span className="font-semibold">Contact No :</span> {customer.phone || '—'}</p>
          <p><span className="font-semibold">Address :</span> {customer.address || ''}</p>
        </div>
        <div>
          <p><span className="font-semibold">Course :</span> {invoice.courseTitle || '—'}</p>
          <p className="mt-3"><span className="font-semibold">Payment method:</span> {invoice.paymentMethod || 'Online'}</p>
        </div>
      </section>

      <div className="mt-3 text-[13px] font-bold">Txn Details — Purchased courses</div>
      <table className="mt-1 w-full border-collapse text-[13px]">
        <thead>
          <tr style={{ background: band }}>
            <th className="px-2 py-1 text-center font-semibold" style={{ border: `1px solid ${line}` }}>Purchased Course</th>
            <th className="px-2 py-1 text-center font-semibold" style={{ border: `1px solid ${line}` }}>Quantity</th>
            <th className="px-2 py-1 text-center font-semibold" style={{ border: `1px solid ${line}` }}>Price (₹)</th>
            <th className="px-2 py-1 text-center font-semibold" style={{ border: `1px solid ${line}` }}>Amount (₹)</th>
          </tr>
        </thead>
        <tbody>
          {lines.map((row, index) => (
            <tr key={`${row.title}-${index}`}>
              <td className="px-2 py-1" style={{ border: `1px solid ${line}` }}>{index + 1}.{row.title}</td>
              <td className="px-2 py-1 text-center" style={{ border: `1px solid ${line}` }}>{row.quantity}</td>
              <td className="px-2 py-1 text-center tabular-nums" style={{ border: `1px solid ${line}` }}>{inr(row.price)}</td>
              <td className="px-2 py-1 text-center tabular-nums" style={{ border: `1px solid ${line}` }}>{inr(row.amount)}</td>
            </tr>
          ))}
          <tr className="font-semibold" style={{ background: band }}>
            <td className="px-2 py-1 text-center" style={{ border: `1px solid ${line}` }}>Total</td>
            <td className="px-2 py-1 text-center" style={{ border: `1px solid ${line}` }}>{invoice.quantity}</td>
            <td style={{ border: `1px solid ${line}` }} />
            <td className="px-2 py-1 text-center tabular-nums" style={{ border: `1px solid ${line}` }}>{inr(invoice.taxable)}</td>
          </tr>
        </tbody>
      </table>

      <table className="mt-3 w-full border-collapse text-[13px]">
        <tbody>
          {[
            ['Lines gross (incl. GST)', `₹${inr(invoice.linesGross || invoice.total)}`, false],
            ...coupons.map((coupon) => [`Coupon: ${coupon.name}`, `-₹${inr(coupon.amount)}`, false]),
            ['Sub Total (Taxable Value)', `₹${inr(invoice.taxable)}`, false],
            [`CGST(${rateLabel(invoice.cgstRate)}%)`, `₹${inr(invoice.cgst)}`, true],
            [`SGST(${rateLabel(invoice.sgstRate)}%)`, `₹${inr(invoice.sgst)}`, true],
            ['Round Off', `₹${inr(invoice.roundOff)}`, false],
            ['Total', `₹${inr(invoice.total)}`, true],
          ].map(([label, value, shaded], index) => (
            <tr key={`${label}-${index}`} className={label === 'Total' ? 'font-bold' : undefined} style={{ background: shaded ? band : '#fff' }}>
              <td className="w-[68%] px-2 py-1" style={{ border: '1px solid #d7d7d7' }}>{label}</td>
              <td className="px-2 py-1 text-right tabular-nums" style={{ border: '1px solid #d7d7d7' }}>{value}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 px-3 py-2 text-[13px]" style={{ border: '1px solid #7eb6ea' }}>
        <p className="font-semibold">Total Amount in Words:</p>
        <p>{invoice.amountInWords}</p>
      </div>

      <div className="mt-4 text-sm">
        <p className="font-bold">Declaration :</p>
        <p className="mt-1 max-w-xl leading-5">{company.declaration}</p>
      </div>

      <div className="mt-6 flex justify-end">
        <div className="w-64 text-center text-sm">
          <p className="font-semibold">For {company.fullName || `${company.legalName || ''} ${company.companyLine || ''}`.trim()}</p>
          <div className="relative mx-auto mt-2 h-24 w-56">
            {stamp ? (
              <img src={stamp} alt="" className="absolute bottom-1 right-2 h-20 w-20 bg-transparent object-contain" />
            ) : null}
            {signature ? (
              <img src={signature} alt="" className="absolute bottom-0 left-6 h-16 max-w-[9rem] bg-transparent object-contain" />
            ) : null}
          </div>
          <div className="mx-auto w-44 border-t border-slate-800" />
          <p className="mt-1">Authorized Signatory</p>
        </div>
      </div>

      <div className="invoice-foot relative mt-auto overflow-hidden pt-6">
        <svg className="block h-28 w-full" viewBox="0 0 1200 160" preserveAspectRatio="none" aria-hidden="true">
          <path fill="#e8f4fc" d="M0 70 C180 130 320 20 520 64 C740 112 900 24 1200 78 L1200 160 L0 160 Z" />
          <path fill="#d4ebf8" d="M0 100 C220 150 420 55 680 96 C880 128 1040 70 1200 108 L1200 160 L0 160 Z" />
          <path fill="#c5e4f6" d="M0 128 C260 150 480 100 760 132 C960 150 1080 120 1200 136 L1200 160 L0 160 Z" />
        </svg>
        <p className="absolute inset-x-0 bottom-6 text-center text-[12px] text-slate-700">
          Thank you for choosing {company.fullName || company.legalName || 'Prajnadhara'}
        </p>
      </div>
      <p className="mt-2 text-left text-[13px] font-bold text-slate-900">Note: This is Digitally Signed Invoice</p>
    </article>
  );
};

export default PayinTaxInvoiceDocument;
