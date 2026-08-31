import { getMpayhubLogoSrc, buildPayinReceiptPrintContext } from './payinReceiptFields';

const escapeHtml = (value) =>
  String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

export const buildPayinReceiptPrintHtml = (txn, { mobile = false } = {}) => {
  const ctx = buildPayinReceiptPrintContext(txn);
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  const pagePad = mobile ? '16px' : '28px 32px';
  const statusClass = ctx.paymentStatusSuccess ? 'status-paid' : 'status-other';

  const gridRows = (ctx.rows || [])
    .map(
      (row) => `
        <div class="field">
          <div class="field-label">${escapeHtml(row.label)}</div>
          <div class="field-value">${escapeHtml(row.value)}</div>
        </div>
      `
    )
    .join('');

  const proofBlock =
    txn.hasProofImage && txn.proofReceiptUrl
      ? `
        <div class="proof">
          <div class="field-label">Payment proof (uploaded)</div>
          <img class="proof-img" src="${escapeHtml(txn.proofReceiptUrl)}" alt="Payment proof" />
        </div>
      `
      : '';

  return `
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>Pay-in Receipt - ${escapeHtml(ctx.transactionId)}</title>
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
          .receipt { max-width: ${mobile ? '100%' : '760px'}; margin: 0 auto; }
          .brand-row { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 18px; }
          .logo { height: 44px; width: auto; max-width: 180px; object-fit: contain; }
          .doc-title { margin: 0 0 6px; font-size: 26px; font-weight: 700; color: #1d4ed8; }
          .doc-meta { margin: 0 0 18px; font-size: 13px; color: #6b7280; line-height: 1.6; }
          .status-badge {
            display: inline-block;
            padding: 6px 16px;
            border-radius: 999px;
            font-size: 12px;
            font-weight: 700;
            margin-bottom: 18px;
          }
          .status-paid { background: #dcfce7; color: #166534; border: 1px solid #86efac; }
          .status-other { background: #fef3c7; color: #92400e; border: 1px solid #fcd34d; }
          .grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 0;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 16px;
          }
          @media (max-width: 560px) { .grid { grid-template-columns: 1fr; } }
          .field { border-bottom: 1px solid #e5e7eb; padding: 10px 12px; min-height: 52px; }
          .field-label { font-size: 11px; color: #6b7280; margin-bottom: 4px; }
          .field-value { font-size: 13px; font-weight: 600; color: #111827; word-break: break-word; }
          .summary {
            margin-bottom: 16px;
            padding: 12px 14px;
            background: #eff6ff;
            border: 1px solid #bfdbfe;
            border-radius: 8px;
            font-size: 13px;
            line-height: 1.55;
          }
          .proof { margin-bottom: 16px; }
          .proof-img { max-height: 280px; max-width: 100%; border: 1px solid #d1d5db; border-radius: 8px; }
          .footer { margin-top: 18px; text-align: center; font-size: 12px; color: #9ca3af; }
          @media print { body { padding: 12mm; } .receipt { max-width: 100%; } }
        </style>
      </head>
      <body>
        <div class="receipt">
          <div class="brand-row">
            <img class="logo" src="${origin}${getMpayhubLogoSrc()}" alt="mPayHub" />
            <div style="text-align:right;font-size:12px;color:#6b7280;">
              <div style="font-weight:600;color:#374151;">Pay-in Receipt</div>
              <div>${escapeHtml(txn.railTypeLabel || 'Wallet Top-up')}</div>
            </div>
          </div>
          <h1 class="doc-title">Pay-in Receipt</h1>
          <p class="doc-meta">
            <strong>Date:</strong> ${escapeHtml(ctx.receiptDate)}<br />
            <strong>Receipt No:</strong> ${escapeHtml(ctx.receiptNo)}
          </p>
          <div style="text-align:center;">
            <span class="status-badge ${statusClass}">${escapeHtml(ctx.paymentStatus)}</span>
          </div>
          <div class="grid">${gridRows}</div>
          ${proofBlock}
          ${ctx.summary ? `<div class="summary">${escapeHtml(ctx.summary)}</div>` : ''}
          <p class="footer">This is a system-generated receipt. No signature is required.</p>
        </div>
      </body>
    </html>
  `;
};

export const openPayinReceiptPrint = (html, { mobile = false } = {}) => {
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
