import { bbpsLogoAssets } from './bbpsLogoAssets';
import { BBPS_B_ASSURED_LOGO } from './bbpsLogoSizes';
import { MPAYHUB_LOGO_SRC, buildBbpsReceiptPrintContext } from './bbpsReceiptFields';

const escapeHtml = (value) =>
  String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

export const buildBbpsReceiptPrintHtml = (txn, identity, { mobile = false } = {}) => {
  const ctx = buildBbpsReceiptPrintContext(txn, identity);
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  const pagePad = mobile ? '16px' : '28px 32px';
  const statusClass = ctx.paymentStatusSuccess ? 'status-paid' : 'status-other';

  return `
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>Payment Receipt - ${escapeHtml(ctx.bConnectTxnId)}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          * { box-sizing: border-box; }
          body {
            font-family: 'Segoe UI', Arial, Helvetica, sans-serif;
            margin: 0;
            padding: ${pagePad};
            color: #1f2937;
            background: #fff;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          .receipt {
            max-width: ${mobile ? '100%' : '720px'};
            margin: 0 auto;
          }
          .brand-row {
            display: flex;
            flex-wrap: wrap;
            align-items: flex-start;
            justify-content: space-between;
            gap: 16px;
            margin-bottom: 20px;
          }
          .logo-mpay {
            height: 44px;
            width: auto;
            max-width: 180px;
            object-fit: contain;
            object-position: left center;
          }
          .logo-frame-b-assured {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: ${BBPS_B_ASSURED_LOGO.width}px;
            height: ${BBPS_B_ASSURED_LOGO.height}px;
            min-width: ${BBPS_B_ASSURED_LOGO.width}px;
            min-height: ${BBPS_B_ASSURED_LOGO.height}px;
            max-width: ${BBPS_B_ASSURED_LOGO.width}px;
            max-height: ${BBPS_B_ASSURED_LOGO.height}px;
            background: transparent;
            flex-shrink: 0;
            overflow: hidden;
            box-sizing: border-box;
            isolation: isolate;
            position: relative;
            z-index: 2;
            padding: 0;
            margin: 0;
            line-height: 0;
          }
          .logo-b-assured {
            width: 100%;
            height: 100%;
            object-fit: contain;
            object-position: center;
            display: block;
          }
          .doc-title {
            margin: 0 0 6px;
            font-size: 28px;
            font-weight: 700;
            color: #1d4ed8;
            letter-spacing: -0.02em;
          }
          .doc-meta {
            margin: 0 0 22px;
            font-size: 13px;
            color: #6b7280;
            line-height: 1.6;
          }
          .doc-meta strong { color: #374151; font-weight: 600; }
          .cards {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 14px;
            margin-bottom: 14px;
          }
          @media (max-width: 560px) {
            .cards { grid-template-columns: 1fr; }
          }
          .card {
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 14px 16px;
            background: #fafafa;
          }
          .card-label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            color: #9ca3af;
            margin-bottom: 8px;
          }
          .customer-name {
            font-size: 20px;
            font-weight: 700;
            color: #111827;
            margin: 0 0 10px;
            line-height: 1.25;
            word-break: break-word;
          }
          .card-line {
            font-size: 13px;
            color: #4b5563;
            margin: 0 0 4px;
            line-height: 1.5;
          }
          .card-line strong { color: #374151; font-weight: 600; }
          .status-badge {
            display: inline-block;
            padding: 4px 14px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 10px;
          }
          .status-paid {
            background: #dcfce7;
            color: #166534;
            border: 1px solid #86efac;
          }
          .status-other {
            background: #fef3c7;
            color: #92400e;
            border: 1px solid #fcd34d;
          }
          .reference-card {
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 14px 16px;
            background: #fafafa;
            margin-bottom: 18px;
          }
          .reference-card .card-label { margin-bottom: 6px; }
          .reference-id {
            font-size: 14px;
            font-weight: 700;
            color: #111827;
            font-family: ui-monospace, 'Cascadia Code', Menlo, Consolas, monospace;
            word-break: break-all;
          }
          .amount-table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 0;
            font-size: 13px;
          }
          .amount-table thead th {
            text-align: left;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: #9ca3af;
            padding: 0 8px 10px 0;
            border-bottom: 1px solid #e5e7eb;
          }
          .amount-table thead th.num { text-align: right; padding-right: 0; }
          .amount-table tbody td {
            padding: 12px 8px 12px 0;
            vertical-align: top;
            color: #374151;
            border-bottom: 1px solid #f3f4f6;
          }
          .amount-table tbody td.num {
            text-align: right;
            padding-right: 0;
            white-space: nowrap;
            font-variant-numeric: tabular-nums;
          }
          .amount-table tbody td.biller {
            font-weight: 600;
            color: #111827;
            max-width: 220px;
            word-break: break-word;
          }
          .grand-total-row td {
            padding-top: 14px;
            border-top: 2px solid #e5e7eb;
            border-bottom: none;
            font-weight: 700;
            font-size: 14px;
            color: #111827;
          }
          .grand-total-row td.num { font-size: 15px; }
          .note-box {
            margin-top: 18px;
            padding: 12px 14px;
            background: #f9fafb;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            font-size: 12px;
            color: #6b7280;
            line-height: 1.55;
          }
          .thank-you {
            margin-top: 22px;
            text-align: center;
            font-size: 13px;
            color: #9ca3af;
          }
          @media print {
            body { padding: 12mm; }
            .receipt { max-width: 100%; }
          }
        </style>
      </head>
      <body>
        <div class="receipt">
          <div class="brand-row">
            <img class="logo-mpay" src="${origin}${MPAYHUB_LOGO_SRC}" alt="mPayHub" />
            <span class="logo-frame-b-assured">
              <img class="logo-b-assured" src="${origin}${bbpsLogoAssets.bAssuredPrimary}" alt="B Assured" width="${BBPS_B_ASSURED_LOGO.width}" height="${BBPS_B_ASSURED_LOGO.height}" />
            </span>
          </div>

          <h1 class="doc-title">Payment Receipt</h1>
          <p class="doc-meta">
            <strong>Date:</strong> ${escapeHtml(ctx.receiptDate)}<br />
            <strong>Receipt No:</strong> #${escapeHtml(ctx.receiptNo)}
          </p>

          <div class="cards">
            <div class="card">
              <div class="card-label">Customer</div>
              <p class="customer-name">${escapeHtml(ctx.customerName)}</p>
              <p class="card-line"><strong>Mobile No:</strong> ${escapeHtml(ctx.mobileNo)}</p>
              <p class="card-line"><strong>${escapeHtml(ctx.billNumberLabel)}:</strong> ${escapeHtml(ctx.billNumber)}</p>
            </div>
            <div class="card">
              <div class="card-label">Payment</div>
              <span class="status-badge ${statusClass}">${escapeHtml(ctx.paymentStatus)}</span>
              <p class="card-line" style="margin-top:0"><strong>Payment Mode:</strong> ${escapeHtml(ctx.paymentMode)}</p>
            </div>
          </div>

          <div class="reference-card">
            <div class="card-label">Reference</div>
            <div class="reference-id">B-Connect TXN ID: ${escapeHtml(ctx.bConnectTxnId)}</div>
          </div>

          <table class="amount-table">
            <thead>
              <tr>
                <th>Biller</th>
                <th class="num">Bill Amount (INR)</th>
                <th class="num">CCF (INR)</th>
                <th class="num">Total Amount (INR)</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td class="biller">${escapeHtml(ctx.billerName)}</td>
                <td class="num">${escapeHtml(ctx.billAmount)}</td>
                <td class="num">${escapeHtml(ctx.ccfAmount)}</td>
                <td class="num">${escapeHtml(ctx.totalAmount)}</td>
              </tr>
              <tr class="grand-total-row">
                <td colspan="3">Grand Total</td>
                <td class="num">${escapeHtml(ctx.grandTotal)}</td>
              </tr>
            </tbody>
          </table>

          <div class="note-box">
            Note: This is a system-generated receipt from BBPS. No signature is required.
          </div>
          <p class="thank-you">Thank you for your payment.</p>
        </div>
      </body>
    </html>
  `;
};

