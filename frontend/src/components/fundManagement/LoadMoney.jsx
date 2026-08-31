import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { contactsAPI, fundManagementAPI } from '../../services/api';
import { mapContactRow } from '../../utils/contactsHelpers';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import FeedbackModal from '../common/FeedbackModal';
import ContactSearchTypeahead from './ContactSearchTypeahead';
import SelectField from '../common/SelectField';
import { formatCurrency } from '../../utils/formatters';
import { validateAmount } from '../../utils/validators';
import { useWallet } from '../../context/WalletContext';
import { useAuth } from '../../context/AuthContext';
import MaintenanceModuleLock from '../common/MaintenanceModuleLock';
import { isModuleEnabled } from '../../utils/maintenanceMode';
import { FiSearch, FiMail, FiX, FiInfo } from 'react-icons/fi';
import { FaPhone, FaUser, FaIndianRupeeSign, FaCircleCheck, FaCircleExclamation } from 'react-icons/fa6';
import { isAdminUser } from '../../utils/rolePermissions';
import AccountAccessBanner from '../common/AccountAccessBanner';

function loadRazorpayScript() {
  return new Promise((resolve, reject) => {
    if (typeof window !== 'undefined' && window.Razorpay) {
      resolve();
      return;
    }
    const existing = document.querySelector('script[src="https://checkout.razorpay.com/v1/checkout.js"]');
    if (existing) {
      existing.addEventListener('load', () => resolve());
      existing.addEventListener('error', reject);
      return;
    }
    const s = document.createElement('script');
    s.src = 'https://checkout.razorpay.com/v1/checkout.js';
    s.async = true;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error('Failed to load Razorpay'));
    document.body.appendChild(s);
  });
}

