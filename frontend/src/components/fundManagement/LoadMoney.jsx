import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { contactsAPI, fundManagementAPI } from '../../services/api';
import { mapContactRow } from '../../utils/contactsHelpers';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import FeedbackModal from '../common/FeedbackModal';
import ContactSearchTypeahead from './ContactSearchTypeahead';
import { formatCurrency } from '../../utils/formatters';
import { validateAmount } from '../../utils/validators';
import { useWallet } from '../../context/WalletContext';
import { FiSearch, FiMail, FiX, FiInfo } from 'react-icons/fi';
import { FaPhone, FaUser, FaDollarSign, FaCircleCheck, FaCircleExclamation } from 'react-icons/fa6';

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
  const { refreshWallets } = useWallet();
  const [customerSearch, setCustomerSearch] = useState('');
  const [customerDetails, setCustomerDetails] = useState(null);
  const [packages, setPackages] = useState([]);
  const [packagesLoading, setPackagesLoading] = useState(true);
  const [selectedPackageId, setSelectedPackageId] = useState('');
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
    let cancelled = false;
    (async () => {
      setPackagesLoading(true);
      const res = await fundManagementAPI.listPayInPackages();
      if (cancelled) return;
      const list = res.success && res.data?.packages ? res.data.packages : [];
      setPackages(list);
      setSelectedPackageId((prev) => {
        if (prev && list.some((p) => String(p.id) === String(prev))) return prev;
        return list.length ? String(list[0].id) : '';
      });
      setPackagesLoading(false);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const selectedPackage = packages.find((p) => String(p.id) === String(selectedPackageId)) || null;

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
  }, [selectedPackageId, amount]);

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
    if (!selectedPackageId) {
      alert('Please select a pay-in package');
      return;
    }
    if (quoteError || !quote) {
      alert(quoteError || 'Wait for a valid price quote, or adjust the amount.');
      return;
    }
    setShowPaymentModal(true);
  };

  const handleProceedToPayment = async () => {
    if (!customerDetails?.id || !selectedPackageId) return;
    setLoading(true);
    try {
      const res = await fundManagementAPI.payInCreateOrder({
        packageId: Number(selectedPackageId),
        amount: String(amount),
        contactId: customerDetails.id,
      });
      if (!res.success) {
        setPayFeedbackModal({
          open: true,
          title: 'Could not start payment',
          description: res.message || 'Order creation failed. Try again or contact support.',
          primaryAction: null,
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

  const handleMockComplete = async () => {
    const tid = orderPayload?.load_money?.transaction_id || orderPayload?.transaction_id;
    if (!tid) {
      alert('Missing transaction reference. Close and try again.');
      return;
    }
    setLoading(true);
    try {
      const res = await fundManagementAPI.payInCompleteMock(tid);
      if (res.success) {
        refreshWallets();
        const net = res.data?.load_money?.net_credit ?? quote?.net_credit;
        setShowGatewayInterface(false);
        setOrderPayload(null);
        setAmount('');
        setCustomerDetails(null);
        setCustomerSearch('');
        setQuote(null);
        setPayFeedbackModal({
          open: true,
          title: 'Payment completed',
          description: `Your wallet has been credited. Net credit: ${formatCurrency(parseFloat(net || 0))}.\n\nFull history: Reports → Pay In.`,
          primaryAction: {
            label: 'Open Pay In report',
            onClick: () => navigate('/reports/payin'),
          },
        });
      } else {
        setPayFeedbackModal({
          open: true,
          title: 'Completion failed',
          description: res.message || 'Mock completion failed.',
          primaryAction: null,
        });
      }
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

  return (
    <div className="max-w-5xl mx-auto space-y-4 sm:space-y-6 px-4 sm:px-0">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Load Money</h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600">
            Add funds using an admin-configured pay-in package (fees shown before you pay). Pay-in history lives under{' '}
            <span className="font-medium text-gray-800">Reports → Pay In</span>.
          </p>
        </div>
      </div>

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
            <div className="p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-xl">
              <div className="flex items-start space-x-4">
                <div className="flex-shrink-0">
                  <div className="w-14 h-14 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center shadow-lg">
                    <FaUser className="text-white" size={24} />
                  </div>
                </div>
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-3">
                    <FaCircleCheck className="text-green-600" size={22} />
                    <h3 className="text-lg font-bold text-gray-900">Contact Information</h3>
                  </div>
                  <p className="text-xs text-gray-600 mb-2">
                    Matched from your saved contacts — confirm identity before sending money.
                  </p>
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <FaUser className="text-blue-600" size={18} />
                      <p className="font-semibold text-gray-900">{customerDetails.name}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <FiMail className="text-blue-600" size={18} />
                      <p className="text-sm text-gray-600">
                        <span className="font-medium">{customerDetails.email || '—'}</span>
                      </p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <FaPhone className="text-blue-600" size={18} />
                      <p className="text-sm text-gray-600">
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
          <Card title="Pay-in package" subtitle="Fees follow the package profile set by operations" padding="lg">
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Package <span className="text-red-500">*</span>
              </label>
              {packagesLoading ? (
                <p className="text-sm text-gray-600">Loading packages…</p>
              ) : packages.length === 0 ? (
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center gap-2">
                  <FaCircleExclamation className="text-yellow-600 flex-shrink-0" size={20} />
                  <p className="text-yellow-800 text-sm">No pay-in packages configured. Contact your administrator.</p>
                </div>
              ) : (
                <>
                  <select
                    value={selectedPackageId}
                    onChange={(e) => setSelectedPackageId(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
                  >
                    {packages.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.display_name} ({p.provider})
                      </option>
                    ))}
                  </select>
                  {selectedPackage && (
                    <p className="text-sm text-gray-500">
                      Allowed amount: {formatCurrency(parseFloat(selectedPackage.min_amount))} –{' '}
                      {formatCurrency(parseFloat(selectedPackage.max_amount_per_txn))} per transaction
                    </p>
                  )}
                </>
              )}
            </div>
          </Card>

          <Card title="Enter amount (INR)" subtitle="Quote updates as you type" padding="lg">
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Amount (INR) <span className="text-red-500">*</span>
                </label>
                <Input
                  type="number"
                  icon={FaDollarSign}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="Enter amount (e.g., 10000)"
                  min="1"
                  step="0.01"
                  size="lg"
                />
              </div>

              {quoteLoading && (
                <p className="text-sm text-gray-600">Calculating fees…</p>
              )}
              {quoteError && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-800 text-sm">{quoteError}</div>
              )}

              {quote && !quoteError && grossNum > 0 && (
                <div className="space-y-4">
                  <div className="p-6 bg-gray-50 rounded-xl border border-gray-200">
                    <h4 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">Summary</h4>
                    <div className="space-y-3">
                      <div className="flex justify-between items-center py-2 border-b border-gray-200">
                        <span className="text-gray-600">You pay (gross)</span>
                        <span className="font-semibold text-gray-900 text-lg">{formatCurrency(grossNum)}</span>
                      </div>
                      <div className="flex justify-between items-center py-2 border-b border-gray-200">
                        <span className="text-gray-600">Total deductions (gateway + platform + upline)</span>
                        <span className="font-semibold text-red-600">-{formatCurrency(parseFloat(quote.total_deduction))}</span>
                      </div>
                      {absorbedRetailerShare > 0 ? (
                        <p className="text-xs text-gray-600 bg-slate-50 border border-slate-200 rounded-lg px-3 py-2">
                          The package’s retailer commission rate ({quote.breakdown?.retailer_commission_pct ?? '—'}%) is
                          included in the <strong>Admin (platform)</strong> share — it is not added to your commission
                          wallet.
                        </p>
                      ) : null}
                      <div className="flex justify-between items-center pt-3 bg-blue-50 p-3 rounded-lg">
                        <span className="text-lg font-bold text-gray-900">Net credit (main wallet)</span>
                        <span className="text-2xl font-bold text-blue-600">{formatCurrency(netNum)}</span>
                      </div>
                    </div>
                  </div>

                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setShowPriceBreakdown((v) => !v)}
                      className="inline-flex items-center gap-2 text-sm font-medium text-blue-700 hover:text-blue-900"
                    >
                      <FiInfo size={18} />
                      {showPriceBreakdown ? 'Hide price breakdown' : 'Prices — full breakdown'}
                    </button>
                    {showPriceBreakdown && quote.lines && (
                      <div className="mt-3 space-y-2">
                        {quote.breakdown?.hierarchy_adjusted ? (
                          <p className="text-xs text-gray-600 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
                            Your upline does not include every distributor tier in the package. Missing tiers roll
                            up to the nearest present upline (Distributor → Master → Super); any remainder is in the{' '}
                            <strong>Admin (platform)</strong> row. Net credit and total deductions follow your Gateway
                            pay-in package settings.
                          </p>
                        ) : null}
                        <div className="border border-gray-200 rounded-xl overflow-hidden shadow-sm bg-white">
                          <table className="w-full text-sm">
                            <thead className="bg-gray-100">
                              <tr>
                                <th className="text-left p-3 font-semibold text-gray-700">Component</th>
                                <th className="text-right p-3 font-semibold text-gray-700">%</th>
                                <th className="text-right p-3 font-semibold text-gray-700">Amount</th>
                              </tr>
                            </thead>
                            <tbody>
                              {quote.lines.map((line) => (
                                <tr key={line.key} className="border-t border-gray-100">
                                  <td className="p-3 text-gray-800">
                                    <span className="block">{line.label}</span>
                                    {line.note ? (
                                      <span className="mt-1 block text-xs font-normal text-gray-500">{line.note}</span>
                                    ) : null}
                                  </td>
                                  <td className="p-3 text-right text-gray-600 align-top">{line.pct}%</td>
                                  <td className="p-3 text-right font-medium text-gray-900 align-top">
                                    {formatCurrency(parseFloat(line.amount))}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <Button
                onClick={handleAmountSubmit}
                disabled={
                  !amount ||
                  parseFloat(amount) <= 0 ||
                  !selectedPackageId ||
                  !quote ||
                  !!quoteError ||
                  quoteLoading
                }
                variant="primary"
                size="lg"
                fullWidth
                icon={FaDollarSign}
                iconPosition="left"
              >
                PAY NOW
              </Button>
            </div>
          </Card>
        </>
      )}

      {showPaymentModal && quote && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-md w-full border-2 border-blue-200 my-auto" padding="lg" shadow="xl">
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 mb-4 sm:mb-6">Payment confirmation</h2>

            <div className="space-y-3 sm:space-y-4 mb-4 sm:mb-6">
              <div className="p-4 bg-gray-50 rounded-lg space-y-3">
                <div className="flex justify-between">
                  <span className="text-gray-600">Customer</span>
                  <span className="font-semibold text-gray-900">{customerDetails.name}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Package</span>
                  <span className="font-semibold text-gray-900 text-right max-w-[60%]">
                    {selectedPackage?.display_name}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Gross</span>
                  <span className="font-semibold text-gray-900">{formatCurrency(grossNum)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Deductions</span>
                  <span className="font-semibold text-red-600">-{formatCurrency(parseFloat(quote.total_deduction))}</span>
                </div>
                <div className="pt-3 border-t border-gray-300 flex justify-between">
                  <span className="font-semibold text-gray-900">Net credit</span>
                  <span className="font-bold text-blue-600 text-xl">{formatCurrency(netNum)}</span>
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
              >
                Proceed to payment
              </Button>
            </div>
          </Card>
        </div>
      )}

      {showGatewayInterface && orderPayload && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Checkout</h2>
                  <p className="text-sm text-gray-600 mt-1">
                    {orderPayload.provider === 'mock' ? 'Mock provider (development)' : orderPayload.provider}
                  </p>
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
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <FiX size={24} />
                </button>
              </div>

              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200 mb-6 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Amount</span>
                  <span className="font-bold text-blue-700">{formatCurrency(parseFloat(orderPayload.amount))}</span>
                </div>
                <div className="flex justify-between text-gray-600">
                  <span>Reference</span>
                  <span className="font-mono text-xs">{orderPayload.transaction_id}</span>
                </div>
              </div>

              {orderPayload.provider === 'mock' && (
                <div className="space-y-4">
                  <p className="text-sm text-gray-600">
                    No real bank call is made. Complete simulation to credit wallets using the mock completion API.
                  </p>
                  <Button
                    onClick={handleMockComplete}
                    disabled={loading}
                    loading={loading}
                    variant="primary"
                    size="lg"
                    fullWidth
                  >
                    Complete simulated payment
                  </Button>
                </div>
              )}

              {orderPayload.provider === 'razorpay' && orderPayload.razorpay && (
                <div className="space-y-4">
                  <p className="text-sm text-gray-600">
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
                <p className="text-sm text-amber-800 bg-amber-50 border border-amber-200 rounded-lg p-4">
                  PayU checkout is not enabled for this build. Choose a mock or Razorpay package.
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
      />
    </div>
  );
};

export default LoadMoney;
