import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import {
  getBankAccounts,
  addTransaction,
  getWallets,
  getPayoutGateways,
  getContactByPhone,
  validateBankAccount,
  mockBankAccounts,
} from '../../services/mockData';
import MPINModal from '../common/MPINModal';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import { formatCurrency } from '../../utils/formatters';
import { validateAmount } from '../../utils/validators';
import { formatAccountNumber } from '../../utils/formatters';
import { FaPhone, FaUser, FaEnvelope, FaCircleCheck, FaPlus, FaMagnifyingGlass, FaCircleExclamation, FaDollarSign } from 'react-icons/fa6';

const Payout = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [bankAccounts, setBankAccounts] = useState([]);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [beneficiaryDetails, setBeneficiaryDetails] = useState(null);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [amount, setAmount] = useState('');
  const [transferMethod, setTransferMethod] = useState('IMPS');
  const [payoutGateway, setPayoutGateway] = useState('');
  const [payoutGateways, setPayoutGateways] = useState([]);
  const [showMPINModal, setShowMPINModal] = useState(false);
  const [mpinError, setMpinError] = useState('');
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [wallets, setWallets] = useState({ main: 0 });
  const [showAddBankAccount, setShowAddBankAccount] = useState(false);
  const [newBankAccount, setNewBankAccount] = useState({
    bankName: '',
    ifsc: '',
    accountNumber: '',
  });
  const [validatingAccount, setValidatingAccount] = useState(false);
  const [validatedBeneficiary, setValidatedBeneficiary] = useState(null);
  const [showValidationModal, setShowValidationModal] = useState(false);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);

  // Common bank names for dropdown
  const bankNames = [
    'HDFC BANK',
    'ICICI BANK',
    'STATE BANK OF INDIA',
    'AXIS BANK',
    'KOTAK MAHINDRA BANK',
    'UNION BANK OF INDIA',
    'PUNJAB NATIONAL BANK',
    'BANK OF BARODA',
    'CANARA BANK',
    'INDIAN BANK',
  ];

  useEffect(() => {
    if (user) {
      const result = getBankAccounts(user.id);
      if (result.success) {
        setBankAccounts(result.accounts || []);
      }

      // Get wallet balance
      const walletResult = getWallets(user.id);
      if (walletResult && walletResult.success) {
        setWallets(walletResult.wallets);
      }

      // Get payout gateways
      const gatewayResult = getPayoutGateways(user.role);
      if (gatewayResult.success) {
        setPayoutGateways(gatewayResult.gateways);
      }
    }
  }, [user]);

  const maxEligibleAmount = wallets.main;

  // Search beneficiary by phone number
  const handlePhoneSearch = async () => {
    if (phoneNumber.length !== 10) {
      alert('Please enter a valid 10-digit phone number');
      return;
    }

    setSearching(true);
    try {
      // Simulate API call
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Try to find contact by phone
      const contactResult = getContactByPhone(user.id, phoneNumber);
      if (contactResult.success) {
        setBeneficiaryDetails({
          name: contactResult.contact.name,
          email: contactResult.contact.email,
          phone: phoneNumber,
        });
      } else {
        // If contact not found, create mock beneficiary
        setBeneficiaryDetails({
          name: 'MURALI PATNALA',
          email: 'murali@example.com',
          phone: phoneNumber,
        });
      }
    } catch (error) {
      alert('Error searching for beneficiary. Please try again.');
    } finally {
      setSearching(false);
    }
  };

  // Validate and add new bank account
  const handleValidateAccount = async () => {
    if (!newBankAccount.bankName || !newBankAccount.ifsc || !newBankAccount.accountNumber) {
      alert('Please fill in all required fields');
      return;
    }

    setValidatingAccount(true);
    try {
      const result = await validateBankAccount(user.id, newBankAccount.accountNumber, newBankAccount.ifsc);
      if (result.success) {
        setValidatedBeneficiary(result.beneficiaryName);
        setShowValidationModal(true);
      } else {
        alert('Account validation failed. Please check the details.');
      }
    } catch (error) {
      alert('Error validating account. Please try again.');
    } finally {
      setValidatingAccount(false);
    }
  };

  // Save validated bank account
  const handleSaveBankAccount = () => {
    const newAccount = {
      id: `acc_${Date.now()}`,
      accountNumber: newBankAccount.accountNumber,
      ifsc: newBankAccount.ifsc.toUpperCase(),
      bankName: newBankAccount.bankName,
      accountHolderName: validatedBeneficiary,
      validated: true,
      beneficiaryName: validatedBeneficiary,
      phone: beneficiaryDetails?.phone || phoneNumber,
      email: beneficiaryDetails?.email || '',
    };

    if (!mockBankAccounts[user.id]) {
      mockBankAccounts[user.id] = [];
    }
    mockBankAccounts[user.id].push(newAccount);

    setBankAccounts([...bankAccounts, newAccount]);
    setSelectedAccount(newAccount);
    setShowValidationModal(false);
    setShowAddBankAccount(false);
    setShowSuccessNotification(true);
    setNewBankAccount({ bankName: '', ifsc: '', accountNumber: '' });
    setValidatedBeneficiary(null);

    // Hide success notification after 3 seconds
    setTimeout(() => {
      setShowSuccessNotification(false);
    }, 3000);
  };

  const handlePayoutSubmit = () => {
    const amountValidation = validateAmount(parseFloat(amount));
    if (!amountValidation.valid) {
      alert(amountValidation.message);
      return;
    }

    if (parseFloat(amount) > maxEligibleAmount) {
      alert(`Amount exceeds maximum eligible amount of ${formatCurrency(maxEligibleAmount)}`);
      return;
    }

    if (!beneficiaryDetails) {
      alert('Please search and select a beneficiary first');
      return;
    }

    if (!selectedAccount) {
      alert('Please select or add a bank account');
      return;
    }

    if (!payoutGateway) {
      alert('Please select a payout gateway');
      return;
    }

    setShowMPINModal(true);
  };

  const handleMPINVerify = async (mpin) => {
    setMpinError('');
    setLoading(true);

    try {
      // Verify MPIN (mock)
      await new Promise((resolve) => setTimeout(resolve, 1000));

      // Process payout
      const charge = parseFloat(amount) * 0.001; // 0.1% charge
      const platformFee = 2.5;
      const totalDeducted = parseFloat(amount) + charge + platformFee;

      const transaction = {
        type: 'payout',
        amount: parseFloat(amount),
        charge: charge,
        platformFee: platformFee,
        totalAmount: totalDeducted,
        status: 'SUCCESS',
        accountNumber: selectedAccount.accountNumber,
        bankName: selectedAccount.bankName,
        ifsc: selectedAccount.ifsc,
        transferMethod: transferMethod,
        gatewayName: payoutGateways.find((gw) => gw.id === payoutGateway)?.name || 'IDFC Payout',
        operatorId: payoutGateways.find((gw) => gw.id === payoutGateway)?.name || 'IDFC Payout',
      };

      const result = addTransaction(user.id, transaction);
      if (result.success) {
        alert(`Payout successful! Amount: ${formatCurrency(parseFloat(amount))}`);
        // Reset form
        setAmount('');
        setPhoneNumber('');
        setBeneficiaryDetails(null);
        setSelectedAccount(null);
        setPayoutGateway('');
        setShowMPINModal(false);
        navigate('/dashboard');
      }
    } catch (error) {
      setMpinError('Invalid MPIN. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Success Notification */}
      {showSuccessNotification && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4 shadow-lg flex items-center space-x-3 min-w-[300px]">
            <FaCircleCheck className="text-green-600 flex-shrink-0" size={24} />
            <div>
              <p className="font-semibold text-green-800">Bank account verified successfully!</p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto space-y-4 sm:space-y-6 px-4 sm:px-0">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Payout (Withdraw Funds)</h1>
            <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600">
              Transfer funds to beneficiary bank accounts via IMPS, NEFT, or RTGS
            </p>
          </div>
        </div>

        {/* Maximum Eligible Payout Amount */}
        <Card padding="lg">
          <div className="p-4 sm:p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-xl">
            <p className="text-sm font-medium text-gray-600 mb-2">Maximum Eligible Payout Amount:</p>
            <p className="text-3xl font-bold text-blue-600">{formatCurrency(maxEligibleAmount)}</p>
          </div>
        </Card>

        {/* Phone Number Search */}
        <Card
          title="Search Beneficiary"
          subtitle="Enter beneficiary phone number to load their information"
          padding="lg"
        >
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row gap-3 sm:gap-4">
              <div className="flex-1">
                <Input
                  label="Enter Beneficiary Phone Number"
                  type="tel"
                  icon={FaPhone}
                  value={phoneNumber}
                  onChange={(e) => {
                    const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                    setPhoneNumber(value);
                    setBeneficiaryDetails(null);
                    setSelectedAccount(null);
                  }}
                  placeholder="Enter 10-digit phone number"
                  maxLength={10}
                  size="lg"
                />
              </div>
              <div className="flex items-end">
                <Button
                  onClick={handlePhoneSearch}
                  disabled={phoneNumber.length !== 10 || searching}
                  loading={searching}
                  icon={FaMagnifyingGlass}
                  iconPosition="left"
                  size="lg"
                  fullWidth
                  className="sm:w-auto"
                >
                  Search
                </Button>
              </div>
            </div>

            {/* Contact Information */}
            {beneficiaryDetails && (
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
                        <p className="font-semibold text-gray-900">{beneficiaryDetails.name}</p>
                      </div>
                      {beneficiaryDetails.email && (
                        <div className="flex items-center space-x-2">
                          <FaEnvelope className="text-blue-600" size={18} />
                          <p className="text-sm text-gray-600">
                            <span className="font-medium">{beneficiaryDetails.email}</span>
                          </p>
                        </div>
                      )}
                      <div className="flex items-center space-x-2">
                        <FaPhone className="text-blue-600" size={18} />
                        <p className="text-sm text-gray-600">
                          <span className="font-medium">{beneficiaryDetails.phone}</span>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Beneficiary List / Bank Account Selection */}
        {beneficiaryDetails && (
          <div>
            <Card
              title="Select Bank Account"
              subtitle="Choose from saved accounts or add a new one"
              padding="lg"
            >
            <div className="space-y-4">
              {bankAccounts.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Beneficiary List
                  </label>
                  <select
                    value={selectedAccount?.id || ''}
                    onChange={(e) => {
                      const account = bankAccounts.find((acc) => acc.id === e.target.value);
                      setSelectedAccount(account || null);
                      setShowAddBankAccount(false);
                    }}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
                  >
                    <option value="">-- Select Bank Account --</option>
                    {bankAccounts.map((account) => (
                      <option key={account.id} value={account.id}>
                        {account.bankName} - A/C: {formatAccountNumber(account.accountNumber)} ({account.accountHolderName})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {selectedAccount && (
                <div className="p-4 bg-gray-50 border border-gray-200 rounded-lg">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-semibold text-gray-900">
                        {selectedAccount.bankName} - A/C: {formatAccountNumber(selectedAccount.accountNumber)}
                      </p>
                      <p className="text-sm text-gray-600 mt-1">IFSC: {selectedAccount.ifsc}</p>
                      <p className="text-sm text-gray-600">Account Holder: {selectedAccount.accountHolderName}</p>
                    </div>
                    {selectedAccount.validated && (
                      <FaCircleCheck className="text-green-600" size={24} />
                    )}
                  </div>
                </div>
              )}

              {/* Add Bank Account Section */}
              {!selectedAccount && (
                <div className="border-t border-gray-200 pt-4">
                  <button
                    onClick={() => setShowAddBankAccount(!showAddBankAccount)}
                    className="flex items-center space-x-2 text-blue-600 hover:text-blue-700 font-medium"
                  >
                    <FaPlus size={18} />
                    <span>Add Bank Account</span>
                  </button>

                  {showAddBankAccount && (
                    <div className="mt-4 p-4 bg-gray-50 border border-gray-200 rounded-lg space-y-4">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Bank Name <span className="text-red-500">*</span>
                        </label>
                        <select
                          value={newBankAccount.bankName}
                          onChange={(e) =>
                            setNewBankAccount({ ...newBankAccount, bankName: e.target.value })
                          }
                          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
                        >
                          <option value="">-- Select Bank --</option>
                          {bankNames.map((bank) => (
                            <option key={bank} value={bank}>
                              {bank}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          IFSC Code <span className="text-red-500">*</span>
                        </label>
                        <Input
                          value={newBankAccount.ifsc}
                          onChange={(e) => {
                            const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '');
                            setNewBankAccount({ ...newBankAccount, ifsc: value });
                          }}
                          placeholder="Enter IFSC code (e.g., UBI00812455)"
                          maxLength={11}
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Account Number <span className="text-red-500">*</span>
                        </label>
                        <Input
                          value={newBankAccount.accountNumber}
                          onChange={(e) => {
                            const value = e.target.value.replace(/\D/g, '');
                            setNewBankAccount({ ...newBankAccount, accountNumber: value });
                          }}
                          placeholder="Enter account number"
                        />
                      </div>

                      <Button
                        onClick={handleValidateAccount}
                        disabled={validatingAccount || !newBankAccount.bankName || !newBankAccount.ifsc || !newBankAccount.accountNumber}
                        loading={validatingAccount}
                        variant="primary"
                        size="lg"
                        fullWidth
                      >
                        Validate Account
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </Card>

            {/* Payout Gateway Selection */}
            {selectedAccount && (
              <Card
                title="Select Payout Gateway"
                subtitle="Choose a payout gateway to process the transaction"
                padding="lg"
              >
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Payout Gateway <span className="text-red-500">*</span>
                </label>
                <select
                  value={payoutGateway}
                  onChange={(e) => setPayoutGateway(e.target.value)}
                  className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
                >
                  <option value="">-- Select Payout Gateway --</option>
                  {payoutGateways.map((gw) => (
                    <option key={gw.id} value={gw.id}>
                      {gw.name}
                    </option>
                  ))}
                </select>
              </div>
              </Card>
            )}

            {/* Transfer Method Selection */}
            {selectedAccount && (
              <Card
                title="Select Transfer Method"
                subtitle="Choose IMPS, NEFT, or RTGS"
                padding="lg"
              >
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
                {['IMPS', 'NEFT', 'RTGS'].map((method) => (
                  <button
                    key={method}
                    onClick={() => setTransferMethod(method)}
                    className={`p-4 sm:p-5 border-2 rounded-xl transition-all transform hover:scale-105 ${
                      transferMethod === method
                        ? 'border-blue-500 bg-gradient-to-br from-blue-50 to-indigo-50 shadow-lg'
                        : 'border-gray-300 hover:border-gray-400 bg-white'
                    }`}
                  >
                    <p className="font-bold text-gray-900 text-base sm:text-lg">{method}</p>
                    {transferMethod === method && (
                      <FaCircleCheck className="text-blue-600 mt-2 mx-auto" size={20} />
                    )}
                  </button>
                ))}
              </div>
              </Card>
            )}

            {/* Amount Input */}
            {selectedAccount && (
              <Card
                title="Enter Amount"
                subtitle="Enter the amount you wish to transfer"
                padding="lg"
              >
              <div className="space-y-6">
                <div>
                  <Input
                    label="Amount (INR)"
                    type="number"
                    icon={FaDollarSign}
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="Enter amount"
                    min="1"
                    max={maxEligibleAmount}
                    step="0.01"
                    size="lg"
                  />
                </div>

                {/* Transaction Summary */}
                {amount && parseFloat(amount) > 0 && (
                  <div className="p-6 bg-gray-50 rounded-xl border border-gray-200">
                    <h4 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">
                      Transaction Summary
                    </h4>
                    <div className="space-y-3">
                      <div className="flex justify-between items-center py-2 border-b border-gray-200">
                        <span className="text-gray-600">Amount:</span>
                        <span className="font-semibold text-gray-900 text-lg">
                          {formatCurrency(parseFloat(amount))}
                        </span>
                      </div>
                      <div className="flex justify-between items-center py-2 border-b border-gray-200">
                        <span className="text-gray-600">Transfer Charge (0.1%):</span>
                        <span className="font-semibold text-red-600">
                          -{formatCurrency(parseFloat(amount) * 0.001)}
                        </span>
                      </div>
                      <div className="flex justify-between items-center py-2 border-b border-gray-200">
                        <span className="text-gray-600">Platform Fee:</span>
                        <span className="font-semibold text-red-600">-{formatCurrency(2.5)}</span>
                      </div>
                      <div className="flex justify-between items-center pt-3 bg-red-50 p-3 rounded-lg">
                        <span className="text-lg font-bold text-gray-900">Total Deducted:</span>
                        <span className="text-2xl font-bold text-red-600">
                          {formatCurrency(parseFloat(amount) + parseFloat(amount) * 0.001 + 2.5)}
                        </span>
                      </div>
                    </div>
                  </div>
                )}

                <Button
                  onClick={handlePayoutSubmit}
                  disabled={!amount || parseFloat(amount) <= 0 || !payoutGateway}
                  variant="primary"
                  size="lg"
                  fullWidth
                >
                  PAY NOW
                </Button>
              </div>
              </Card>
            )}
          </div>
        )}

      {/* Validation Confirmation Modal */}
      {showValidationModal && validatedBeneficiary && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-md w-full border-2 border-blue-200 my-auto" padding="lg" shadow="xl">
            <h2 className="text-xl sm:text-2xl font-bold text-gray-900 mb-4 sm:mb-6">Confirm Beneficiary</h2>

            <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg mb-6">
              <p className="text-sm text-gray-600 mb-2">Beneficiary Name:</p>
              <p className="text-xl font-bold text-gray-900">{validatedBeneficiary}</p>
              <p className="text-sm text-gray-600 mt-2">
                Account: {formatAccountNumber(newBankAccount.accountNumber)}
              </p>
              <p className="text-sm text-gray-600">IFSC: {newBankAccount.ifsc}</p>
              <p className="text-sm text-gray-600">Bank: {newBankAccount.bankName}</p>
            </div>

            <div className="flex space-x-3">
              <Button
                onClick={() => {
                  setShowValidationModal(false);
                  setValidatedBeneficiary(null);
                }}
                variant="outline"
                size="lg"
                fullWidth
              >
                Cancel
              </Button>
              <Button onClick={handleSaveBankAccount} variant="primary" size="lg" fullWidth>
                Save Account
              </Button>
            </div>
          </Card>
        </div>
      )}

      {/* MPIN Modal */}
      <MPINModal
        isOpen={showMPINModal}
        onClose={() => {
          setShowMPINModal(false);
          setMpinError('');
        }}
        onVerify={handleMPINVerify}
        title="Enter MPIN to Confirm Payout"
        error={mpinError}
      />
      </div>
    </>
  );
};

export default Payout;
