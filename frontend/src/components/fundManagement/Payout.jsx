import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { contactsAPI, bankAccountsAPI, fundManagementAPI, walletsAPI } from '../../services/api';
import { mapContactRow } from '../../utils/contactsHelpers';
import MPINModal from '../common/MPINModal';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import FeedbackModal from '../common/FeedbackModal';
import ContactSearchTypeahead from './ContactSearchTypeahead';
import { formatCurrency } from '../../utils/formatters';
import { validateAmount } from '../../utils/validators';
import { formatAccountNumber } from '../../utils/formatters';
import {
  FaPhone,
  FaUser,
  FaEnvelope,
  FaCircleCheck,
  FaPlus,
  FaMagnifyingGlass,
  FaCircleExclamation,
  FaDollarSign,
} from 'react-icons/fa6';

function bankAccountsFromListResult(result) {
  if (!result?.success || !result.data) return [];
  const d = result.data;
  if (Array.isArray(d.results)) return d.results;
  if (Array.isArray(d.bank_accounts)) return d.bank_accounts;
  if (Array.isArray(d)) return d;
  return [];
}

function mapBankAccountRow(a) {
  if (!a) return null;
  return {
    id: a.id,
    accountNumber: a.account_number,
    ifsc: a.ifsc,
    bankName: a.bank_name,
    accountHolderName: a.account_holder_name || a.beneficiary_name || '',
    validated: Boolean(a.is_verified),
  };
}