export const openBbpsReceiptPrint = (html, { mobile = false } = {}) => {
  const script = `
    <script>
      window.addEventListener('load', function () {
        setTimeout(function () {
          try { window.focus(); window.print(); } catch (e) {}
        }, 350);
      });
    <\/script>
  `;
  const htmlWithPrint = html.includes('</body>') ? html.replace('</body>', `${script}</body>`) : `${html}${script}`;
  const features = mobile ? 'width=420,height=820' : 'width=820,height=900';
  const printWindow = window.open('about:blank', '_blank', features);

  if (!printWindow) {
    const iframe = document.createElement('iframe');
    iframe.style.cssText = 'position:fixed;right:0;bottom:0;width:0;height:0;border:0';
    document.body.appendChild(iframe);
    const doc = iframe.contentWindow?.document;
    if (!doc) return;
    doc.open();
    doc.write(htmlWithPrint);
    doc.close();
    setTimeout(() => {
      iframe.contentWindow?.focus();
      iframe.contentWindow?.print();
      setTimeout(() => document.body.removeChild(iframe), 800);
    }, 300);
    return;
  }

  try {
    const blob = new Blob([htmlWithPrint], { type: 'text/html;charset=utf-8' });
    const receiptUrl = URL.createObjectURL(blob);
    printWindow.location.replace(receiptUrl);
    window.setTimeout(() => URL.revokeObjectURL(receiptUrl), 120000);
  } catch {
    printWindow.document.open();
    printWindow.document.write(htmlWithPrint);
    printWindow.document.close();
  }
};
