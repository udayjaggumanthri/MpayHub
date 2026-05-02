import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { bbpsAPI, walletsAPI } from '../../services/api';
import { formatCurrency, formatDate } from '../../utils/formatters';
import { validateMPIN } from '../../utils/validators';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import MPINModal from '../common/MPINModal';
import { FaCircleCheck, FaCircleExclamation, FaMagnifyingGlass } from 'react-icons/fa6';
import BharatConnectBranding from './BharatConnectBranding';

const CreditCardBill = ({ category = 'credit-card', onPaymentSuccess }) => {
  const { user } = useAuth();
  const [biller, setBiller] = useState('');
  const [billDetails, setBillDetails] = useState(null);
  const [billId, setBillId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentAmountType, setPaymentAmountType] = useState('total');
  const [customAmount, setCustomAmount] = useState('');
  const [bbpsWallet, setBbpsWallet] = useState(0);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);
  const [transactionId, setTransactionId] = useState('');
  const [billerOptions, setBillerOptions] = useState([]);
  const [paymentMode, setPaymentMode] = useState('Cash');
  const [paymentChannel, setPaymentChannel] = useState('AGT');
  const [inputSchema, setInputSchema] = useState([]);
  const [inputValues, setInputValues] = useState({});
  const [quote, setQuote] = useState(null);
  const [lastReceipt, setLastReceipt] = useState(null);
  const [fetchRequestId, setFetchRequestId] = useState('');
  const [paymentModes, setPaymentModes] = useState([]);
  const [paymentModeChannelMap, setPaymentModeChannelMap] = useState({});
  const title = (category || 'bill-payment').replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());

  const getCanonicalValue = useCallback((canonicalKey, fallbackKeys = []) => {
    if (!canonicalKey) return '';
    const schemaHit = inputSchema.find((f) => f.canonical_key === canonicalKey);
    if (schemaHit && String(inputValues[schemaHit.param_name] || '').trim()) {
      return String(inputValues[schemaHit.param_name] || '').trim();
    }
    for (const key of fallbackKeys) {
      if (String(inputValues[key] || '').trim()) return String(inputValues[key] || '').trim();
    }
    return '';
  }, [inputSchema, inputValues]);

  const buildInputParams = useCallback(() => {
    if (inputSchema.length > 0) {
      return inputSchema
        .filter((p) => p.send_in_input_params !== false)
        .map((p) => ({
          paramName: p.param_name,
          paramValue: inputValues[p.param_name] || '',
        }))
        .filter((row) => String(row.paramName || '').trim() && String(row.paramValue || '').trim() !== '');
    }
    const fallback = [];
    if (String(inputValues['Customer Number'] || '').trim()) {
      fallback.push({ paramName: 'Customer Number', paramValue: inputValues['Customer Number'] });
    }
    return fallback;
  }, [inputSchema, inputValues]);

  const loadWallets = useCallback(async () => {
    const res = await walletsAPI.getWalletByType('bbps');
    if (res.success && res.data?.wallet) {
      setBbpsWallet(parseFloat(res.data.wallet.balance || 0));
    }
  }, []);

  useEffect(() => {
    if (user) loadWallets();
  }, [user, loadWallets]);

  useEffect(() => {
    const loadBillers = async () => {
      const bRes = await bbpsAPI.getBillers(category);
      if (bRes.success && Array.isArray(bRes.data?.billers)) {
        setBillerOptions(bRes.data.billers);
      } else {
        setBillerOptions([]);
      }
    };
    loadBillers();
  }, [category]);

  useEffect(() => {
    const loadSchema = async () => {
      if (!biller) {
        setPaymentModes([]);
        setPaymentModeChannelMap({});
        return;
      }
      const res = await bbpsAPI.getBillerSchema(biller);
      if (res.success) {
        const schema = res.data?.input_schema || [];
        setInputSchema(schema);
        const seed = {};
        schema.forEach((f) => {
          seed[f.param_name] = '';
        });
        setInputValues(seed);
        const modeList = Array.isArray(res.data?.payment_modes) ? res.data.payment_modes : [];
        const modeChannelMap = res.data?.payment_mode_channel_map || {};
        setPaymentModes(modeList);
        setPaymentModeChannelMap(modeChannelMap);
        const defMode = String(res.data?.default_payment_mode || modeList[0] || '').trim();
        const defCh = String(
          modeChannelMap[defMode] || res.data?.default_payment_channel || ''
        ).trim();
        if (defMode) {
          setPaymentMode(defMode);
        }
        if (defCh) {
          setPaymentChannel(defCh);
        }
        if (modeList.length === 0) {
          setError('No supported payment method is currently available for this biller. Please contact admin.');
        } else {
          setError('');
        }
      }
    };
    loadSchema();
  }, [biller]);

  useEffect(() => {
    if (!paymentModes.length) return;
    if (!paymentModes.includes(paymentMode)) {
      setPaymentMode(paymentModes[0]);
      return;
    }
    const mappedChannel = String(paymentModeChannelMap[paymentMode] || '').trim();
    if (mappedChannel && mappedChannel !== paymentChannel) {
      setPaymentChannel(mappedChannel);
    }
  }, [paymentMode, paymentChannel, paymentModes, paymentModeChannelMap]);

  const getPaymentAmount = React.useCallback(() => {
    if (!billDetails) return 0;
    if (paymentAmountType === 'total') return billDetails.totalDueAmount;
    if (paymentAmountType === 'minimum') return billDetails.minimumDueAmount;
    return parseFloat(customAmount) || 0;
  }, [billDetails, paymentAmountType, customAmount]);

  useEffect(() => {
    const loadQuote = async () => {
      if (!billDetails || !biller || getPaymentAmount() <= 0) return;
      const q = await bbpsAPI.getQuote({
        amount: getPaymentAmount(),
        biller_id: biller,
        bill_type: category,
      });
      if (q.success) setQuote(q.data || null);
    };
    loadQuote();
  }, [billDetails, biller, category, getPaymentAmount]);

  const validateInputs = () => {
    if (!biller) return 'Please select biller.';
    if (inputSchema.length === 0) {
      if (!String(inputValues['Customer Number'] || inputValues['Card Last4 Digits'] || '').trim()) {
        return 'Please enter customer identifier.';
      }
      if (!String(inputValues['Mobile Number'] || '').trim()) return 'Please enter Mobile Number.';
      return '';
    }
    for (const p of inputSchema) {
      const v = String(inputValues[p.param_name] || '').trim();
      if (!p.is_optional && !v) return `Please enter ${p.param_name}.`;
      if (v && p.min_length && v.length < p.min_length) return `${p.param_name} is too short.`;
      if (v && p.max_length && v.length > p.max_length) return `${p.param_name} is too long.`;
      if (p.canonical_key === 'mobile' && v && v.replace(/\D/g, '').length !== 10) {
        return `${p.param_name} must be 10 digits.`;
      }
    }
    return '';
  };

  const handleFetchBill = async () => {
    const invalid = validateInputs();
    if (invalid) {
      setError(invalid);
      return;
    }
    setLoading(true);
    setError('');
    setBillDetails(null);
    setBillId(null);
    setFetchRequestId('');
    try {
      const paramLookup = {
        ...inputValues,
        ...Object.fromEntries(
        inputSchema.map((f) => [f.param_name, inputValues[f.param_name] || ''])
        ),
      };
      const requestInputParams = buildInputParams();
      const result = await bbpsAPI.fetchBill(biller, {
        bill_type: category,
        input_params: requestInputParams,
        card_last4: paramLookup['Card Last4 Digits'] || undefined,
        mobile: getCanonicalValue('mobile', ['Mobile Number']),
        customer_number: getCanonicalValue('customer_number', ['Customer Number']),
      });
      if (result.success && result.data?.bill) {
        const bill = result.data.bill;
        setBillDetails({
          billerName: bill.biller_name || biller,
          billNumber: bill.bill_number || bill.billNumber || 'NA',
          billDate: bill.bill_date || bill.billDate || '',
          billPeriod: bill.bill_period || bill.billPeriod || '',
          name: bill.customer_name || bill.name || 'N/A',
          telephoneNumber: bill.mobile || paramLookup['Mobile Number'] || 'N/A',
          dueDate: bill.due_date,
          minimumDueAmount: parseFloat(bill.minimum_due || bill.minimumDueAmount || 0),
          totalDueAmount: parseFloat(bill.total_due || bill.totalDueAmount || 0),
        });
        setBillId(bill.id || null);
        setFetchRequestId(String(bill.request_id || bill.requestId || '').trim());
      } else {
        setError(result.message || 'Bill not found.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handlePayment = () => {
    if (!billDetails) return;
    if (!paymentMode || !paymentModes.includes(paymentMode)) {
      setError('Please select a supported payment method.');
      return;
    }
    if (!paymentChannel) {
      setError('No eligible payment channel found for selected method. Please choose another method.');
      return;
    }
    const amount = getPaymentAmount();
    if (amount <= 0) {
      setError('Please select a valid amount.');
      return;
    }
    if (!quote) {
      setError('Quote not ready. Please wait and retry.');
      return;
    }
    setShowPaymentModal(true);
  };

  const handleMPINSubmit = async (mpin) => {
    const mpinValidation = validateMPIN(mpin);
    if (!mpinValidation.valid) {
      setError(mpinValidation.message);
      return;
    }
    if (!user || !billDetails) return;
    const amount = getPaymentAmount();
    const totalDeducted = Number(quote?.total_deducted || amount);
    if (bbpsWallet < totalDeducted) {
      setError(`Insufficient BBPS wallet balance. Required: ${formatCurrency(totalDeducted)}, Available: ${formatCurrency(bbpsWallet)}`);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const inputParams = buildInputParams();
      const mobile = getCanonicalValue('mobile', ['Mobile Number']);
      const displayName = String(billDetails?.name || '').trim();
      const customerNameForPay = displayName && displayName.toUpperCase() !== 'N/A' ? displayName : '';
      const payerName = String(user?.name || '').trim();
      const customerInfo = { customerMobile: mobile };
      if (customerNameForPay) {
        customerInfo.customerName = customerNameForPay;
      }
      const result = await bbpsAPI.payBill({
        bill_id: billId || undefined,
        biller: biller,
        biller_id: biller,
        bill_type: category,
        amount,
        mpin,
        request_id: fetchRequestId || undefined,
        customer_name: customerNameForPay || undefined,
        remitter_name: payerName || undefined,
        payment_mode: paymentMode,
        init_channel: paymentChannel,
        input_params: inputParams,
        customer_info: customerInfo,
        customer_details: inputValues,
      });
      if (result.success) {
        const billPayment = result.data?.bill_payment || {};
        const txnAt = new Date().toISOString();
        setTransactionId(billPayment.service_id || billPayment.id || 'N/A');
        setLastReceipt({
          bConnectTxnId: billPayment.request_id || billPayment.service_id || 'N/A',
          txnRefId: billPayment.service_id || 'N/A',
          billerId: biller,
          billerName: billDetails?.billerName || biller,
          customerName: billDetails?.name || 'N/A',
          customerNumber: inputValues['Customer Number'] || inputValues['Mobile Number'] || 'N/A',
          billDate: billDetails?.billDate || '',
          billPeriod: billDetails?.billPeriod || 'NA',
          billNumber: billDetails?.billNumber || 'NA',
          dueDate: billDetails?.dueDate || '',
          billAmount: getPaymentAmount(),
          serviceCharge: serviceCharge,
          totalAmount: totalDeducted,
          paymentMode,
          initChannel: paymentChannel,
          status: 'SUCCESS',
          approvalNumber: billPayment.request_id || 'AB123456',
          txnAt,
        });
        setShowSuccessNotification(true);
        try {
          const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
          const osc = audioCtx.createOscillator();
          const gain = audioCtx.createGain();
          osc.connect(gain);
          gain.connect(audioCtx.destination);
          osc.frequency.value = 880;
          gain.gain.setValueAtTime(0.04, audioCtx.currentTime);
          osc.start();
          osc.stop(audioCtx.currentTime + 0.2);
        } catch (_) {}
        setShowPaymentModal(false);
        await loadWallets();
        setTimeout(() => {
          setShowSuccessNotification(false);
          setBiller('');
          setBillDetails(null);
          setBillId(null);
          setFetchRequestId('');
          setInputSchema([]);
          setInputValues({});
          setQuote(null);
          setPaymentAmountType('total');
          setCustomAmount('');
          if (onPaymentSuccess) onPaymentSuccess();
        }, 3000);
      } else {
        setError(result.message || 'Payment failed.');
      }
    } finally {
      setLoading(false);
    }
  };

  const serviceCharge = Number(quote?.applied_charge || 0);
  const totalDeducted = Number(quote?.total_deducted || (getPaymentAmount() + serviceCharge));

  return (
    <>
      {showSuccessNotification && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4 shadow-lg flex items-center space-x-3 min-w-[300px]">
            <FaCircleCheck className="text-green-600 flex-shrink-0" size={24} />
            <div>
              <BharatConnectBranding stage="stage3" />
              <p className="font-semibold text-green-800">Payment successful!</p>
              <p className="text-sm text-gray-700">Transaction ID: {transactionId}</p>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-6">
        <Card padding="lg">
          <div className="p-4 sm:p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-xl">
            <p className="text-sm font-medium text-gray-600 mb-2">Your BBPS Wallet Balance:</p>
            <p className="text-3xl font-bold text-blue-600">{formatCurrency(bbpsWallet)}</p>
          </div>
        </Card>

        <Card
          title={`${title} Bill Payment`}
          subtitle={`Enter ${title.toLowerCase()} details to fetch and pay`}
          padding="lg"
        >
          <BharatConnectBranding stage="stage2" />
          {error && (
            <div className="mb-4 bg-red-50 border-2 border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center space-x-2">
              <FaCircleExclamation size={20} />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Biller <span className="text-red-500">*</span>
              </label>
              <select
                value={biller}
                onChange={(e) => {
                  setBiller(e.target.value);
                  setBillDetails(null);
                  setBillId(null);
                  setFetchRequestId('');
                  setPaymentModes([]);
                  setPaymentModeChannelMap({});
                  setError('');
                }}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
              >
                <option value="">-- Select Biller --</option>
                {billerOptions.map((opt) => (
                  <option key={opt.biller_id || opt.id} value={opt.biller_id || opt.name}>
                    {opt.biller_name || opt.name}
                  </option>
                ))}
              </select>
              {billerOptions.length === 0 ? (
                <p className="mt-2 text-xs text-amber-700">
                  No active billers available for this category. Ask admin to sync and enable billers.
                </p>
              ) : null}
            </div>

            <div className="grid md:grid-cols-2 gap-4">
              <div className="md:col-span-2">
                <label className="block text-sm font-medium text-gray-700 mb-2">Payment method</label>
                <select
                  value={paymentMode}
                  onChange={(e) => setPaymentMode(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg"
                  disabled={!biller || paymentModes.length === 0}
                >
                  {paymentModes.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {biller ? (
              <p className="text-xs text-gray-600 -mt-2">
                Payment methods come from BillAvenue biller configuration. Payment channel is auto-selected in the
                background based on the selected method.
              </p>
            ) : null}
            {biller && paymentModes.length === 0 ? (
              <p className="text-xs text-amber-700 -mt-2">
                This biller currently has no method supported for assisted terminal payment. Ask admin to review biller
                mode/channel configuration.
              </p>
            ) : null}

            {inputSchema.length > 0 ? (
              <div className="grid md:grid-cols-2 gap-4">
                {inputSchema.map((f) => (
                  <Input
                    key={f.param_name}
                    label={`${f.param_name}${f.is_optional ? '' : ' *'}`}
                    type={f.canonical_key === 'mobile' ? 'tel' : 'text'}
                    value={inputValues[f.param_name] || ''}
                    onChange={(e) => {
                      const raw = e.target.value;
                      const next = f.canonical_key === 'mobile' ? raw.replace(/\D/g, '').slice(0, 10) : raw;
                      setInputValues((prev) => ({ ...prev, [f.param_name]: next }));
                    }}
                    placeholder={f.param_name}
                    required={!f.is_optional}
                  />
                ))}
              </div>
            ) : (
              <div className="grid md:grid-cols-2 gap-4">
                <Input
                  label="Customer Number *"
                  type="text"
                  value={inputValues['Customer Number'] || ''}
                  onChange={(e) =>
                    setInputValues((prev) => ({ ...prev, 'Customer Number': e.target.value }))
                  }
                  placeholder="Enter customer identifier"
                  required
                />
                <Input
                  label="Mobile Number *"
                  type="text"
                  value={inputValues['Mobile Number'] || ''}
                  onChange={(e) =>
                    setInputValues((prev) => ({ ...prev, 'Mobile Number': e.target.value.replace(/\D/g, '').slice(0, 10) }))
                  }
                  placeholder="Enter 10-digit mobile"
                  required
                />
              </div>
            )}

            <Button
              onClick={handleFetchBill}
              disabled={loading || !biller}
              loading={loading}
              icon={FaMagnifyingGlass}
              iconPosition="left"
              variant="primary"
              size="lg"
              fullWidth
            >
              Fetch Bill
            </Button>
          </div>
        </Card>

        {billDetails && (
          <Card
            title="Bill Details"
            subtitle="Review your bill information before proceeding to payment"
            padding="lg"
          >
            <div className="space-y-4">
              <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Name:</span>
                <span className="font-semibold text-gray-900">{billDetails.name}</span>
              </div>

              <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Telephone Number:</span>
                <span className="font-semibold text-gray-900">{billDetails.telephoneNumber}</span>
              </div>

              <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Due Date:</span>
                <span className="font-semibold text-gray-900">{formatDate(billDetails.dueDate)}</span>
              </div>

              <div className="flex justify-between items-center p-4 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Minimum Due Amount:</span>
                <span className="font-semibold text-gray-900">
                  {formatCurrency(billDetails.minimumDueAmount)}
                </span>
              </div>

              <div className="flex justify-between items-center p-4 bg-blue-50 border-2 border-blue-200 rounded-lg">
                <span className="text-gray-700 font-medium">Total Due Amount:</span>
                <span className="font-bold text-blue-600 text-xl">
                  {formatCurrency(billDetails.totalDueAmount)}
                </span>
              </div>

              <div className="mt-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
                <h4 className="text-sm font-semibold text-gray-900 mb-4">Select Payment Amount:</h4>
                <div className="space-y-3">
                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input
                      type="radio"
                      name="paymentAmount"
                      value="total"
                      checked={paymentAmountType === 'total'}
                      onChange={(e) => setPaymentAmountType(e.target.value)}
                      className="w-4 h-4 text-blue-600 focus:ring-blue-500"
                    />
                    <div className="flex-1">
                      <span className="text-sm font-medium text-gray-900">Total Due Amount</span>
                      <span className="ml-2 text-sm font-bold text-blue-600">
                        {formatCurrency(billDetails.totalDueAmount)}
                      </span>
                    </div>
                  </label>

                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input
                      type="radio"
                      name="paymentAmount"
                      value="minimum"
                      checked={paymentAmountType === 'minimum'}
                      onChange={(e) => setPaymentAmountType(e.target.value)}
                      className="w-4 h-4 text-blue-600 focus:ring-blue-500"
                    />
                    <div className="flex-1">
                      <span className="text-sm font-medium text-gray-900">Minimum Due Amount</span>
                      <span className="ml-2 text-sm font-bold text-green-600">
                        {formatCurrency(billDetails.minimumDueAmount)}
                      </span>
                    </div>
                  </label>

                  <label className="flex items-center space-x-3 cursor-pointer">
                    <input
                      type="radio"
                      name="paymentAmount"
                      value="custom"
                      checked={paymentAmountType === 'custom'}
                      onChange={(e) => setPaymentAmountType(e.target.value)}
                      className="w-4 h-4 text-blue-600 focus:ring-blue-500"
                    />
                    <div className="flex-1">
                      <span className="text-sm font-medium text-gray-900">Custom Amount</span>
                      {paymentAmountType === 'custom' && (
                        <input
                          type="number"
                          value={customAmount}
                          onChange={(e) => {
                            const value = parseFloat(e.target.value);
                            if (value >= 0 && value <= billDetails.totalDueAmount) {
                              setCustomAmount(e.target.value);
                            }
                          }}
                          placeholder="Enter amount"
                          min={0}
                          max={billDetails.totalDueAmount}
                          step="0.01"
                          className="ml-3 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 w-48"
                        />
                      )}
                    </div>
                  </label>
                </div>
              </div>

              {getPaymentAmount() > 0 && (
                <div className="mt-6 p-6 bg-gray-50 rounded-xl border border-gray-200">
                  <h4 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">
                    Transaction Summary
                  </h4>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center py-2 border-b border-gray-200">
                      <span className="text-gray-600">Bill Amount:</span>
                      <span className="font-semibold text-gray-900 text-lg">
                        {formatCurrency(getPaymentAmount())}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-gray-200">
                      <span className="text-gray-600">Service Charge:</span>
                      <span className="font-semibold text-red-600">+{formatCurrency(serviceCharge)}</span>
                    </div>
                    {quote?.shadow_mode && (
                      <div className="flex justify-between items-center py-2 border-b border-gray-200">
                        <span className="text-amber-800">Computed Charge (shadow):</span>
                        <span className="font-semibold text-amber-800">{formatCurrency(Number(quote?.computed_charge || 0))}</span>
                      </div>
                    )}
                    <div className="flex justify-between items-center pt-3 bg-blue-50 p-3 rounded-lg">
                      <span className="text-lg font-bold text-gray-900">Total Deducted from BBPS Wallet:</span>
                      <span className="text-2xl font-bold text-red-600">{formatCurrency(totalDeducted)}</span>
                    </div>
                    {bbpsWallet < totalDeducted && (
                      <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-2">
                        <FaCircleExclamation className="text-red-600" size={18} />
                        <p className="text-sm text-red-700">
                          Insufficient balance. Required: {formatCurrency(totalDeducted)}, Available:{' '}
                          {formatCurrency(bbpsWallet)}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>

            <Button
              onClick={handlePayment}
              disabled={
                (paymentAmountType === 'custom' && (!customAmount || parseFloat(customAmount) <= 0)) ||
                bbpsWallet < totalDeducted ||
                !quote
              }
              variant="primary"
              size="lg"
              fullWidth
              className="mt-6"
            >
              Proceed to Pay
            </Button>
          </Card>
        )}

        {lastReceipt && (
          <Card title="B-Connect Receipt" subtitle="Payment confirmation with enterprise receipt fields" padding="lg">
            <BharatConnectBranding stage="stage3" />
            <div className="grid md:grid-cols-2 gap-3 text-sm">
              <div className="border rounded p-2">B-Connect Transaction ID: <strong>{lastReceipt.bConnectTxnId}</strong></div>
              <div className="border rounded p-2">Transaction Ref ID: <strong>{lastReceipt.txnRefId}</strong></div>
              <div className="border rounded p-2">Biller ID: <strong>{lastReceipt.billerId}</strong></div>
              <div className="border rounded p-2">Biller Name: <strong>{lastReceipt.billerName}</strong></div>
              <div className="border rounded p-2">Customer Name: <strong>{lastReceipt.customerName}</strong></div>
              <div className="border rounded p-2">Customer Number: <strong>{lastReceipt.customerNumber}</strong></div>
              <div className="border rounded p-2">Bill Date: <strong>{formatDate(lastReceipt.billDate)}</strong></div>
              <div className="border rounded p-2">Bill Period: <strong>{lastReceipt.billPeriod}</strong></div>
              <div className="border rounded p-2">Bill Number: <strong>{lastReceipt.billNumber}</strong></div>
              <div className="border rounded p-2">Due Date: <strong>{formatDate(lastReceipt.dueDate)}</strong></div>
              <div className="border rounded p-2">Bill Amount: <strong>{formatCurrency(lastReceipt.billAmount)}</strong></div>
              <div className="border rounded p-2">Service Charge: <strong>{formatCurrency(lastReceipt.serviceCharge)}</strong></div>
              <div className="border rounded p-2">Total Amount: <strong>{formatCurrency(lastReceipt.totalAmount)}</strong></div>
              <div className="border rounded p-2">Payment Mode: <strong>{lastReceipt.paymentMode}</strong></div>
              <div className="border rounded p-2">Initiating Channel: <strong>{lastReceipt.initChannel}</strong></div>
              <div className="border rounded p-2">Status: <strong>{lastReceipt.status}</strong></div>
              <div className="border rounded p-2">Approval Number: <strong>{lastReceipt.approvalNumber}</strong></div>
              <div className="border rounded p-2 md:col-span-2">Transaction Date & Time: <strong>{formatDate(lastReceipt.txnAt)}</strong></div>
            </div>
          </Card>
        )}
      </div>

      <MPINModal
        isOpen={showPaymentModal && billDetails !== null}
        onClose={() => {
          setShowPaymentModal(false);
          setError('');
        }}
        onVerify={handleMPINSubmit}
        title={`Enter MPIN to Confirm Payment - ${formatCurrency(totalDeducted)}`}
        error={error}
        loading={loading}
      />
    </>
  );
};

export default CreditCardBill;
