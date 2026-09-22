import { getMpayhubLogoSrc, buildAepsReceiptPrintContext } from './aepsReceiptFields';

const escapeHtml = (value) =>
  String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');

export const buildAepsReceiptPrintHtml = (txn, { mobile = false } = {}) => {
  const ctx = buildAepsReceiptPrintContext(txn);
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  const logoSrc = `${origin}${getMpayhubLogoSrc()}`;
  const pagePad = mobile ? '16px' : '28px 32px';
  const statusClass =
    ctx.statusTone === 'success' ? 'status-ok' : ctx.statusTone === 'danger' ? 'status-bad' : 'status-other';
  const statementHtml = (ctx.statementRows || []).length
    ? `
      <table class="stmt">
        <thead><tr><th>Date</th><th>Narration</th><th>Amount</th><th>Type</th></tr></thead>
        <tbody>
          ${ctx.statementRows
            .map(
              (r) => `<tr>
                <td>${escapeHtml(r.date || r.txnDate || '—')}</td>
                <td>${escapeHtml(r.narration || r.remarks || '—')}</td>
                <td>${escapeHtml(r.amount || r.txnAmount || '—')}</td>
                <td>${escapeHtml(r.txnType || r.type || '—')}</td>
              </tr>`
            )
            .join('')}
        </tbody>
      </table>`
    : '';

  return `
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <title>AEPS Receipt - ${escapeHtml(ctx.merchantTranId)}</title>
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
          .receipt { max-width: ${mobile ? '100%' : '720px'}; margin: 0 auto; }
          .brand-row {
            display: flex; align-items: center; justify-content: space-between;
            gap: 16px; margin-bottom: 18px;
          }
          .logo-mpay { height: 44px; width: auto; max-width: 180px; object-fit: contain; }
          .doc-title { margin: 0 0 4px; font-size: 26px; font-weight: 700; color: #1d4ed8; }
          .doc-meta { margin: 0 0 18px; font-size: 13px; color: #6b7280; }
          .status-badge {
            display: inline-block; padding: 6px 12px; border-radius: 999px;
            font-size: 12px; font-weight: 700; text-transform: uppercase;
          }
          .status-ok { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
          .status-bad { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
          .status-other { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
          .grid {
            display: grid; grid-template-columns: 1fr 1fr; gap: 0;
            border: 1px solid #d1d5db; border-radius: 10px; overflow: hidden; margin: 16px 0;
          }
          .cell { padding: 10px 12px; border-bottom: 1px solid #e5e7eb; border-right: 1px solid #e5e7eb; }
          .cell:nth-child(2n) { border-right: none; }
          .cell-label { font-size: 11px; color: #6b7280; margin-bottom: 2px; }
          .cell-value { font-size: 13px; font-weight: 600; color: #111827; word-break: break-all; }
          .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
          .stmt { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px; }
          .stmt th, .stmt td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }
          .stmt th { background: #f9fafb; color: #6b7280; text-transform: uppercase; font-size: 10px; }
          .note { margin-top: 18px; font-size: 12px; color: #6b7280; }
          @media print { body { padding: 12px; } }
        </style>
      </head>
      <body>
        <div class="receipt">
          <div class="brand-row">
            <img class="logo-mpay" src="${escapeHtml(logoSrc)}" alt="mPayHub" />
            <div style="text-align:right">
              <div class="doc-title">AEPS Receipt</div>
              <div class="doc-meta">${escapeHtml(ctx.productLabel)}</div>
            </div>
          </div>
          <span class="status-badge ${statusClass}">${escapeHtml(ctx.status)}</span>
          <div class="grid">
            <div class="cell"><div class="cell-label">Amount</div><div class="cell-value">${escapeHtml(ctx.amount)}</div></div>
            <div class="cell"><div class="cell-label">Bank RRN</div><div class="cell-value mono">${escapeHtml(ctx.rrn)}</div></div>
            <div class="cell"><div class="cell-label">Txn ID</div><div class="cell-value mono">${escapeHtml(ctx.merchantTranId)}</div></div>
            <div class="cell"><div class="cell-label">Network ref</div><div class="cell-value mono">${escapeHtml(ctx.fpId)}</div></div>
            <div class="cell"><div class="cell-label">Bank</div><div class="cell-value">${escapeHtml(ctx.bank)}</div></div>
            <div class="cell"><div class="cell-label">Aadhaar</div><div class="cell-value mono">${escapeHtml(ctx.aadhaar)}</div></div>
            <div class="cell"><div class="cell-label">Mobile</div><div class="cell-value">${escapeHtml(ctx.mobile)}</div></div>
            <div class="cell"><div class="cell-label">Available balance</div><div class="cell-value">${escapeHtml(ctx.balance)}</div></div>
            <div class="cell"><div class="cell-label">When</div><div class="cell-value">${escapeHtml(ctx.when)}</div></div>
            <div class="cell"><div class="cell-label">Response</div><div class="cell-value">${escapeHtml(ctx.response)}</div></div>
          </div>
          ${statementHtml}
          <p class="note">This is a system-generated mPayHub AEPS receipt. No signature is required.</p>
        </div>
      </body>
    </html>
  `;
};

export const openAepsReceiptPrint = (html, { mobile = false } = {}) => {
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