const LoadMoney = () => {
  const navigate = useNavigate();
  const { user, maintenance, refreshMaintenance } = useAuth();
  const payInMaintenance = !isModuleEnabled(maintenance, 'pay_in');
  const { refreshWallets } = useWallet();
  const [customerSearch, setCustomerSearch] = useState('');
  const [customerDetails, setCustomerDetails] = useState(null);
  const [checkoutGateways, setCheckoutGateways] = useState([]);
  const [gatewaysLoading, setGatewaysLoading] = useState(true);
  const [selectedCheckoutKey, setSelectedCheckoutKey] = useState('');
  const [gatewayRetryMode, setGatewayRetryMode] = useState(false);
  const [amount, setAmount] = useState('');
  const [quote, setQuote] = useState(null);
  const [quoteLoading, setQuoteLoading] = useState(false);
  const [quoteError, setQuoteError] = useState('');
  const [showPriceBreakdown, setShowPriceBreakdown] = useState(false);
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showGatewayInterface, setShowGatewayInterface] = useState(false);
  const [orderPayload, setOrderPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchFeedbackModal, setSearchFeedbackModal] = useState({
    open: false,
    title: '',
    description: '',
    primaryAction: null,
  });
  const [payFeedbackModal, setPayFeedbackModal] = useState({
    open: false,
    title: '',
    description: '',
    primaryAction: null,
  });

  useEffect(() => {
    refreshMaintenance?.();
    const id = setInterval(() => refreshMaintenance?.(), 60000);
    return () => clearInterval(id);
  }, [refreshMaintenance]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setGatewaysLoading(true);
      const res = await fundManagementAPI.listPayInCheckoutGateways();
      if (cancelled) return;
      const list =
        res.success && res.data?.payment_methods
          ? res.data.payment_methods
          : res.success && res.data?.gateways
            ? res.data.gateways
            : [];
      setCheckoutGateways(list);
      setSelectedCheckoutKey((prev) => {
        if (prev && list.some((g) => g.option_key === prev)) return prev;
        if (!list.length) return '';
        const def = list.find((g) => g.is_default && !g.disabled) || list.find((g) => !g.disabled) || list[0];
        return def.option_key;
      });
      setGatewaysLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedCheckout =
    checkoutGateways.find((g) => g.option_key === selectedCheckoutKey) || null;
  const isQrRail = selectedCheckout?.rail_type === 'qr';
  const selectedPackageId = selectedCheckout?.package_id
    ? String(selectedCheckout.package_id)
    : '';
  const selectedGatewayId =
    !isQrRail && selectedCheckout?.gateway_id ? String(selectedCheckout.gateway_id) : '';

  useEffect(() => {
    if (!selectedPackageId || !amount) {
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
        packageId: Number(selectedPackageId),
        amount: String(amount),
      });
      setQuoteLoading(false);
      if (res.success && res.data) {
        setQuote(res.data);
        setQuoteError('');
      } else {
        setQuote(null);
        setQuoteError(res.message || 'Could not calculate fees for this amount.');
      }
    }, 350);
    return () => clearTimeout(t);
  }, [selectedCheckoutKey, selectedPackageId, amount]);

  useEffect(() => {
    if (!isAdminUser(user)) setShowPriceBreakdown(false);
  }, [user]);

  const handlePickCustomer = useCallback((mapped) => {
    setCustomerDetails(mapped);
  }, []);

  const handleCustomerSearch = async () => {
    const raw = customerSearch.trim();
    const digitsOnly = raw.replace(/\D/g, '');
    const usePhone = digitsOnly.length === 10;
    const useName = !usePhone && raw.length >= 2;

    if (!usePhone && !useName) {
      setSearchFeedbackModal({
        open: true,
        title: 'Check your search',
        description:
          'Enter a full 10-digit mobile number, or at least 2 characters of the contact name, then try Search again.',
        primaryAction: null,
      });
      return;
    }

    setSearching(true);
    try {
      const result = await contactsAPI.searchContactForTransaction(
        usePhone ? { phone: digitsOnly } : { name: raw }
      );
      const row = result.success ? result.data?.contact : null;
      const mapped = mapContactRow(row);
      if (mapped) {
        setCustomerDetails(mapped);
      } else {
        const hint =
          'If this person is not in your saved contacts yet, add them under User Management → Contacts first, then search again.';
        const description = [result.message, hint].filter(Boolean).join('\n\n');
        setSearchFeedbackModal({
          open: true,
          title: 'Contact not found',
          description,
          primaryAction: {
            label: 'Go to Contacts',
            onClick: () => navigate('/user-management/contacts'),
          },
        });
        setCustomerDetails(null);
      }
    } catch (error) {
      setSearchFeedbackModal({
        open: true,
        title: 'Could not search',
        description: 'Something went wrong while searching. Check your connection and try again.',
        primaryAction: null,
      });
      setCustomerDetails(null);
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (amount && parseFloat(amount) > 0 && customerDetails) {
        e.preventDefault();
        e.returnValue = 'Are you sure you want to exit? Your transaction may be incomplete.';
        return e.returnValue;
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, [amount, customerDetails]);

  const handleAmountSubmit = () => {
    const amountValidation = validateAmount(parseFloat(amount));
    if (!amountValidation.valid) {
      alert(amountValidation.message);
      return;
    }
    if (!customerDetails?.id) {
      alert('Please search and select a customer first');
      return;
    }
    if (!selectedCheckoutKey || !selectedPackageId) {
      alert('Please select a payment method');
      return;
    }
    if (isQrRail) {
      if (quoteError || !quote) {
        alert(quoteError || 'Wait for a valid price quote, or adjust the amount.');
        return;
      }
      navigate('/fund-management/load-money/qr', {
        state: {
          contact: customerDetails,
          amount,
          quote,
          checkoutKey: selectedCheckoutKey,
        },
      });
      return;
    }
    if (quoteError || !quote) {
      alert(quoteError || 'Wait for a valid price quote, or adjust the amount.');
      return;
    }
    setShowPaymentModal(true);
  };

  const openGatewayRetry = () => {
    setGatewayRetryMode(true);
    setShowPaymentModal(false);
    setShowGatewayInterface(false);
    setOrderPayload(null);
    setPayFeedbackModal((m) => ({ ...m, open: false }));
  };

  const handleProceedToPayment = async () => {
    if (!customerDetails?.id || !selectedCheckoutKey || !selectedPackageId) return;
    if (checkoutGateways.length > 0 && !selectedGatewayId) {
      alert('Please select a payment gateway');
      return;
    }
    setLoading(true);
    setGatewayRetryMode(false);
    try {
      const res = await fundManagementAPI.payInCreateOrder({
        packageId: Number(selectedPackageId),
        amount: String(amount),
        contactId: customerDetails.id,
        gatewayId: selectedGatewayId ? Number(selectedGatewayId) : undefined,
      });
      if (!res.success) {
        setPayFeedbackModal({
          open: true,
          title: 'Could not start payment',
          description: res.message || 'Order creation failed. Try again or contact support.',
          primaryAction: {
            label: 'Try another gateway',
            onClick: openGatewayRetry,
          },
        });
        return;
      }
      setOrderPayload(res.data);
      setShowPaymentModal(false);
      setShowGatewayInterface(true);
    } finally {
      setLoading(false);
    }
  };

  const handleRazorpayPay = async () => {
    const rz = orderPayload?.razorpay;
    const txnId = orderPayload?.transaction_id;
    if (!rz?.key_id || !rz?.order_id) {
      setPayFeedbackModal({
        open: true,
        title: 'Razorpay not ready',
        description: 'Payment options are missing. Close and try again.',
        primaryAction: null,
      });
      return;
    }
    setLoading(true);
    try {
      await loadRazorpayScript();
      const options = {
        key: rz.key_id,
        amount: rz.amount,
        currency: rz.currency || 'INR',
        order_id: rz.order_id,
        name: 'mPayhub',
        description: `Load money — ${txnId || ''}`,
        prefill: {
          name: customerDetails?.name || orderPayload?.customer_name || '',
          email: customerDetails?.email || orderPayload?.customer_email || '',
          contact: customerDetails?.phone || orderPayload?.customer_phone || '',
        },
        async handler(response) {
          const oid = response?.razorpay_order_id;
          const pid = response?.razorpay_payment_id;
          const sig = response?.razorpay_signature;
          if (!txnId || !oid || !pid || !sig) {
            setShowGatewayInterface(false);
            setPayFeedbackModal({
              open: true,
              title: 'Incomplete payment response',
              description:
                'Razorpay did not return full payment details. If money was debited, check Reports → Pay In or contact support with your reference ID.',
              primaryAction: {
                label: 'Open Pay In report',
                onClick: () => navigate('/reports/payin'),
              },
            });
            return;
          }
          setLoading(true);
          try {
            const res = await fundManagementAPI.payInVerifyRazorpay({
              transactionId: txnId,
              razorpayOrderId: oid,
              razorpayPaymentId: pid,
              razorpaySignature: sig,
            });
            setShowGatewayInterface(false);
            setOrderPayload(null);
            setAmount('');
            setCustomerDetails(null);
            setCustomerSearch('');
            setQuote(null);
            if (res.success) {
              refreshWallets();
              const net = res.data?.load_money?.net_credit;
              setPayFeedbackModal({
                open: true,
                title: 'Payment successful',
                description: `Your wallet has been credited. Net credit: ${formatCurrency(parseFloat(net || 0))}. Reference: ${txnId}.\n\nFull history: Reports → Pay In.`,
                primaryAction: {
                  label: 'Open Pay In report',
                  onClick: () => navigate('/reports/payin'),
                },
              });
            } else {
              setPayFeedbackModal({
                open: true,
                title: 'Could not confirm payment',
                description:
                  res.message ||
                  'Verification failed. If Razorpay shows success, check Reports → Pay In in a moment, or configure a public webhook URL for production.',
                primaryAction: {
                  label: 'Try another gateway',
                  onClick: openGatewayRetry,
                },
                alternateAction: {
                  label: 'Open Pay In report',
                  onClick: () => navigate('/reports/payin'),
                },
              });
            }
          } finally {
            setLoading(false);
          }
        },
        modal: {
          ondismiss() {
            setLoading(false);
          },
        },
      };
      const rzp = new window.Razorpay(options);
      rzp.open();
    } catch (e) {
      setPayFeedbackModal({
        open: true,
        title: 'Checkout error',
        description: e?.message || 'Could not open Razorpay checkout.',
        primaryAction: null,
      });
    } finally {
      setLoading(false);
    }
  };

  const customerSearchTrim = customerSearch.trim();
  const customerDigits = customerSearchTrim.replace(/\D/g, '');
  const customerSearchSubmitDisabled =
    searching || !(customerDigits.length === 10 || customerSearchTrim.length >= 2);

  const netNum = quote ? parseFloat(quote.net_credit) : 0;
  const grossNum = amount ? parseFloat(amount) : 0;
  const absorbedRetailerShare = quote ? parseFloat(quote.retailer_share_absorbed_to_admin || 0) : 0;
  const showPayinCommissionDetail = isAdminUser(user);
  const quoteTotalDeduction =
    quote && quote.total_deduction != null && String(quote.total_deduction).trim() !== ''
      ? parseFloat(quote.total_deduction)
      : null;

  return (
    <div className="max-w-5xl mx-auto space-y-4 sm:space-y-6 px-4 sm:px-0">
      <AccountAccessBanner user={user} mode="pay_in" maintenance={maintenance} />
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-slate-100">Load Money</h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600 dark:text-slate-400">
            Add funds using your assigned payment gateway (fees shown before you pay). Pay-in history lives under{' '}
            <span className="font-medium text-gray-800 dark:text-slate-200">Reports → Pay In</span>.
          </p>
        </div>
      </div>

      <MaintenanceModuleLock maintenance={maintenance} moduleKey="pay_in">
      <Card
        title="Customer Search"
        subtitle="Type a name or phone — suggestions appear as you type; tap a row to select, or use Search for an exact match"
        padding="lg"
      >
        <div className="space-y-6">
          <ContactSearchTypeahead
            value={customerSearch}
            onChange={setCustomerSearch}
            onPick={handlePickCustomer}
            onClearSelection={() => setCustomerDetails(null)}
            placeholder="Start typing name or phone..."
            helperText="At least 2 characters. If several names match, pick from the list or enter the full 10-digit phone. Press Enter to search."
            onSubmitSearch={handleCustomerSearch}
            submitSearchDisabled={customerSearchSubmitDisabled}
            trailingAction={
              <Button
                onClick={handleCustomerSearch}
                disabled={customerSearchSubmitDisabled}
                loading={searching}
                icon={FiSearch}
                iconPosition="left"
                size="lg"
                fullWidth
                className="sm:w-auto min-h-[3.125rem] text-lg leading-snug"
              >
                Search
              </Button>
            }
          />

          {customerDetails && (
            <div className="p-6 bg-gradient-to-r from-blue-50 dark:from-blue-950/40 to-indigo-50 dark:to-indigo-950/40 border-2 border-blue-200 dark:border-blue-800 rounded-xl">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center shadow-lg">
                    <FaUser className="text-white" size={24} />
                  </div>
                </div>
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-3">
                    <FaCircleCheck className="text-green-600 dark:text-green-400" size={22} />
                    <h3 className="text-lg font-bold text-gray-900 dark:text-slate-100">Contact Information</h3>
                  </div>
                  <p className="text-xs text-gray-600 dark:text-slate-400 mb-2">
                    Matched from your saved contacts — confirm identity before sending money.
                  </p>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <FaUser className="text-blue-600 dark:text-blue-400" size={18} />
                      <p className="font-semibold text-gray-900 dark:text-slate-100">{customerDetails.name}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <FiMail className="text-blue-600 dark:text-blue-400" size={18} />
                      <p className="text-sm text-gray-600 dark:text-slate-400">
                        <span className="font-medium">{customerDetails.email || '—'}</span>
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <FaPhone className="text-blue-600 dark:text-blue-400" size={18} />
                      <p className="text-sm text-gray-600 dark:text-slate-400">
                        <span className="font-medium">{customerDetails.phone}</span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </Card>

      {customerDetails && (
        <>
          <Card title="Payment method" subtitle="Choose gateway checkout or manual QR pay-in" padding="lg">
            <div className="space-y-3">
              {gatewaysLoading ? (
                <p className="text-sm text-gray-600 dark:text-slate-400">Loading payment gateways…</p>
              ) : checkoutGateways.length === 0 ? (
                <div className="p-4 bg-yellow-50 dark:bg-yellow-950/40 border border-yellow-200 dark:border-yellow-800 rounded-lg flex items-center gap-2">
                  <FaCircleExclamation className="text-yellow-600 dark:text-yellow-400 flex-shrink-0" size={20} />
                  <p className="text-yellow-800 dark:text-yellow-300 text-sm">
                    No payment methods are available on your account. Contact your administrator.
                  </p>
                </div>
              ) : (
                <>
                  <SelectField
                    label="Payment method"
                    required
                    value={selectedCheckoutKey}
                    onChange={(val) => {
                      setSelectedCheckoutKey(val);
                      setGatewayRetryMode(false);
                    }}
                    searchable={!checkoutGateways.some((g) => g.disabled || (g.status && g.status !== 'active'))}
                    options={checkoutGateways.map((g) => {
                      const isDisabled = g.disabled || (g.status && g.status !== 'active');
                      const suffix = isDisabled && g.disabled_reason ? ` — ${g.disabled_reason}` : '';
                      const railLabel = g.rail_type === 'qr' ? ' [QR]' : '';
                      return {
                        value: g.option_key,
                        label: `${g.name}${railLabel}${g.is_default ? ' (default)' : ''}${suffix}`,
                        disabled: isDisabled,
                      };
                    })}
                    getOptionValue={(g) => g.value}
                    getOptionLabel={(g) => g.label}
                    includeEmptyOption={false}
                  />
                  {selectedCheckout && (
                    <p className="text-sm text-gray-500 dark:text-slate-400">
                      Allowed amount: {formatCurrency(parseFloat(selectedCheckout.min_amount))} –{' '}
                      {formatCurrency(parseFloat(selectedCheckout.max_amount_per_txn))} per transaction
                    </p>
                  )}
                  {isQrRail ? (
                    <p className="text-sm text-emerald-800 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-100 dark:border-emerald-900 rounded-lg px-3 py-2">
                      You will be taken to a QR top-up screen where <strong>all available QR accounts</strong> are shown.
                      Scan any one, then submit UTR and payment screenshot for admin review.
                    </p>
                  ) : null}
                  {selectedCheckout?.status && selectedCheckout.status !== 'active' ? (
                    <p className="text-xs text-amber-700 dark:text-amber-300">
                      This gateway may be unavailable. Consider choosing another option.
                    </p>
                  ) : null}
                  {gatewayRetryMode && (
                    <div className="mt-3 p-3 rounded-lg border border-amber-300 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 text-sm text-amber-900 dark:text-amber-300">
                      The previous gateway did not complete payment. Choose another gateway below and tap{' '}
                      <strong>PAY NOW</strong> to try again with the same amount.
                    </div>
                  )}
                </>
              )}
            </div>
          </Card>

          <Card title="Enter amount (INR)" subtitle="Quote updates as you type" padding="lg">
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
                  Amount (INR) <span className="text-red-500">*</span>
                </label>
                <Input
                  type="number"
                  icon={FaIndianRupeeSign}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="Enter amount (e.g., 10000)"
                  min="1"
                  step="0.01"
                  size="lg"
                />
              </div>

              {quoteLoading && (
                <p className="text-sm text-gray-600 dark:text-slate-400">Calculating fees…</p>
              )}
              {quoteError && (
                <div className="p-4 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg text-red-800 dark:text-red-300 text-sm">{quoteError}</div>
              )}

              {quote && !quoteError && grossNum > 0 && (
                <div className="space-y-4">
                  <div className="p-6 bg-gray-50 dark:bg-slate-800/50 rounded-xl border border-gray-200 dark:border-slate-700">
                    <h4 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-4 uppercase tracking-wide">Summary</h4>
                    <div className="space-y-3">
                      <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-slate-700">
                        <span className="text-gray-600 dark:text-slate-400">You pay (gross)</span>
                        <span className="font-semibold text-gray-900 dark:text-slate-100 text-lg">{formatCurrency(grossNum)}</span>
                      </div>
                      {showPayinCommissionDetail &&
                      quoteTotalDeduction != null &&
                      !Number.isNaN(quoteTotalDeduction) ? (
                        <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-slate-700">
                          <span className="text-gray-600 dark:text-slate-400">Total deductions (gateway + platform + upline)</span>
                          <span className="font-semibold text-red-600 dark:text-red-400">-{formatCurrency(quoteTotalDeduction)}</span>
                        </div>
                      ) : null}
                      {showPayinCommissionDetail && absorbedRetailerShare > 0 ? (
                        <p className="text-xs text-gray-600 dark:text-slate-400 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-lg px-3 py-2">
                          The package’s retailer commission rate ({quote.breakdown?.retailer_commission_pct ?? '—'}%) is
                          included in the <strong>Admin (platform)</strong> share — it is not added to your commission
                          wallet.
                        </p>
                      ) : null}
                      <div className="flex justify-between items-center pt-3 bg-blue-50 dark:bg-blue-950/40 p-3 rounded-lg">
                        <span className="text-lg font-bold text-gray-900 dark:text-slate-100">Net credit (main wallet)</span>
                        <span className="text-2xl font-bold text-blue-600 dark:text-blue-400">{formatCurrency(netNum)}</span>
                      </div>
                    </div>
                  </div>

                  {showPayinCommissionDetail ? (
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setShowPriceBreakdown((v) => !v)}
                      className="inline-flex items-center gap-2 text-sm font-medium text-blue-700 dark:text-blue-300 hover:text-blue-900 dark:hover:text-blue-200"
                    >
                      <FiInfo size={18} />
                      {showPriceBreakdown ? 'Hide price breakdown' : 'Prices — full breakdown'}
                    </button>
                    {showPriceBreakdown && quote.lines && quote.lines.length > 0 ? (
                      <div className="mt-3 space-y-2">
                        {quote.breakdown?.hierarchy_adjusted ? (
                          <p className="text-xs text-gray-600 dark:text-slate-400 rounded-lg bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 px-3 py-2">
                            Your upline does not include every distributor tier in the package. Missing tiers roll
                            up to the nearest present upline (Distributor → Master → Super); any remainder is in the{' '}
                            <strong>Admin (platform)</strong> row. Net credit and total deductions follow your Gateway
                            pay-in package settings.
                          </p>
                        ) : null}
                        <div className="border border-gray-200 dark:border-slate-700 rounded-xl overflow-hidden shadow-sm bg-white dark:bg-slate-900">
                          <table className="w-full text-sm">
                            <thead className="bg-gray-100 dark:bg-slate-800">
                              <tr>
                                <th className="text-left p-3 font-semibold text-gray-700 dark:text-slate-300">Component</th>
                                <th className="text-right p-3 font-semibold text-gray-700 dark:text-slate-300">%</th>
                                <th className="text-right p-3 font-semibold text-gray-700 dark:text-slate-300">Amount</th>
                              </tr>
                            </thead>
                            <tbody>
                              {quote.lines.map((line) => (
                                <tr key={line.key} className="border-t border-gray-100 dark:border-slate-800">
                                  <td className="p-3 text-gray-800 dark:text-slate-200">
                                    <span className="block">{line.label}</span>
                                    {line.note ? (
                                      <span className="mt-1 block text-xs font-normal text-gray-500 dark:text-slate-400">{line.note}</span>
                                    ) : null}
                                  </td>
                                  <td className="p-3 text-right text-gray-600 dark:text-slate-400 align-top">{line.pct}%</td>
                                  <td className="p-3 text-right font-medium text-gray-900 dark:text-slate-100 align-top">
                                    {formatCurrency(parseFloat(line.amount))}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    ) : null}
                  </div>
                  ) : null}
                </div>
              )}

              <Button
                onClick={handleAmountSubmit}
                disabled={
                  payInMaintenance ||
                  !amount ||
                  parseFloat(amount) <= 0 ||
                  !selectedCheckoutKey ||
                  selectedCheckout?.disabled ||
                  gatewaysLoading ||
                  !quote ||
                  !!quoteError ||
                  quoteLoading
                }
                variant="primary"
                size="lg"
                fullWidth
                icon={FaIndianRupeeSign}
                iconPosition="left"
              >
                {isQrRail ? 'CONTINUE TO QR PAYMENT' : 'PAY NOW'}
              </Button>
            </div>
          </Card>
        </>
      )}
      </MaintenanceModuleLock>

      {showPaymentModal && quote && !payInMaintenance && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-md w-full border-2 border-blue-200 dark:border-blue-800 my-auto" padding="lg" shadow="xl">
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-slate-100 mb-4 sm:mb-6">Payment confirmation</h2>

            <div className="space-y-3 sm:space-y-4 mb-4 sm:mb-6">
              <div className="p-4 bg-gray-50 dark:bg-slate-800/50 rounded-lg space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-slate-400">Customer</span>
                  <span className="font-semibold text-gray-900 dark:text-slate-100">{customerDetails.name}</span>
                </div>
                {selectedCheckout ? (
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-slate-400">Gateway</span>
                    <span className="font-semibold text-gray-900 dark:text-slate-100 text-right max-w-[60%]">{selectedCheckout.name}</span>
                  </div>
                ) : null}
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-slate-400">Gross</span>
                  <span className="font-semibold text-gray-900 dark:text-slate-100">{formatCurrency(grossNum)}</span>
                </div>
                {showPayinCommissionDetail &&
                quoteTotalDeduction != null &&
                !Number.isNaN(quoteTotalDeduction) ? (
                  <div className="flex justify-between">
                    <span className="text-gray-600 dark:text-slate-400">Deductions</span>
                    <span className="font-semibold text-red-600 dark:text-red-400">-{formatCurrency(quoteTotalDeduction)}</span>
                  </div>
                ) : null}
                <div className="pt-3 border-t border-gray-300 dark:border-slate-600 flex justify-between">
                  <span className="font-semibold text-gray-900 dark:text-slate-100">Net credit</span>
                  <span className="font-bold text-blue-600 dark:text-blue-400 text-xl">{formatCurrency(netNum)}</span>
                </div>
              </div>
            </div>

            <div className="flex space-x-3">
              <Button onClick={() => setShowPaymentModal(false)} variant="outline" size="lg" fullWidth>
                Cancel
              </Button>
              <Button
                onClick={handleProceedToPayment}
                variant="primary"
                size="lg"
                fullWidth
                loading={loading}
                disabled={payInMaintenance}
              >
                Proceed to payment
              </Button>
            </div>
          </Card>
        </div>
      )}

      {showGatewayInterface && orderPayload && !payInMaintenance && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <div className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900 dark:text-slate-100">Checkout</h2>
                  <p className="text-sm text-gray-600 dark:text-slate-400 mt-1 capitalize">{orderPayload.provider}</p>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    if (
                      window.confirm('Are you sure you want to exit? Your transaction may stay pending until it expires.')
                    ) {
                      setShowGatewayInterface(false);
                      setOrderPayload(null);
                    }
                  }}
                  className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors"
                >
                  <FiX size={24} />
                </button>
              </div>

              <div className="p-4 bg-blue-50 dark:bg-blue-950/40 rounded-lg border border-blue-200 dark:border-blue-800 mb-6 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600 dark:text-slate-400">Amount</span>
                  <span className="font-bold text-blue-700 dark:text-blue-300">{formatCurrency(parseFloat(orderPayload.amount))}</span>
                </div>
                <div className="flex justify-between text-gray-600 dark:text-slate-400">
                  <span>Reference</span>
                  <span className="font-mono text-xs">{orderPayload.transaction_id}</span>
                </div>
                {orderPayload.payment_gateway_name ? (
                  <div className="flex justify-between text-gray-600 dark:text-slate-400">
                    <span>Gateway</span>
                    <span className="font-medium text-gray-800 dark:text-slate-200">{orderPayload.payment_gateway_name}</span>
                  </div>
                ) : null}
              </div>

              {orderPayload.provider === 'razorpay' && orderPayload.razorpay && (
                <div className="space-y-4">
                  <p className="text-sm text-gray-600 dark:text-slate-400">
                    After you pay, we verify the payment with Razorpay and credit your wallet immediately. In production,
                    also configure a Razorpay webhook to <span className="font-mono text-xs">/api/integrations/razorpay/webhook/</span>{' '}
                    on a public URL for redundancy.
                  </p>
                  <Button onClick={handleRazorpayPay} disabled={loading} loading={loading} variant="primary" size="lg" fullWidth>
                    Pay with Razorpay
                  </Button>
                </div>
              )}

              {orderPayload.provider === 'payu' && (
                <p className="text-sm text-amber-800 dark:text-amber-300 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg p-4">
                  PayU checkout is not enabled yet. Please choose a Razorpay package.
                </p>
              )}

              {!['razorpay', 'payu'].includes(orderPayload.provider) && (
                <p className="text-sm text-red-800 dark:text-red-300 bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 rounded-lg p-4">
                  Unknown provider "{orderPayload.provider}". Please contact support or select a different package.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      <FeedbackModal
        open={searchFeedbackModal.open}
        onClose={() => setSearchFeedbackModal((m) => ({ ...m, open: false }))}
        title={searchFeedbackModal.title}
        description={searchFeedbackModal.description}
        primaryAction={searchFeedbackModal.primaryAction}
      />
      <FeedbackModal
        open={payFeedbackModal.open}
        onClose={() => setPayFeedbackModal((m) => ({ ...m, open: false }))}
        title={payFeedbackModal.title}
        description={payFeedbackModal.description}
        primaryAction={payFeedbackModal.primaryAction}
        alternateAction={payFeedbackModal.alternateAction}
      />
    </div>
  );
};

export default LoadMoney;
