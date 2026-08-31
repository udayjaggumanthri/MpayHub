import React, { useEffect, useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { fundManagementAPI } from '../../services/api';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import LoadingSpinner from '../common/LoadingSpinner';
import FeedbackModal from '../common/FeedbackModal';
import AccountAccessBanner from '../common/AccountAccessBanner';
import MaintenanceModuleLock from '../common/MaintenanceModuleLock';
import { formatCurrency } from '../../utils/formatters';
import { useAuth } from '../../context/AuthContext';
import { isModuleEnabled } from '../../utils/maintenanceMode';
import { FaQrcode, FaArrowLeft } from 'react-icons/fa6';

const ACCEPTED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_BYTES = 5 * 1024 * 1024;

const QrPayInPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { user, maintenance } = useAuth();
  const payInMaintenance = !isModuleEnabled(maintenance, 'pay_in');

  const state = location.state || {};
  const contact = state.contact || null;
  const initialAmount = state.amount != null ? String(state.amount) : '';
  const initialQuote = state.quote || null;
  const preselectedKey = state.checkoutKey || '';

  const [qrOptions, setQrOptions] = useState([]);
  const [loadingOptions, setLoadingOptions] = useState(true);
  const [selectedKey, setSelectedKey] = useState(preselectedKey);
  const [amount, setAmount] = useState(initialAmount);
  const [quote, setQuote] = useState(initialQuote);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState('');
  const [utr, setUtr] = useState('');
  const [paymentDate, setPaymentDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [receipt, setReceipt] = useState(null);
  const [receiptPreview, setReceiptPreview] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [successModal, setSuccessModal] = useState({ open: false, txnId: '' });

  useEffect(() => {
    if (!contact?.id) {
      navigate('/fund-management/load-money', { replace: true });
    }
  }, [contact, navigate]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadingOptions(true);
      const res = await fundManagementAPI.listPayInCheckoutGateways();
      if (cancelled) return;
      const list =
        res.success && res.data?.payment_methods
          ? res.data.payment_methods
          : res.success && res.data?.gateways
            ? res.data.gateways
            : [];
      const qrs = list.filter((o) => o.rail_type === 'qr');
      setQrOptions(qrs);
      setSelectedKey((prev) => {
        if (prev && qrs.some((q) => q.option_key === prev && !q.disabled)) return prev;
        const def = qrs.find((q) => q.is_default && !q.disabled) || qrs.find((q) => !q.disabled);
        return def?.option_key || '';
      });
      setLoadingOptions(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selected = useMemo(
    () => qrOptions.find((q) => q.option_key === selectedKey) || null,
    [qrOptions, selectedKey]
  );

  useEffect(() => {
    if (!selected?.package_id || !amount) {
      setQuote(null);
      setQuoteError('');
      return undefined;
    }
    const n = parseFloat(amount);
    if (Number.isNaN(n) || n <= 0) {
      setQuote(null);
      setQuoteError('');
      return undefined;
    }
    const t = setTimeout(async () => {
      setQuoteLoading(true);
      setQuoteError('');
      const res = await fundManagementAPI.payInQuote({
        packageId: Number(selected.package_id),
        amount: String(amount),
      });
      setQuoteLoading(false);
      if (res.success && res.data) {
        setQuote(res.data);
      } else {
        setQuote(null);
        setQuoteError(res.message || 'Could not calculate fees for this amount.');
      }
    }, 350);
    return () => clearTimeout(t);
  }, [selected?.package_id, amount]);

  const handleReceiptChange = (e) => {
    const file = e.target.files?.[0];
    setError('');
    if (!file) {
      setReceipt(null);
      setReceiptPreview('');
      return;
    }
    if (!ACCEPTED_TYPES.includes(file.type)) {
      setError('Receipt must be JPEG, PNG, or WebP.');
      return;
    }
    if (file.size > MAX_BYTES) {
      setError('Receipt must be 5 MB or smaller.');
      return;
    }
    setReceipt(file);
    setReceiptPreview(URL.createObjectURL(file));
  };

  const handleSubmit = async () => {
    setError('');
    if (!selected?.package_id || !selected?.qr_account_id) {
      setError('Select a QR account to pay into.');
      return;
    }
    if (!utr.trim()) {
      setError('Enter the UTR / bank reference from your payment.');
      return;
    }
    if (!paymentDate) {
      setError('Select the payment date.');
      return;
    }
    if (!receipt) {
      setError('Upload a screenshot of the payment.');
      return;
    }
    if (!quote || quoteError) {
      setError(quoteError || 'Enter a valid amount within package limits.');
      return;
    }
    setSubmitting(true);
    try {
      const res = await fundManagementAPI.submitPayInQr({
        packageId: selected.package_id,
        qrAccountId: selected.qr_account_id,
        contactId: contact.id,
        amount: String(amount),
        utr: utr.trim(),
        paymentDate,
        receiptFile: receipt,
      });
      if (!res.success) {
        setError(res.message || 'Could not submit payment proof.');
        return;
      }
      const txnId = res.data?.load_money?.transaction_id || res.data?.transaction_id || '';
      setSuccessModal({ open: true, txnId });
    } finally {
      setSubmitting(false);
    }
  };

  const maxLimit = selected
    ? Math.min(
        parseFloat(selected.max_amount_per_txn || 0) || Infinity,
        parseFloat(selected.remaining_daily_limit || 0) || Infinity
      )
    : null;

  if (!contact?.id) return null;

  return (
    <div className="max-w-6xl mx-auto space-y-6 px-4 sm:px-0 pb-10">
      <AccountAccessBanner user={user} mode="pay_in" maintenance={maintenance} />

      <div className="flex items-center gap-3">
        <Link
          to="/fund-management/load-money"
          className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-100"
        >
          <FaArrowLeft />
          Back to Load Money
        </Link>
      </div>

      <MaintenanceModuleLock maintenance={maintenance} moduleKey="pay_in">
        <Card padding="lg" className="border-2 border-slate-200 dark:border-slate-700 shadow-sm overflow-hidden">
          <div className="border-b border-slate-200 dark:border-slate-700 bg-gradient-to-r from-slate-50 dark:from-slate-900 to-emerald-50/40 dark:to-emerald-950/40 -mx-6 -mt-6 px-6 py-5 mb-6">
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-slate-100 text-center">Top-up request (QR)</h1>
            {maxLimit != null && Number.isFinite(maxLimit) ? (
              <p className="text-center text-red-600 dark:text-red-400 font-semibold mt-2 text-sm sm:text-base">
                Maximum top-up amount limit: {formatCurrency(maxLimit)}
              </p>
            ) : null}
            <p className="text-center text-sm text-gray-600 dark:text-slate-400 mt-2">
              Paying for: <strong>{contact.name}</strong> · {contact.phone}
            </p>
          </div>

          {loadingOptions ? (
            <LoadingSpinner text="Loading QR accounts…" />
          ) : qrOptions.length === 0 ? (
            <div className="text-center py-12 text-gray-600 dark:text-slate-400">
              <FaQrcode className="mx-auto text-gray-300 mb-3" size={48} />
              <p>No QR collection accounts are available on your account.</p>
              <Button className="mt-4" variant="outline" onClick={() => navigate('/fund-management/load-money')}>
                Return to Load Money
              </Button>
            </div>
          ) : (
            <>
              <div className="mb-6">
                <h2 className="text-sm font-semibold uppercase tracking-wide text-gray-700 dark:text-slate-300 mb-3">
                  Select QR account ({qrOptions.length})
                </h2>
                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                  {qrOptions.map((opt) => {
                    const active = opt.option_key === selectedKey;
                    const disabled = opt.disabled;
                    return (
                      <button
                        key={opt.option_key}
                        type="button"
                        disabled={disabled}
                        onClick={() => !disabled && setSelectedKey(opt.option_key)}
                        className={`text-left rounded-xl border-2 p-4 transition-all ${
                          disabled
                            ? 'border-gray-200 dark:border-slate-700 bg-gray-50 dark:bg-slate-800/50 opacity-60 cursor-not-allowed'
                            : active
                              ? 'border-emerald-500 bg-emerald-50/60 dark:bg-emerald-950/40 ring-2 ring-emerald-200 dark:ring-emerald-800 shadow-md'
                              : 'border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 hover:border-emerald-300 dark:hover:border-emerald-700 hover:shadow-sm'
                        }`}
                      >
                        <div className="flex gap-3">
                          {opt.qr_image_url ? (
                            <img
                              src={opt.qr_image_url}
                              alt=""
                              className="h-20 w-20 rounded-lg border bg-white dark:bg-slate-900 object-contain p-1 flex-shrink-0"
                            />
                          ) : (
                            <div className="h-20 w-20 rounded-lg border bg-gray-50 dark:bg-slate-800/50 flex items-center justify-center text-gray-400 dark:text-slate-500">
                              <FaQrcode size={28} />
                            </div>
                          )}
                          <div className="min-w-0 flex-1">
                            <p className="font-semibold text-gray-900 dark:text-slate-100 truncate">{opt.name}</p>
                            <p className="text-xs text-gray-600 dark:text-slate-400 mt-0.5 truncate">
                              {opt.account_display_name || '—'}
                            </p>
                            {opt.upi_vpa ? (
                              <p className="text-xs font-mono text-gray-700 dark:text-slate-300 mt-1 truncate">{opt.upi_vpa}</p>
                            ) : null}
                            <p className="text-xs text-emerald-800 dark:text-emerald-300 font-medium mt-2">
                              Left today: {formatCurrency(parseFloat(opt.remaining_daily_limit || 0))}
                            </p>
                            {disabled && opt.disabled_reason ? (
                              <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">{opt.disabled_reason}</p>
                            ) : null}
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-bold text-gray-800 dark:text-slate-200 mb-1.5">
                      Payment mode
                    </label>
                    <div className="px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg bg-gray-50 dark:bg-slate-800/50 text-gray-800 dark:text-slate-200 font-medium">
                      QR / UPI
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-800 dark:text-slate-200 mb-1.5">
                      Top-up amount <span className="text-red-500">*</span>
                    </label>
                    <Input
                      type="number"
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      placeholder="Amount"
                      min="1"
                      step="0.01"
                    />
                    {quoteLoading ? <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">Calculating fees…</p> : null}
                    {quoteError ? <p className="text-xs text-red-600 dark:text-red-400 mt-1">{quoteError}</p> : null}
                    {quote && !quoteError ? (
                      <p className="text-xs text-emerald-800 dark:text-emerald-300 mt-2 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-100 dark:border-emerald-900 rounded-lg px-3 py-2">
                        Net credit after fees: <strong>{formatCurrency(parseFloat(quote.net_credit || 0))}</strong>
                      </p>
                    ) : null}
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-800 dark:text-slate-200 mb-1.5">
                      UTR no. <span className="text-red-500">*</span>
                    </label>
                    <Input value={utr} onChange={(e) => setUtr(e.target.value)} placeholder="Enter UTR no." />
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-800 dark:text-slate-200 mb-1.5">
                      Payment date <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="date"
                      value={paymentDate}
                      onChange={(e) => setPaymentDate(e.target.value)}
                      className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-emerald-500"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-bold text-gray-800 dark:text-slate-200 mb-1.5">
                      Receipt upload <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp"
                      onChange={handleReceiptChange}
                      className="block w-full text-sm text-gray-600 dark:text-slate-400 file:mr-4 file:rounded-lg file:border-0 file:bg-emerald-600 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-white"
                    />
                    {receiptPreview ? (
                      <img src={receiptPreview} alt="Receipt" className="mt-3 max-h-36 rounded-lg border" />
                    ) : null}
                  </div>
                </div>

                <div className="flex flex-col">
                  <div className="flex-1 rounded-xl border-2 border-dashed border-gray-300 dark:border-slate-600 bg-white dark:bg-slate-900 p-6 flex flex-col items-center justify-center min-h-[320px]">
                    <p className="text-lg font-bold text-gray-900 dark:text-slate-100 mb-4 tracking-wide">SCAN &amp; PAY</p>
                    {selected?.qr_image_url ? (
                      <img
                        src={selected.qr_image_url}
                        alt="Scan QR"
                        className="max-h-64 max-w-full rounded-lg border-2 border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-900 p-3 object-contain"
                      />
                    ) : (
                      <FaQrcode className="text-gray-300" size={120} />
                    )}
                    {selected ? (
                      <div className="mt-5 text-center space-y-1 text-sm">
                        <p className="font-semibold text-gray-900 dark:text-slate-100">{selected.account_display_name || selected.name}</p>
                        {selected.upi_vpa ? (
                          <p className="font-mono text-gray-700 dark:text-slate-300">{selected.upi_vpa}</p>
                        ) : null}
                        <p className="text-gray-500 dark:text-slate-400">Pay exactly {formatCurrency(parseFloat(amount || 0) || 0)}</p>
                      </div>
                    ) : null}
                  </div>
                </div>
              </div>

              {error ? (
                <div className="mt-6 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-sm text-red-800 dark:text-red-300">
                  {error}
                </div>
              ) : null}

              <div className="mt-8 flex flex-col sm:flex-row gap-3 justify-center">
                <Button
                  variant="outline"
                  size="lg"
                  className="sm:min-w-[140px] border-gray-400"
                  onClick={() => navigate('/fund-management/load-money')}
                >
                  Cancel
                </Button>
                <Button
                  variant="primary"
                  size="lg"
                  className="sm:min-w-[140px] bg-emerald-600 hover:bg-emerald-700"
                  onClick={handleSubmit}
                  loading={submitting}
                  disabled={
                    payInMaintenance ||
                    !selected ||
                    selected.disabled ||
                    !quote ||
                    !!quoteError ||
                    quoteLoading
                  }
                >
                  Submit
                </Button>
              </div>
            </>
          )}
        </Card>
      </MaintenanceModuleLock>

      <FeedbackModal
        open={successModal.open}
        onClose={() => {
          setSuccessModal({ open: false, txnId: '' });
          navigate('/fund-management/load-money', { replace: true });
        }}
        title="Submitted for review"
        description={`Your QR payment proof was submitted successfully.\n\nReference: ${successModal.txnId || '—'}\n\nTrack status under Reports → Pay In.`}
        primaryAction={{
          label: 'Open Pay In report',
          onClick: () => navigate('/reports/payin'),
        }}
      />
    </div>
  );
};

export default QrPayInPage;
