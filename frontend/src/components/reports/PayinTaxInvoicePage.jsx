import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { createPortal } from 'react-dom';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { FiArrowLeft, FiPrinter, FiSave } from 'react-icons/fi';
import { useAuth } from '../../context/AuthContext';
import { reportsAPI } from '../../services/api';
import { isAdminUser } from '../../utils/rolePermissions';
import Button from '../common/Button';
import Input from '../common/Input';
import PayinTaxInvoiceDocument from './PayinTaxInvoiceDocument';
import { recomputeInvoice } from './payinTaxInvoiceMath';

const PRINT_STYLE = `
  .tax-invoice-print-host { display: none; }
  @media print {
    @page { size: A4 portrait; margin: 8mm; }
    html, body { background: #fff !important; height: auto !important; margin: 0 !important; }
    #root { display: none !important; }
    body > .tax-invoice-print-host {
      display: block !important;
      position: static !important;
      width: 100% !important;
      height: auto !important;
      overflow: visible !important;
    }
    .tax-invoice-sheet { min-height: 277mm; }
    .no-print { display: none !important; }
  }
`;

const PayinTaxInvoicePage = () => {
  const { transactionId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const preview = useMemo(() => (invoice ? recomputeInvoice(invoice) : null), [invoice]);

  const load = useCallback(async () => {
    if (!transactionId) return;
    setLoading(true);
    setError('');
    const res = await reportsAPI.getPayinTaxInvoice(transactionId);
    setLoading(false);
    if (!res?.success) {
      setError(res?.message || 'Could not open this invoice.');
      setInvoice(null);
      return;
    }
    setInvoice(recomputeInvoice(res.data?.invoice || {}));
  }, [transactionId]);

  useEffect(() => {
    load();
  }, [load]);

  if (!isAdminUser(user)) {
    return <Navigate to="/reports/payin" replace />;
  }

  const patchCustomer = (key, value) => {
    setInvoice((prev) => recomputeInvoice({
      ...prev,
      customer: { ...(prev?.customer || {}), [key]: value },
    }));
  };

  const patchField = (key, value) => {
    setInvoice((prev) => recomputeInvoice({ ...prev, [key]: value }));
  };

  const patchLine = (index, key, value) => {
    setInvoice((prev) => {
      const lines = (prev.lines || []).map((row, i) => {
        if (i !== index) return row;
        if (key === 'price') {
          return { ...row, price: value, listAmount: value };
        }
        return { ...row, [key]: value };
      });
      return recomputeInvoice({ ...prev, lines });
    });
  };

  const addLine = () => {
    setInvoice((prev) => recomputeInvoice({
      ...prev,
      lines: [...(prev.lines || []), { title: 'New course', quantity: 1, price: '0', amount: '0' }],
    }));
  };

  const removeLine = (index) => {
    setInvoice((prev) => {
      const lines = (prev.lines || []).filter((_, i) => i !== index);
      return recomputeInvoice({
        ...prev,
        lines: lines.length ? lines : [{ title: 'Pay In', quantity: 1, price: prev.transactionAmount || prev.total || '0' }],
      });
    });
  };

  const patchCoupon = (index, key, value) => {
    setInvoice((prev) => {
      const coupons = (prev.coupons || []).map((row, i) => (i === index ? { ...row, [key]: value } : row));
      return recomputeInvoice({ ...prev, coupons });
    });
  };

  const addCoupon = () => {
    setInvoice((prev) => {
      const linesGross = Number(prev.linesGross || 0);
      const txn = Number(prev.transactionAmount || 0);
      const currentCoupons = Number(prev.couponTotal || 0);
      const suggested = Math.max(0, Math.round((linesGross - currentCoupons - txn) * 100) / 100);
      return recomputeInvoice({
        ...prev,
        coupons: [...(prev.coupons || []), { name: 'Coupon', amount: String(suggested || 0) }],
      });
    });
  };

  const removeCoupon = (index) => {
    setInvoice((prev) => recomputeInvoice({
      ...prev,
      coupons: (prev.coupons || []).filter((_, i) => i !== index),
    }));
  };

  const handleSave = async () => {
    if (!preview) return;
    setSaving(true);
    setNotice('');
    setError('');
    const res = await reportsAPI.savePayinTaxInvoice(transactionId, preview);
    setSaving(false);
    if (!res?.success) {
      setError(res?.message || 'Could not save invoice.');
      return;
    }
    setInvoice(recomputeInvoice(res.data?.invoice || preview));
    setNotice('Invoice saved. You can print or Save as PDF.');
  };

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 sm:p-6">
      <style>{PRINT_STYLE}</style>
      <div className="no-print flex flex-wrap items-center justify-between gap-3">
        <div>
          <button
            type="button"
            onClick={() => navigate('/reports/payin')}
            className="mb-1 inline-flex items-center gap-1 text-sm text-blue-700 hover:underline"
          >
            <FiArrowLeft /> Back to Pay In report
          </button>
          <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Generate tax invoice</h1>
          <p className="text-sm text-gray-500">
            Transaction <span className="font-mono">{transactionId}</span>
            {' · '}
            <Link to="/admin/invoice-settings" className="text-blue-700 hover:underline">Invoice settings</Link>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" variant="outline" onClick={handlePrint} icon={FiPrinter}>
            Print / Save as PDF
          </Button>
          <Button type="button" loading={saving} onClick={handleSave} icon={FiSave}>
            Save invoice
          </Button>
        </div>
      </div>

      {loading ? <p className="text-sm text-gray-500">Loading…</p> : null}
      {error ? <p className="no-print text-sm text-red-600">{error}</p> : null}
      {notice ? <p className="no-print text-sm text-emerald-700">{notice}</p> : null}

      {preview ? (
        <div className="grid gap-6 lg:grid-cols-[minmax(280px,340px)_1fr]">
          <div className="no-print space-y-4 rounded-lg border border-gray-200 bg-white p-4 dark:border-slate-700 dark:bg-slate-900">
            <h2 className="text-sm font-bold text-gray-900 dark:text-slate-100">Edit invoice</h2>
            <div className="rounded border border-slate-200 bg-slate-50 p-2 text-xs text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
              <div>Paid amount: ₹{preview.transactionAmount}</div>
              <div>Invoice total: ₹{preview.total}</div>
              {preview.rrn ? <div>RRN: {preview.rrn}</div> : null}
              {!preview.amountMatchesTransaction ? (
                <p className="mt-1 font-semibold text-amber-700">
                  Lines − coupons should match the paid amount. Add a coupon (or adjust courses) to balance.
                </p>
              ) : (
                <p className="mt-1 font-semibold text-emerald-700">Invoice total matches the paid transaction.</p>
              )}
            </div>
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">Customer</h3>
              <Input label="Customer name" value={preview.customer?.name || ''} onChange={(e) => patchCustomer('name', e.target.value)} />
              <Input label="Email" value={preview.customer?.email || ''} onChange={(e) => patchCustomer('email', e.target.value)} />
              <Input label="Phone" value={preview.customer?.phone || ''} onChange={(e) => patchCustomer('phone', e.target.value)} />
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-slate-300">Address</label>
                <textarea
                  className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
                  rows={2}
                  value={preview.customer?.address || ''}
                  onChange={(e) => patchCustomer('address', e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-3 border-t border-gray-100 pt-3 dark:border-slate-700">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">Invoice summary</h3>
              <p className="text-[11px] text-gray-500 dark:text-slate-400">
                Shown once on the invoice next to customer details as <span className="font-semibold">Course :</span>
              </p>
              <Input
                label="Course title (summary)"
                value={preview.courseTitle || ''}
                onChange={(e) => patchField('courseTitle', e.target.value)}
              />
              <Input label="Payment method" value={preview.paymentMethod || ''} onChange={(e) => patchField('paymentMethod', e.target.value)} />
              <Input label="Invoice date" value={preview.date || ''} onChange={(e) => patchField('date', e.target.value)} />
            </div>

            <div className="space-y-2 border-t border-gray-100 pt-3 dark:border-slate-700">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-slate-400">
                    Purchased courses (line items)
                  </h3>
                  <p className="mt-0.5 text-[11px] text-gray-500 dark:text-slate-400">
                    Each row becomes one line in the Txn Details table. Separate from the summary course title above.
                  </p>
                </div>
                <button type="button" className="shrink-0 text-xs font-semibold text-blue-700 hover:underline" onClick={addLine}>
                  Add line item
                </button>
              </div>
              {(preview.lines || []).map((row, index) => (
                <div key={`line-${index}`} className="space-y-2 rounded border border-gray-100 p-2 dark:border-slate-700">
                  <p className="text-[11px] font-semibold text-gray-500 dark:text-slate-400">Line {index + 1}</p>
                  <Input
                    label="Purchased course name"
                    value={row.title || ''}
                    onChange={(e) => patchLine(index, 'title', e.target.value)}
                  />
                  <div className="grid grid-cols-2 gap-2">
                    <Input label="Qty" value={String(row.quantity ?? 1)} onChange={(e) => patchLine(index, 'quantity', e.target.value)} />
                    <Input label="Price (incl. GST)" value={String(row.listAmount || row.price || '')} onChange={(e) => patchLine(index, 'price', e.target.value)} />
                  </div>
                  {(preview.lines || []).length > 1 ? (
                    <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => removeLine(index)}>
                      Remove line item
                    </button>
                  ) : null}
                </div>
              ))}
            </div>

            <div className="space-y-2 border-t border-gray-100 pt-3 dark:border-slate-700">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-semibold">Coupons (Partner only)</h3>
                <button type="button" className="text-xs font-semibold text-blue-700 hover:underline" onClick={addCoupon}>
                  Add coupon
                </button>
              </div>
              <p className="text-[11px] text-gray-500">
                Use coupons to balance course totals against the paid transaction amount. Not sent to LMS.
              </p>
              {(preview.coupons || []).map((row, index) => (
                <div key={`coupon-${index}`} className="space-y-2 rounded border border-gray-100 p-2 dark:border-slate-700">
                  <Input label="Coupon name" value={row.name || ''} onChange={(e) => patchCoupon(index, 'name', e.target.value)} />
                  <Input label="Amount (₹)" value={String(row.amount ?? '')} onChange={(e) => patchCoupon(index, 'amount', e.target.value)} />
                  <button type="button" className="text-xs text-red-600 hover:underline" onClick={() => removeCoupon(index)}>
                    Remove coupon
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="overflow-auto rounded-lg border border-gray-200 bg-slate-50 p-3 dark:border-slate-700 dark:bg-slate-950">
            <PayinTaxInvoiceDocument invoice={preview} />
          </div>
        </div>
      ) : null}

      {preview && typeof document !== 'undefined'
        ? createPortal(
          <div className="tax-invoice-print-host">
            <PayinTaxInvoiceDocument invoice={preview} />
          </div>,
          document.body,
        )
        : null}
    </div>
  );
};

export default PayinTaxInvoicePage;
