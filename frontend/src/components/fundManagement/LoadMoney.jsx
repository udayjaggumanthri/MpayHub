import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { addTransaction, getPaymentGateways, calculateServiceCharge } from '../../services/mockData';
import { contactsAPI } from '../../services/api';
import { mapContactRow } from '../../utils/contactsHelpers';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import { formatCurrency } from '../../utils/formatters';
import { validateAmount } from '../../utils/validators';
import { FiSearch, FiMail, FiX } from 'react-icons/fi';
import { FaPhone, FaUser, FaDollarSign, FaCircleCheck, FaCreditCard, FaMobileScreenButton, FaGlobe, FaCircleExclamation } from 'react-icons/fa6';

const LoadMoney = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [phoneNumber, setPhoneNumber] = useState('');
  const [customerDetails, setCustomerDetails] = useState(null);
  const [gateway, setGateway] = useState('');
  const [amount, setAmount] = useState('');
  const [serviceCharge, setServiceCharge] = useState({ chargeRate: 0, charge: 0, netAmount: 0 });
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [showGatewayInterface, setShowGatewayInterface] = useState(false);
  const [selectedPaymentMethod, setSelectedPaymentMethod] = useState('');
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [gateways, setGateways] = useState([]);

  // Load available gateways based on user role
  useEffect(() => {
    if (user?.role) {
      const result = getPaymentGateways(user.role);
      if (result.success) {
        setGateways(result.gateways);
      }
    }
  }, [user]);

  // Payment methods for gateway interface
  const paymentMethods = [
    { id: 'upi', name: 'UPI', icon: FaMobileScreenButton, description: 'Pay using UPI ID or QR code' },
    { id: 'card', name: 'Cards', icon: FaCreditCard, description: 'Credit/Debit Cards' },
    { id: 'netbanking', name: 'Netbanking', icon: FaGlobe, description: 'Internet Banking' },
    { id: 'wallet', name: 'Wallets', icon: FaDollarSign, description: 'Paytm, PhonePe, etc.' },
  ];

  // Search customer by phone number
  const handlePhoneSearch = async () => {
    if (phoneNumber.length !== 10) {
      alert('Please enter a valid 10-digit phone number');
      return;
    }

    setSearching(true);
    try {
      const result = await contactsAPI.searchContactByPhone(phoneNumber);
      const row = result.success ? result.data?.contact : null;
      const mapped = mapContactRow(row);
      if (mapped) {
        setCustomerDetails(mapped);
      } else {
        alert(
          result.message ||
            'Contact not found. Add this person under User Management → Contacts, then search again.'
        );
        setCustomerDetails(null);
      }
    } catch (error) {
      alert('Error searching contact. Please try again.');
      setCustomerDetails(null);
    } finally {
      setSearching(false);
    }
  };

  // Calculate service charge when amount or gateway changes
  useEffect(() => {
    if (amount && parseFloat(amount) > 0 && gateway) {
      const chargeData = calculateServiceCharge(parseFloat(amount), gateway, 'payin');
      setServiceCharge(chargeData);
    } else {
      setServiceCharge({ chargeRate: 0, charge: 0, netAmount: 0 });
    }
  }, [amount, gateway]);

  // Safety check: Warn user if they try to leave during transaction
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
    if (!customerDetails) {
      alert('Please search and select a customer first');
      return;
    }
    if (!gateway) {
      alert('Please select a payment gateway');
      return;
    }
    setShowPaymentModal(true);
  };

  const handleProceedToPayment = () => {
    setShowPaymentModal(false);
    setShowGatewayInterface(true);
  };

  const handlePaymentMethodSelect = (methodId) => {
    setSelectedPaymentMethod(methodId);
  };

  const handlePayment = async () => {
    if (!selectedPaymentMethod) {
      alert('Please select a payment method');
      return;
    }

    setLoading(true);
    try {
      // Simulate payment gateway processing
      await new Promise((resolve) => setTimeout(resolve, 3000));

      // Add transaction to passbook
      const transaction = {
        type: 'payin',
        amount: parseFloat(amount),
        charge: serviceCharge.charge,
        netCredit: serviceCharge.netAmount,
        mode: gateway.toUpperCase(),
        paymentMethod: selectedPaymentMethod.toUpperCase(),
        status: 'SUCCESS',
        serviceId: `PAYIN${Date.now()}`,
        date: new Date(),
      };

      const result = addTransaction(user.id, transaction);
      if (result.success) {
        alert(`Payment successful! Net credit: ${formatCurrency(serviceCharge.netAmount)}`);
        // Reset form
        setAmount('');
        setGateway('');
        setCustomerDetails(null);
        setPhoneNumber('');
        setSelectedPaymentMethod('');
        setShowGatewayInterface(false);
        // Navigate to dashboard (wallets will auto-refresh)
        navigate('/dashboard');
      }
    } catch (error) {
      alert('Payment failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-4 sm:space-y-6 px-4 sm:px-0">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Load Money</h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600">Add funds to your wallet using payment gateway</p>
        </div>
      </div>

      {/* Customer Search Section */}
      <Card
        title="Customer Search"
        subtitle="Enter customer phone number to load money"
        padding="lg"
      >
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
            <div className="flex-1">
              <Input
                label="Enter Customer Phone Number"
                type="tel"
                icon={FaPhone}
                value={phoneNumber}
                onChange={(e) => {
                  const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                  setPhoneNumber(value);
                  setCustomerDetails(null);
                }}
                placeholder="Enter 10-digit phone number"
                maxLength={10}
                size="lg"
              />
            </div>
            <div className="flex items-end sm:items-end">
              <Button
                onClick={handlePhoneSearch}
                disabled={phoneNumber.length !== 10 || searching}
                loading={searching}
                icon={FiSearch}
                iconPosition="left"
                size="lg"
                fullWidth
                className="sm:w-auto"
              >
                Search
              </Button>
            </div>
          </div>

          {/* Customer Details - Pre-filled after search */}
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
                  <div className="space-y-2">
                    <div className="flex items-center space-x-2">
                      <FaUser className="text-blue-600" size={18} />
                      <p className="font-semibold text-gray-900">{customerDetails.name}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <FiMail className="text-blue-600" size={18} />
                      <p className="text-sm text-gray-600">
                        <span className="font-medium">{customerDetails.email}</span>
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

      {/* Payment Gateway & Amount Section */}
      {customerDetails && (
        <>
          {/* Gateway Selection - Dropdown */}
          <Card
            title="Select Payment Gateway"
            subtitle="Choose a payment gateway to process the transaction"
            padding="lg"
          >
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Payment Gateway <span className="text-red-500">*</span>
              </label>
              {gateways.length === 0 ? (
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <FaCircleExclamation className="text-yellow-600" size={20} />
                    <p className="text-yellow-800 font-medium">
                      No active payment gateways available. Please contact your administrator.
                    </p>
                  </div>
                </div>
              ) : (
                <>
                  <select
                    value={gateway}
                    onChange={(e) => setGateway(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
                  >
                    <option value="">-- Select Payment Gateway --</option>
                    {gateways.map((gw) => (
                      <option key={gw.id} value={gw.id}>
                        {gw.name} ({gw.chargeRate}% charge)
                      </option>
                    ))}
                  </select>
                  {gateway && (
                    <p className="mt-2 text-sm text-gray-500">
                      Service charge: {gateways.find((gw) => gw.id === gateway)?.chargeRate}% of transaction amount
                    </p>
                  )}
                </>
              )}
            </div>
          </Card>

          {/* Amount Input */}
          <Card
            title="Enter Amount (INR)"
            subtitle="Enter the amount you wish to load"
            padding="lg"
          >
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

              {/* Real-time Service Charge Calculation */}
              {amount && parseFloat(amount) > 0 && gateway && (
                <div className="p-6 bg-gray-50 rounded-xl border border-gray-200">
                  <h4 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">
                    Transaction Summary
                  </h4>
                  <div className="space-y-3">
                    <div className="flex justify-between items-center py-2 border-b border-gray-200">
                      <span className="text-gray-600">Amount Entered:</span>
                      <span className="font-semibold text-gray-900 text-lg">
                        {formatCurrency(parseFloat(amount))}
                      </span>
                    </div>
                    <div className="flex justify-between items-center py-2 border-b border-gray-200">
                      <span className="text-gray-600">
                        Service Charge ({serviceCharge.chargeRate}%):
                      </span>
                      <span className="font-semibold text-red-600">
                        -{formatCurrency(serviceCharge.charge)}
                      </span>
                    </div>
                    <div className="flex justify-between items-center pt-3 bg-blue-50 p-3 rounded-lg">
                      <span className="text-lg font-bold text-gray-900">Net Credit Amount:</span>
                      <span className="text-2xl font-bold text-blue-600">
                        {formatCurrency(serviceCharge.netAmount)}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <Button
                onClick={handleAmountSubmit}
                disabled={!amount || parseFloat(amount) <= 0 || !gateway}
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

      {/* Payment Confirmation Modal */}
      {showPaymentModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card
            className="max-w-md w-full border-2 border-blue-200 my-auto"
            padding="lg"
            shadow="xl"
          >
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 mb-4 sm:mb-6">Payment Confirmation</h2>

            <div className="space-y-3 sm:space-y-4 mb-4 sm:mb-6">
              <div className="p-4 bg-gray-50 rounded-lg">
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Customer:</span>
                    <span className="font-semibold text-gray-900">{customerDetails.name}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Amount:</span>
                    <span className="font-semibold text-gray-900">{formatCurrency(parseFloat(amount))}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Service Charge:</span>
                    <span className="font-semibold text-red-600">-{formatCurrency(serviceCharge.charge)}</span>
                  </div>
                  <div className="pt-3 border-t border-gray-300 flex justify-between">
                    <span className="font-semibold text-gray-900">Net Credit:</span>
                    <span className="font-bold text-blue-600 text-xl">
                      {formatCurrency(serviceCharge.netAmount)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Gateway:</span>
                    <span className="font-semibold">{gateways.find((gw) => gw.id === gateway)?.name}</span>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex space-x-3">
              <Button
                onClick={() => setShowPaymentModal(false)}
                variant="outline"
                size="lg"
                fullWidth
              >
                Cancel
              </Button>
              <Button
                onClick={handleProceedToPayment}
                variant="primary"
                size="lg"
                fullWidth
              >
                Proceed to Payment
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* Payment Gateway Interface Modal */}
      {showGatewayInterface && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-bold text-gray-900">Payment Gateway</h2>
                  <p className="text-sm text-gray-600 mt-1">
                    {gateways.find((gw) => gw.id === gateway)?.name}
                  </p>
                </div>
                <button
                  onClick={() => {
                    if (window.confirm('Are you sure you want to exit? Your transaction may be incomplete.')) {
                      setShowGatewayInterface(false);
                      setSelectedPaymentMethod('');
                    }
                  }}
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <FiX size={24} />
                </button>
              </div>

              {/* Transaction Summary */}
              <div className="p-4 bg-blue-50 rounded-lg border border-blue-200 mb-6">
                <div className="flex justify-between items-center">
                  <span className="text-gray-600">Amount to Pay:</span>
                  <span className="text-2xl font-bold text-blue-600">
                    {formatCurrency(parseFloat(amount))}
                  </span>
                </div>
                <div className="flex justify-between items-center mt-2 text-sm">
                  <span className="text-gray-500">Net Credit:</span>
                  <span className="font-semibold text-gray-700">
                    {formatCurrency(serviceCharge.netAmount)}
                  </span>
                </div>
              </div>

              {/* Payment Methods */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Select Payment Method</h3>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {paymentMethods.map((method) => {
                    const MethodIcon = method.icon;
                    const isSelected = selectedPaymentMethod === method.id;
                    return (
                      <button
                        key={method.id}
                        onClick={() => handlePaymentMethodSelect(method.id)}
                        className={`
                          p-5 rounded-2xl border-2 transition-all transform hover:scale-105 hover:-translate-y-1 text-left
                          ${isSelected
                            ? 'border-transparent bg-gradient-to-br from-blue-500 to-indigo-600 shadow-xl shadow-blue-200'
                            : 'border-blue-200 bg-white hover:border-blue-300 hover:shadow-lg hover:bg-blue-50'
                          }
                        `}
                      >
                        <div className="flex items-center space-x-3">
                          <div className={`p-3 rounded-xl ${isSelected ? 'bg-white/20 backdrop-blur-sm' : 'bg-blue-100 hover:bg-blue-200 transition-colors'}`}>
                            <MethodIcon className={isSelected ? 'text-white' : 'text-blue-600'} size={24} />
                          </div>
                          <div className="flex-1">
                            <p className={`font-bold ${isSelected ? 'text-white' : 'text-gray-900'} text-base`}>
                              {method.name}
                            </p>
                            <p className={`text-xs mt-1 ${isSelected ? 'text-white/90' : 'text-gray-600'}`}>{method.description}</p>
                          </div>
                          {isSelected && (
                            <FaCircleCheck className="text-white" size={22} />
                          )}
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Payment Action */}
              <div className="flex space-x-3 pt-4 border-t border-gray-200">
                <Button
                  onClick={() => {
                    if (window.confirm('Are you sure you want to exit? Your transaction may be incomplete.')) {
                      setShowGatewayInterface(false);
                      setSelectedPaymentMethod('');
                    }
                  }}
                  variant="outline"
                  size="lg"
                  fullWidth
                >
                  Cancel
                </Button>
                <Button
                  onClick={handlePayment}
                  disabled={!selectedPaymentMethod || loading}
                  loading={loading}
                  variant="primary"
                  size="lg"
                  fullWidth
                >
                  {loading ? 'Processing...' : 'Complete Payment'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default LoadMoney;
