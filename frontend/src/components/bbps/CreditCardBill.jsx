import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { fetchBill, addTransaction, getWallets, calculateBBPSCharge } from '../../services/mockData';
import { formatCurrency, formatDate } from '../../utils/formatters';
import { validateMPIN } from '../../utils/validators';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import MPINModal from '../common/MPINModal';
import { FaCircleCheck, FaCircleExclamation, FaCreditCard, FaPhone, FaMagnifyingGlass } from 'react-icons/fa6';

const CreditCardBill = ({ onPaymentSuccess }) => {
  const { user } = useAuth();
  const [biller, setBiller] = useState('');
  const [cardLast4, setCardLast4] = useState('');
  const [mobile, setMobile] = useState('');
  const [billDetails, setBillDetails] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [paymentMPIN, setPaymentMPIN] = useState('');
  const [paymentAmountType, setPaymentAmountType] = useState('total'); // 'total', 'minimum', 'custom'
  const [customAmount, setCustomAmount] = useState('');
  const [bbpsWallet, setBbpsWallet] = useState(0);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);
  const [transactionId, setTransactionId] = useState('');

  useEffect(() => {
    if (user) {
      const walletResult = getWallets(user.id);
      if (walletResult && walletResult.success) {
        setBbpsWallet(walletResult.wallets.bbps || 0);
      }
    }
  }, [user]);

  const handleFetchBill = async () => {
    if (!biller || !cardLast4 || !mobile) {
      setError('Please fill all fields');
      return;
    }

    if (cardLast4.length !== 4 || !/^\d{4}$/.test(cardLast4)) {
      setError('Please enter last 4 digits of credit card');
      return;
    }

    if (mobile.length !== 10 || !/^\d{10}$/.test(mobile)) {
      setError('Please enter a valid 10-digit mobile number');
      return;
    }

    setLoading(true);
    setError('');
    setBillDetails(null);

    try {
      // Simulate API delay
      await new Promise((resolve) => setTimeout(resolve, 1500));

      const result = fetchBill(biller, cardLast4, mobile);
      if (result.success) {
        setBillDetails(result.bill);
      } else {
        setError(result.message || 'Bill not found');
      }
    } catch (err) {
      setError('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const getPaymentAmount = () => {
    if (!billDetails) return 0;
    if (paymentAmountType === 'total') {
      return billDetails.totalDueAmount;
    } else if (paymentAmountType === 'minimum') {
      return billDetails.minimumDueAmount;
    } else {
      return parseFloat(customAmount) || 0;
    }
  };

  const handlePayment = () => {
    if (!billDetails) return;
    const amount = getPaymentAmount();
    if (amount <= 0) {
      alert('Please select a valid payment amount');
      return;
    }
    setShowPaymentModal(true);
  };

  const handleMPINSubmit = async () => {
    const mpinValidation = validateMPIN(paymentMPIN);
    if (!mpinValidation.valid) {
      setError(mpinValidation.message);
      return;
    }

    if (!user || !billDetails) return;

    const amount = getPaymentAmount();
    const serviceCharge = calculateBBPSCharge(amount);
    const totalDeducted = amount + serviceCharge;

    // Check BBPS wallet balance
    if (bbpsWallet < totalDeducted) {
      setError(`Insufficient BBPS wallet balance. Required: ${formatCurrency(totalDeducted)}, Available: ${formatCurrency(bbpsWallet)}`);
      return;
    }

    setLoading(true);
    setError('');

    try {
      // Simulate payment processing delay
      await new Promise((resolve) => setTimeout(resolve, 2000));

      // Create transaction
      const transaction = {
        type: 'bbps',
        billType: 'Credit Card',
        biller: biller,
        billerId: biller.replace(/\s+/g, '').toUpperCase().substring(0, 10), // Generate biller ID from name
        amount: amount,
        charge: serviceCharge,
        status: 'SUCCESS',
        cardLast4: cardLast4,
        mobile: mobile,
      };

      const result = addTransaction(user.id, transaction);
      
      if (result.success) {
        setTransactionId(result.transaction.serviceId);
        setShowSuccessNotification(true);
        setShowPaymentModal(false);
        
        // Update wallet balance
        const walletResult = getWallets(user.id);
        if (walletResult && walletResult.success) {
          setBbpsWallet(walletResult.wallets.bbps || 0);
        }

        // Reset form after 3 seconds
        setTimeout(() => {
          setShowSuccessNotification(false);
          setBiller('');
          setCardLast4('');
          setMobile('');
          setBillDetails(null);
          setPaymentMPIN('');
          setPaymentAmountType('total');
          setCustomAmount('');
          if (onPaymentSuccess) {
            onPaymentSuccess();
          }
        }, 3000);
      } else {
        setError(result.message || 'Payment failed. Please try again.');
      }
    } catch (err) {
      setError('An error occurred during payment. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const serviceCharge = calculateBBPSCharge(getPaymentAmount());
  const totalDeducted = getPaymentAmount() + serviceCharge;

  return (
    <>
      {/* Success Notification */}
      {showSuccessNotification && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4 shadow-lg flex items-center space-x-3 min-w-[300px]">
            <FaCircleCheck className="text-green-600 flex-shrink-0" size={24} />
            <div>
              <p className="font-semibold text-green-800">Payment successful!</p>
              <p className="text-sm text-gray-700">Transaction ID: {transactionId}</p>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-6">
        {/* BBPS Wallet Balance */}
        <Card padding="lg">
          <div className="p-4 sm:p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-xl">
            <p className="text-sm font-medium text-gray-600 mb-2">Your BBPS Wallet Balance:</p>
            <p className="text-3xl font-bold text-blue-600">{formatCurrency(bbpsWallet)}</p>
          </div>
        </Card>

        <Card
          title="Credit Card Bill Payment"
          subtitle="Enter your credit card details to fetch and pay your bill"
          padding="lg"
        >

          {error && (
            <div className="mb-4 bg-red-50 border-2 border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center space-x-2">
              <FaCircleExclamation size={20} />
              <span>{error}</span>
            </div>
          )}

          <div className="space-y-6">
            {/* Biller Selection */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Select Biller <span className="text-red-500">*</span>
              </label>
              <select
                value={biller}
                onChange={(e) => {
                  setBiller(e.target.value);
                  setBillDetails(null);
                  setError('');
                }}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
              >
                <option value="">-- Select Biller --</option>
                <option value="Federal Bank Credit Card">Federal Bank Credit Card</option>
                <option value="HDFC Credit Card">HDFC Credit Card</option>
                <option value="ICICI Credit Card">ICICI Credit Card</option>
                <option value="SBI Credit Card">SBI Credit Card</option>
                <option value="Axis Bank Credit Card">Axis Bank Credit Card</option>
                <option value="Kotak Credit Card">Kotak Credit Card</option>
              </select>
            </div>

            {/* Last 4 digits */}
            <Input
              label="Last 4 digits of Credit Card"
              type="text"
              value={cardLast4}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 4);
                setCardLast4(value);
                setBillDetails(null);
                setError('');
              }}
              placeholder="Enter last 4 digits (e.g., 3998)"
              maxLength={4}
              icon={FaCreditCard}
              required
            />

            {/* Mobile Number */}
            <Input
              label="Registered Mobile Number"
              type="tel"
              value={mobile}
              onChange={(e) => {
                const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                setMobile(value);
                setBillDetails(null);
                setError('');
              }}
              placeholder="Enter 10-digit mobile number"
              maxLength={10}
              icon={FaPhone}
              required
            />

            {/* Fetch Bill Button */}
            <Button
              onClick={handleFetchBill}
              disabled={loading || !biller || cardLast4.length !== 4 || mobile.length !== 10}
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

        {/* Bill Details */}
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

            {/* Payment Amount Selection */}
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

            {/* Transaction Summary */}
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
                    <span className="font-semibold text-red-600">
                      +{formatCurrency(serviceCharge)}
                    </span>
                  </div>
                  <div className="flex justify-between items-center pt-3 bg-blue-50 p-3 rounded-lg">
                    <span className="text-lg font-bold text-gray-900">Total Deducted from BBPS Wallet:</span>
                    <span className="text-2xl font-bold text-red-600">
                      {formatCurrency(totalDeducted)}
                    </span>
                  </div>
                  {bbpsWallet < totalDeducted && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center space-x-2">
                      <FaCircleExclamation className="text-red-600" size={18} />
                      <p className="text-sm text-red-700">
                        Insufficient balance. Required: {formatCurrency(totalDeducted)}, Available: {formatCurrency(bbpsWallet)}
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
                paymentAmountType === 'custom' && (!customAmount || parseFloat(customAmount) <= 0) ||
                bbpsWallet < totalDeducted
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
      </div>

      {/* MPIN Modal */}
      <MPINModal
        isOpen={showPaymentModal && billDetails !== null}
        onClose={() => {
          setShowPaymentModal(false);
          setPaymentMPIN('');
          setError('');
        }}
        onVerify={(mpin) => {
          setPaymentMPIN(mpin);
          handleMPINSubmit();
        }}
        title={`Enter MPIN to Confirm Payment - ${formatCurrency(totalDeducted)}`}
        error={error}
        loading={loading}
      />
    </>
  );
};

export default CreditCardBill;