const Payout = () => {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [bankAccounts, setBankAccounts] = useState([]);
  const [beneficiarySearch, setBeneficiarySearch] = useState('');
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
  const [wallets, setWallets] = useState({ main: 0, commission: 0 });
  const [payoutMeta, setPayoutMeta] = useState(null);
  const [payoutPreview, setPayoutPreview] = useState(null);
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
  const [searchFeedbackModal, setSearchFeedbackModal] = useState({
    open: false,
    title: '',
    description: '',
    primaryAction: null,
  });
  const [payoutFeedbackModal, setPayoutFeedbackModal] = useState({
    open: false,
    title: '',
    description: '',
    primaryAction: null,
  });

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

  const refreshCore = useCallback(async () => {
    if (!user) return;
    const [wRes, qRes, gRes, bRes] = await Promise.all([
      walletsAPI.getAllWallets(),
      fundManagementAPI.getPayoutQuote(),
      fundManagementAPI.getGateways({ type: 'payout' }),
      bankAccountsAPI.listBankAccounts(),
    ]);

    if (wRes.success && wRes.data?.wallets) {
      const m = wRes.data.wallets;
      setWallets({
        main: parseFloat(m.main?.balance ?? 0),
        commission: parseFloat(m.commission?.balance ?? 0),
      });
    }

    if (qRes.success && qRes.data) {
      setPayoutMeta(qRes.data);
    }

    if (gRes.success && gRes.data?.gateways) {
      setPayoutGateways(gRes.data.gateways);
    }

    const raw = bankAccountsFromListResult(bRes);
    setBankAccounts(raw.map(mapBankAccountRow).filter(Boolean));
  }, [user]);

  useEffect(() => {
    refreshCore();
  }, [refreshCore]);

  const maxEligibleAmount = payoutMeta ? parseFloat(payoutMeta.max_eligible_amount) : 0;
  const slabLowMax = payoutMeta ? parseFloat(payoutMeta.slab_low_max) : 24999;
  const chargeLow = payoutMeta ? parseFloat(payoutMeta.charge_low) : 7;
  const chargeHigh = payoutMeta ? parseFloat(payoutMeta.charge_high) : 15;

  useEffect(() => {
    const n = parseFloat(amount);
    if (!amount || Number.isNaN(n) || n <= 0) {
      setPayoutPreview(null);
      return undefined;
    }
    const t = setTimeout(async () => {
      const res = await fundManagementAPI.getPayoutQuote({ amount: n });
      if (res.success && res.data?.preview) {
        setPayoutPreview(res.data.preview);
      } else {
        setPayoutPreview(null);
      }
    }, 350);
    return () => clearTimeout(t);
  }, [amount]);

  const handlePickBeneficiary = useCallback((mapped) => {
    setBeneficiaryDetails(mapped);
  }, []);

  const handleBeneficiarySearch = async () => {
    const raw = beneficiarySearch.trim();
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
      const contactResult = await contactsAPI.searchContactForTransaction(
        usePhone ? { phone: digitsOnly } : { name: raw }
      );
      const mapped = mapContactRow(contactResult.success ? contactResult.data?.contact : null);
      if (mapped) {
        setBeneficiaryDetails(mapped);
      } else {
        const hint =
          'If this beneficiary is not in your saved contacts yet, add them under User Management → Contacts first, then search again.';
        const description = [contactResult.message, hint].filter(Boolean).join('\n\n');
        setSearchFeedbackModal({
          open: true,
          title: 'Contact not found',
          description,
          primaryAction: {
            label: 'Go to Contacts',
            onClick: () => navigate('/user-management/contacts'),
          },
        });
        setBeneficiaryDetails(null);
      }
    } catch (error) {
      setSearchFeedbackModal({
        open: true,
        title: 'Could not search',
        description: 'Something went wrong while searching. Check your connection and try again.',
        primaryAction: null,
      });
      setBeneficiaryDetails(null);
    } finally {
      setSearching(false);
    }
  };

  const handleValidateAccount = async () => {
    if (!newBankAccount.bankName || !newBankAccount.ifsc || !newBankAccount.accountNumber) {
      alert('Please fill in all required fields');
      return;
    }

    setValidatingAccount(true);
    try {
      const result = await bankAccountsAPI.validateBankAccount(
        newBankAccount.accountNumber,
        newBankAccount.ifsc
      );
      const name = result.success ? result.data?.beneficiary_name : null;
      if (name) {
        setValidatedBeneficiary(name);
        setShowValidationModal(true);
      } else {
        alert(result.message || 'Account validation failed. Please check the details.');
      }
    } catch (error) {
      alert('Error validating account. Please try again.');
    } finally {
      setValidatingAccount(false);
    }
  };

  const handleSaveBankAccount = async () => {
    setLoading(true);
    try {
      const holder = validatedBeneficiary || '';
      const body = {
        account_number: newBankAccount.accountNumber,
        ifsc: newBankAccount.ifsc.toUpperCase(),
        bank_name: newBankAccount.bankName,
        account_holder_name: holder,
        beneficiary_name: holder,
      };
      if (beneficiaryDetails?.id) {
        body.contact = beneficiaryDetails.id;
      }
      const result = await bankAccountsAPI.createBankAccount(body);
      if (result.success) {
        const created = result.data?.bank_account || result.data;
        const mapped = mapBankAccountRow(created);
        if (mapped) {
          setBankAccounts((prev) => [...prev, mapped]);
          setSelectedAccount(mapped);
        }
        await refreshCore();
        setShowValidationModal(false);
        setShowAddBankAccount(false);
        setShowSuccessNotification(true);
        setNewBankAccount({ bankName: '', ifsc: '', accountNumber: '' });
        setValidatedBeneficiary(null);
        setTimeout(() => setShowSuccessNotification(false), 3000);
      } else {
        alert(result.message || result.errors?.join?.(', ') || 'Failed to save bank account');
      }
    } catch (e) {
      alert('Could not save bank account');
    } finally {
      setLoading(false);
    }
  };

  const handlePayoutSubmit = () => {
    const amountValidation = validateAmount(parseFloat(amount));
    if (!amountValidation.valid) {
      alert(amountValidation.message);
      return;
    }

    const amt = parseFloat(amount);
    if (amt > maxEligibleAmount) {
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

    setShowMPINModal(true);
  };

  const handleMPINVerify = async (mpin) => {
    setMpinError('');
    setLoading(true);
    try {
      const res = await fundManagementAPI.payout({
        bankAccountId: selectedAccount.id,
        amount: parseFloat(amount),
        mpin,
        transferMode: transferMethod,
        gateway: payoutGateway || null,
      });
      if (res.success) {
        setShowMPINModal(false);
        setPayoutFeedbackModal({
          open: true,
          title: 'Payout successful',
          description: `${formatCurrency(parseFloat(amount))} has been scheduled. Main wallet balance will update in your dashboard.`,
          primaryAction: {
            label: 'Go to dashboard',
            onClick: () => navigate('/dashboard'),
          },
        });
        setAmount('');
        setBeneficiarySearch('');
        setBeneficiaryDetails(null);
        setSelectedAccount(null);
        setPayoutGateway('');
        await refreshCore();
      } else {
        setMpinError(res.message || 'Payout failed');
      }
    } catch (error) {
      setMpinError('Something went wrong. Try again.');
    } finally {
      setLoading(false);
    }
  };

  const beneficiarySearchTrim = beneficiarySearch.trim();
  const beneficiaryDigits = beneficiarySearchTrim.replace(/\D/g, '');
  const beneficiarySearchSubmitDisabled =
    searching || !(beneficiaryDigits.length === 10 || beneficiarySearchTrim.length >= 2);

  const previewCharge = payoutPreview ? parseFloat(payoutPreview.charge) : null;
  const previewTotal = payoutPreview ? parseFloat(payoutPreview.total_debit) : null;

  return (
    <>
      {showSuccessNotification && (
        <div className="fixed top-4 right-4 z-50 animate-slide-in">
          <div className="bg-green-50 border-2 border-green-200 rounded-lg p-4 shadow-lg flex items-center space-x-3 min-w-[300px]">
            <FaCircleCheck className="text-green-600 flex-shrink-0" size={24} />
            <div>
              <p className="font-semibold text-green-800">Bank account saved</p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto space-y-4 sm:space-y-6 px-4 sm:px-0">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Payout (Withdraw Funds)</h1>
            <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600">
              Transfer from your main wallet via IMPS, NEFT, or RTGS. Slab charges: ₹{chargeLow} up to{' '}
              {formatCurrency(slabLowMax)}, ₹{chargeHigh} above.
            </p>
          </div>
        </div>

        <Card padding="lg">
          <div className="p-4 sm:p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-xl space-y-3">
            <p className="text-sm font-medium text-gray-600">Maximum eligible payout (main wallet)</p>
            <p className="text-3xl font-bold text-blue-600">{formatCurrency(maxEligibleAmount)}</p>
            <p className="text-xs text-gray-600">
              Main balance: {formatCurrency(wallets.main)}
              {wallets.commission > 0 ? ` · Commission wallet: ${formatCurrency(wallets.commission)}` : ''}
            </p>
          </div>
        </Card>

        <Card
          title="Search Beneficiary"
          subtitle="Type a name or phone — suggestions as you type; tap to select, or use Search for an exact match"
          padding="lg"
        >
          <div className="space-y-6">
            <ContactSearchTypeahead
              value={beneficiarySearch}
              onChange={setBeneficiarySearch}
              onPick={handlePickBeneficiary}
              onClearSelection={() => {
                setBeneficiaryDetails(null);
                setSelectedAccount(null);
              }}
              placeholder="Start typing name or phone..."
              helperText="At least 2 characters. If several names match, pick from the list or enter the full 10-digit phone. Press Enter to search."
              onSubmitSearch={handleBeneficiarySearch}
              submitSearchDisabled={beneficiarySearchSubmitDisabled}
              trailingAction={
                <Button
                  onClick={handleBeneficiarySearch}
                  disabled={beneficiarySearchSubmitDisabled}
                  loading={searching}
                  icon={FaMagnifyingGlass}
                  iconPosition="left"
                  size="lg"
                  fullWidth
                  className="sm:w-auto min-h-[3.125rem] text-lg leading-snug"
                >
                  Search
                </Button>
              }
            />

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
                    <p className="text-xs text-gray-600 mb-2">
                      Matched from your saved contacts — confirm identity before payout.
                    </p>
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <FaUser className="text-blue-600" size={18} />
                        <p className="font-semibold text-gray-900">{beneficiaryDetails.name}</p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <FaEnvelope className="text-blue-600" size={18} />
                        <p className="text-sm text-gray-600">
                          <span className="font-medium">{beneficiaryDetails.email || '—'}</span>
                        </p>
                      </div>
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

        {beneficiaryDetails && (
          <div>
            <Card title="Select Bank Account" subtitle="Choose from saved accounts or add a new one" padding="lg">
              <div className="space-y-4">
                {bankAccounts.length > 0 && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Beneficiary List</label>
                    <select
                      value={selectedAccount?.id ?? ''}
                      onChange={(e) => {
                        const account = bankAccounts.find((acc) => String(acc.id) === String(e.target.value));
                        setSelectedAccount(account || null);
                        setShowAddBankAccount(false);
                      }}
                      className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
                    >
                      <option value="">-- Select Bank Account --</option>
                      {bankAccounts.map((account) => (
                        <option key={account.id} value={account.id}>
                          {account.bankName} - A/C: {formatAccountNumber(account.accountNumber)} (
                          {account.accountHolderName})
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {bankAccounts.length === 0 && (
                  <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg flex gap-2 text-sm text-amber-900">
                    <FaCircleExclamation className="flex-shrink-0 mt-0.5" />
                    <span>No saved bank accounts yet. Add one below (validation may charge your main wallet per backend rules).</span>
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
                      {selectedAccount.validated && <FaCircleCheck className="text-green-600" size={24} />}
                    </div>
                  </div>
                )}

                {!selectedAccount && (
                  <div className="border-t border-gray-200 pt-4">
                    <button
                      type="button"
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
                            placeholder="Enter IFSC code"
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
                          disabled={
                            validatingAccount ||
                            !newBankAccount.bankName ||
                            !newBankAccount.ifsc ||
                            !newBankAccount.accountNumber
                          }
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

            {selectedAccount && payoutGateways.length > 0 && (
              <Card
                title="Payout route (optional)"
                subtitle="If your deployment routes payouts through a specific provider, select it; otherwise leave blank"
                padding="lg"
              >
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Payout gateway</label>
                  <select
                    value={payoutGateway}
                    onChange={(e) => setPayoutGateway(e.target.value)}
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
                  >
                    <option value="">-- Optional --</option>
                    {payoutGateways.map((gw) => (
                      <option key={gw.id} value={gw.id}>
                        {gw.name}
                      </option>
                    ))}
                  </select>
                </div>
              </Card>
            )}

            {selectedAccount && (
              <Card title="Select Transfer Method" subtitle="Choose IMPS, NEFT, or RTGS" padding="lg">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
                  {['IMPS', 'NEFT', 'RTGS'].map((method) => (
                    <button
                      key={method}
                      type="button"
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

            {selectedAccount && (
              <Card title="Enter Amount" subtitle="Enter the amount you wish to transfer" padding="lg">
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

                  {amount && parseFloat(amount) > 0 && (
                    <div className="p-6 bg-gray-50 rounded-xl border border-gray-200">
                      <h4 className="text-sm font-semibold text-gray-700 mb-4 uppercase tracking-wide">
                        Transaction Summary
                      </h4>
                      <div className="space-y-3">
                        <div className="flex justify-between items-center py-2 border-b border-gray-200">
                          <span className="text-gray-600">Payout amount</span>
                          <span className="font-semibold text-gray-900 text-lg">
                            {formatCurrency(parseFloat(amount))}
                          </span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-gray-200">
                          <span className="text-gray-600">Transfer charge (slab)</span>
                          <span className="font-semibold text-red-600">
                            {previewCharge != null ? `-${formatCurrency(previewCharge)}` : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between items-center pt-3 bg-red-50 p-3 rounded-lg">
                          <span className="text-lg font-bold text-gray-900">Total debited from main wallet</span>
                          <span className="text-2xl font-bold text-red-600">
                            {previewTotal != null ? formatCurrency(previewTotal) : '—'}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  <Button
                    onClick={handlePayoutSubmit}
                    disabled={!amount || parseFloat(amount) <= 0}
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
                <Button onClick={handleSaveBankAccount} variant="primary" size="lg" fullWidth loading={loading}>
                  Save Account
                </Button>
              </div>
            </Card>
          </div>
        )}

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

        <FeedbackModal
          open={searchFeedbackModal.open}
          onClose={() => setSearchFeedbackModal((m) => ({ ...m, open: false }))}
          title={searchFeedbackModal.title}
          description={searchFeedbackModal.description}
          primaryAction={searchFeedbackModal.primaryAction}
        />
        <FeedbackModal
          open={payoutFeedbackModal.open}
          onClose={() => setPayoutFeedbackModal((m) => ({ ...m, open: false }))}
          title={payoutFeedbackModal.title}
          description={payoutFeedbackModal.description}
          primaryAction={payoutFeedbackModal.primaryAction}
        />
      </div>
    </>
  );
};

export default Payout;
