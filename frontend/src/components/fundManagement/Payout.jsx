import React, { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { contactsAPI, bankAccountsAPI, fundManagementAPI, walletsAPI } from '../../services/api';
import { mapContactRow } from '../../utils/contactsHelpers';
import MPINModal from '../common/MPINModal';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import FeedbackModal from '../common/FeedbackModal';
import PaymentFlowOverlay from '../common/PaymentFlowOverlay';
import ContactSearchTypeahead from './ContactSearchTypeahead';
import SelectField from '../common/SelectField';
import { formatCurrency } from '../../utils/formatters';
import { validateAmount, validateAccountNumber, validateIFSC, validatePhone } from '../../utils/validators';
import AccountAccessBanner from '../common/AccountAccessBanner';
import MaintenanceModuleLock from '../common/MaintenanceModuleLock';
import { isModuleEnabled } from '../../utils/maintenanceMode';
import {
  FaPhone,
  FaUser,
  FaEnvelope,
  FaCircleCheck,
  FaPlus,
  FaMagnifyingGlass,
  FaCircleExclamation,
  FaIndianRupeeSign,
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
  const { user, maintenance, refreshMaintenance } = useAuth();
  const payoutMaintenance = !isModuleEnabled(maintenance, 'payout');
  const [bankAccounts, setBankAccounts] = useState([]);
  const [beneficiarySearch, setBeneficiarySearch] = useState('');
  const [beneficiaryDetails, setBeneficiaryDetails] = useState(null);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [amount, setAmount] = useState('');
  const [transferMethod, setTransferMethod] = useState('IMPS');
  const [payoutGateway, setPayoutGateway] = useState('');
  const [payoutGateways, setPayoutGateways] = useState([]);
  const [geoCoords, setGeoCoords] = useState({ lat: '', long: '' });
  const [showMPINModal, setShowMPINModal] = useState(false);
  const [mpinError, setMpinError] = useState('');
  const [loading, setLoading] = useState(false);
  const [searching, setSearching] = useState(false);
  const [wallets, setWallets] = useState({ main: 0, commission: 0 });
  const [payoutMeta, setPayoutMeta] = useState(null);
  const [payoutPreview, setPayoutPreview] = useState(null);
  const [showAddBankAccount, setShowAddBankAccount] = useState(false);
  const [newBankAccount, setNewBankAccount] = useState({
    ifsc: '',
    accountNumber: '',
    mobileNumber: '',
  });
  const [validatingAccount, setValidatingAccount] = useState(false);
  const [validationData, setValidationData] = useState(null);
  const [showValidationModal, setShowValidationModal] = useState(false);
  const [showSuccessNotification, setShowSuccessNotification] = useState(false);

  const validatedBeneficiary = validationData?.beneficiary_name || null;
  const [searchFeedbackModal, setSearchFeedbackModal] = useState({
    open: false,
    title: '',
    description: '',
    primaryAction: null,
  });
  const [formFeedbackModal, setFormFeedbackModal] = useState({
    open: false,
    title: '',
    description: '',
  });
  const [paymentFlow, setPaymentFlow] = useState({
    open: false,
    phase: 'processing',
    amount: null,
    subtitle: '',
    reference: '',
    details: [],
    primaryAction: null,
    secondaryAction: null,
  });
  const payoutSubmitLockRef = useRef(false);

  const showFormFeedback = (title, description) => {
    setFormFeedbackModal({
      open: true,
      title: title || 'Please check',
      description: description || '',
    });
  };

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
    if (typeof navigator === 'undefined' || !navigator.geolocation) return undefined;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGeoCoords({
          lat: String(pos.coords.latitude),
          long: String(pos.coords.longitude),
        });
      },
      () => {
        setGeoCoords((prev) =>
          prev.lat ? prev : { lat: '28.7041', long: '77.1025' }
        );
      },
      { enableHighAccuracy: false, timeout: 8000, maximumAge: 600000 }
    );
    return undefined;
  }, []);

  useEffect(() => {
    refreshMaintenance?.();
    const id = setInterval(() => refreshMaintenance?.(), 60000);
    return () => clearInterval(id);
  }, [refreshMaintenance]);

  useEffect(() => {
    refreshCore();
  }, [refreshCore]);

  const mainWalletBalance = payoutMeta?.main_balance != null
    ? parseFloat(payoutMeta.main_balance)
    : wallets.main;
  const maxEligibleAmount = payoutMeta ? parseFloat(payoutMeta.max_eligible_amount) : 0;

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
    const accountValidation = validateAccountNumber(newBankAccount.accountNumber);
    if (!accountValidation.valid) {
      showFormFeedback('Invalid account number', accountValidation.message);
      return;
    }

    const ifscValidation = validateIFSC(newBankAccount.ifsc);
    if (!ifscValidation.valid) {
      showFormFeedback('Invalid IFSC', ifscValidation.message);
      return;
    }

    const phoneValidation = validatePhone(newBankAccount.mobileNumber);
    if (!phoneValidation.valid) {
      showFormFeedback('Invalid mobile number', phoneValidation.message);
      return;
    }

    setValidatingAccount(true);
    try {
      const result = await bankAccountsAPI.validateBankAccount(
        newBankAccount.accountNumber,
        newBankAccount.ifsc.toUpperCase(),
        newBankAccount.mobileNumber
      );
      const data = result.success ? result.data : null;
      if (data?.beneficiary_name) {
        setValidationData(data);
        setShowValidationModal(true);
      } else {
        showFormFeedback(
          'Validation failed',
          result.message || 'Account validation failed. Please check the details.'
        );
      }
    } catch (error) {
      showFormFeedback('Validation error', 'Could not validate account. Please try again.');
    } finally {
      setValidatingAccount(false);
    }
  };

  const handleSaveBankAccount = async () => {
    if (validationData?.bank_account) {
      const mapped = mapBankAccountRow(validationData.bank_account);
      if (mapped) {
        setBankAccounts((prev) => [...prev, mapped]);
        setSelectedAccount(mapped);
      }
      await refreshCore();
      setShowValidationModal(false);
      setShowAddBankAccount(false);
      setShowSuccessNotification(true);
      setNewBankAccount({ ifsc: '', accountNumber: '', mobileNumber: '' });
      setValidationData(null);
      setTimeout(() => setShowSuccessNotification(false), 3000);
      return;
    }

    setLoading(true);
    try {
      const holder = validatedBeneficiary || '';
      const bankName =
        validationData?.bank_name ||
        validationData?.verification_details?.bank_name ||
        validationData?.verification_details?.ifsc_details?.bank ||
        '';
      const body = {
        account_number: newBankAccount.accountNumber,
        ifsc: (validationData?.ifsc || newBankAccount.ifsc).toUpperCase(),
        bank_name: bankName || 'UNKNOWN',
        account_holder_name: holder,
        beneficiary_name: holder,
        mobile_number: newBankAccount.mobileNumber,
        validation_token: validationData?.validation_token,
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
        setNewBankAccount({ ifsc: '', accountNumber: '', mobileNumber: '' });
        setValidationData(null);
        setTimeout(() => setShowSuccessNotification(false), 3000);
      } else {
        showFormFeedback(
          'Could not save account',
          result.message || result.errors?.join?.(', ') || 'Failed to save bank account'
        );
      }
    } catch (e) {
      showFormFeedback('Could not save account', 'Please try again in a moment.');
    } finally {
      setLoading(false);
    }
  };

  const handlePayoutSubmit = () => {
    if (loading || payoutSubmitLockRef.current) return;

    const amountValidation = validateAmount(parseFloat(amount));
    if (!amountValidation.valid) {
      showFormFeedback('Invalid amount', amountValidation.message);
      return;
    }

    const amt = parseFloat(amount);
    if (amt < 100) {
      showFormFeedback('Minimum amount', 'Minimum payout amount is ₹100.');
      return;
    }
    if (amt > maxEligibleAmount) {
      showFormFeedback(
        'Amount too high',
        `Maximum eligible amount is ${formatCurrency(maxEligibleAmount)}. Reduce the amount or top up your main wallet.`
      );
      return;
    }

    if (!beneficiaryDetails) {
      showFormFeedback('Beneficiary required', 'Search and select a beneficiary first.');
      return;
    }

    if (!selectedAccount) {
      showFormFeedback('Bank account required', 'Select or add a bank account to continue.');
      return;
    }

    setMpinError('');
    setShowMPINModal(true);
  };

  const resetPayoutForm = () => {
    setAmount('');
    setBeneficiarySearch('');
    setBeneficiaryDetails(null);
    setSelectedAccount(null);
    setPayoutGateway('');
    setPayoutPreview(null);
  };

  const openPayoutReceipt = ({ status, txnId, amountValue, chargeValue, totalValue, accountLabel, failureMessage }) => {
    const st = (status || '').toUpperCase();
    const isSuccess = st === 'SUCCESS';
    const isFailed = st === 'FAILED' || Boolean(failureMessage);
    const isPending = !isSuccess && !isFailed;
    const phase = isSuccess ? 'success' : isPending ? 'pending' : 'failed';

    const details = [
      accountLabel ? { label: 'Account', value: accountLabel } : null,
      chargeValue != null ? { label: 'Charge', value: formatCurrency(chargeValue) } : null,
      totalValue != null ? { label: 'Total held', value: formatCurrency(totalValue) } : null,
      {
        label: 'Status',
        value: isSuccess ? 'Successful' : isPending ? 'Waiting for bank' : 'Failed',
      },
    ].filter(Boolean);

    setPaymentFlow({
      open: true,
      phase,
      amount: amountValue,
      subtitle: isSuccess
        ? 'Money sent successfully'
        : isPending
          ? 'Transfer queued. Amount is held on your wallet until the bank confirms — usually within a few minutes.'
          : failureMessage || 'The transfer could not be completed',
      reference: txnId || '',
      details,
      primaryAction: {
        label: txnId ? 'View receipt / refresh status' : 'View Pay Out report',
        onClick: () => {
          if (txnId) {
            navigate(`/reports/payout?open_receipt=1&service_id=${encodeURIComponent(txnId)}`);
            return;
          }
          navigate('/reports/payout');
        },
      },
      secondaryAction: isPending && txnId
        ? {
            label: 'Check status now',
            onClick: async () => {
              const res = await fundManagementAPI.getPayoutStatus(txnId);
              if (!res.success || !res.data?.payout) {
                showFormFeedback('Status check', res.message || 'Could not refresh status yet.');
                return;
              }
              const p = res.data.payout;
              openPayoutReceipt({
                status: p.status,
                txnId: p.transaction_id || txnId,
                amountValue: parseFloat(p.amount ?? amountValue) || amountValue,
                chargeValue: p.charge != null ? parseFloat(p.charge) : chargeValue,
                totalValue: p.total_deducted != null ? parseFloat(p.total_deducted) : totalValue,
                accountLabel,
                failureMessage: p.failure_reason || '',
              });
            },
          }
        : null,
    });
  };

  const closePaymentFlow = () => {
    setPaymentFlow((s) => ({ ...s, open: false }));
    payoutSubmitLockRef.current = false;
  };

  const handleMPINVerify = async (mpin) => {
    if (payoutSubmitLockRef.current || loading) return;
    payoutSubmitLockRef.current = true;
    setMpinError('');
    setLoading(true);

    const amountValue = parseFloat(amount);
    const chargeValue = previewCharge;
    const totalValue = previewTotal;
    const accountLabel = selectedAccount
      ? `${selectedAccount.bankName} · ${selectedAccount.accountNumber || ''}`
      : '';

    setShowMPINModal(false);
    setPaymentFlow({
      open: true,
      phase: 'processing',
      amount: amountValue,
      subtitle: 'Securely verifying and initiating transfer…',
      reference: '',
      details: [],
      primaryAction: null,
      secondaryAction: null,
    });

    // Brief cinematic beat so the processing screen is visible even on fast APIs
    await new Promise((r) => setTimeout(r, 650));

    try {
      const res = await fundManagementAPI.payout({
        bankAccountId: selectedAccount.id,
        amount: amountValue,
        mpin,
        transferMode: transferMethod,
        gateway: payoutGateway || null,
        purposeCode: '004',
        lat: geoCoords.lat || '28.7041',
        long: geoCoords.long || '77.1025',
      });
      if (res.success) {
        const payout = res.data?.payout || {};
        openPayoutReceipt({
          status: payout.status,
          txnId: payout.transaction_id || '',
          amountValue: parseFloat(payout.amount ?? amountValue) || amountValue,
          chargeValue:
            payout.charge != null ? parseFloat(payout.charge) : chargeValue,
          totalValue:
            payout.total_deducted != null ? parseFloat(payout.total_deducted) : totalValue,
          accountLabel,
        });
        resetPayoutForm();
        await refreshCore();
      } else {
        const msg = res.message || 'Payout could not be completed.';
        const isMpinError =
          /mpin/i.test(msg) || Boolean(res.errors?.mpin);
        if (isMpinError) {
          setPaymentFlow((s) => ({ ...s, open: false }));
          setShowMPINModal(true);
          setMpinError(msg);
          payoutSubmitLockRef.current = false;
        } else {
          openPayoutReceipt({
            status: 'FAILED',
            amountValue,
            chargeValue,
            totalValue,
            accountLabel,
            failureMessage: msg,
          });
          payoutSubmitLockRef.current = false;
        }
      }
    } catch (error) {
      const msg =
        error?.response?.data?.message ||
        error?.message ||
        'Something went wrong. Please try again or check Pay Out report.';
      if (/mpin/i.test(String(msg))) {
        setPaymentFlow((s) => ({ ...s, open: false }));
        setShowMPINModal(true);
        setMpinError(String(msg));
        payoutSubmitLockRef.current = false;
      } else {
        openPayoutReceipt({
          status: 'FAILED',
          amountValue,
          chargeValue,
          totalValue,
          accountLabel,
          failureMessage: String(msg),
        });
        payoutSubmitLockRef.current = false;
      }
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
          <div className="bg-green-50 dark:bg-green-950/40 border-2 border-green-200 dark:border-green-800 rounded-lg p-4 shadow-lg flex items-center space-x-3 min-w-[300px]">
            <FaCircleCheck className="text-green-600 dark:text-green-400 flex-shrink-0" size={24} />
            <div>
              <p className="font-semibold text-green-800 dark:text-green-300">Bank account saved</p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto space-y-4 sm:space-y-6 px-4 sm:px-0">
        <AccountAccessBanner user={user} mode="pay_out" />
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-slate-100">Payout</h1>
            <p className="mt-1 text-sm text-gray-600 dark:text-slate-400">
              Transfer from main wallet (IMPS / NEFT). Min ₹100. Funds stay held until the bank confirms.
            </p>
          </div>
        </div>

        <MaintenanceModuleLock maintenance={maintenance} moduleKey="payout">
        <Card padding="lg">
          <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/60 px-4 py-4 sm:px-5 sm:py-5 space-y-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500 dark:text-slate-400">
                Main wallet
              </p>
              <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-slate-100">
                {formatCurrency(mainWalletBalance)}
              </p>
              {wallets.commission > 0 ? (
                <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Commission wallet {formatCurrency(wallets.commission)} (not used for payout)
                </p>
              ) : null}
            </div>
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
                      Confirm beneficiary before continuing.
                    </p>
                    <div className="space-y-2">
                      <div className="flex items-center space-x-2">
                        <FaUser className="text-blue-600 dark:text-blue-400" size={18} />
                        <p className="font-semibold text-gray-900 dark:text-slate-100">{beneficiaryDetails.name}</p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <FaEnvelope className="text-blue-600 dark:text-blue-400" size={18} />
                        <p className="text-sm text-gray-600 dark:text-slate-400">
                          <span className="font-medium">{beneficiaryDetails.email || '—'}</span>
                        </p>
                      </div>
                      <div className="flex items-center space-x-2">
                        <FaPhone className="text-blue-600 dark:text-blue-400" size={18} />
                        <p className="text-sm text-gray-600 dark:text-slate-400">
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
            <Card title="Bank account" padding="lg">
              <div className="space-y-4">
                {bankAccounts.length > 0 && (
                  <div>
                    <SelectField
                      label="Select account"
                      value={selectedAccount?.id ?? ''}
                      onChange={(val) => {
                        const account = bankAccounts.find((acc) => String(acc.id) === String(val));
                        setSelectedAccount(account || null);
                        setShowAddBankAccount(false);
                      }}
                      options={bankAccounts}
                      getOptionLabel={(account) =>
                        `${account.bankName} · ${account.accountNumber || ''}${
                          account.accountHolderName ? ` · ${account.accountHolderName}` : ''
                        }`
                      }
                      getOptionValue={(account) => account.id}
                      placeholder="Choose bank account"
                      searchable
                    />
                  </div>
                )}

                {bankAccounts.length === 0 && (
                  <div className="p-3 bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 rounded-lg flex gap-2 text-sm text-amber-900 dark:text-amber-300">
                    <FaCircleExclamation className="flex-shrink-0 mt-0.5" />
                    <span>No bank accounts yet. Add one to continue.</span>
                  </div>
                )}

                {selectedAccount && (
                  <div className="p-4 bg-gray-50 dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700 rounded-lg">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold text-gray-900 dark:text-slate-100 truncate">
                          {selectedAccount.bankName}
                        </p>
                        <p className="text-sm text-gray-600 dark:text-slate-400 mt-1">
                          {selectedAccount.accountNumber} · {selectedAccount.ifsc}
                        </p>
                        <p className="text-sm text-gray-600 dark:text-slate-400">
                          {selectedAccount.accountHolderName}
                        </p>
                      </div>
                      {selectedAccount.validated && (
                        <FaCircleCheck className="text-green-600 dark:text-green-400 flex-shrink-0" size={22} />
                      )}
                    </div>
                  </div>
                )}

                {!selectedAccount && (
                  <div className="border-t border-gray-200 dark:border-slate-700 pt-4">
                    <button
                      type="button"
                      onClick={() => setShowAddBankAccount(!showAddBankAccount)}
                      className="flex items-center space-x-2 text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-200 font-medium"
                    >
                      <FaPlus size={18} />
                      <span>Add Bank Account</span>
                    </button>

                    {showAddBankAccount && (
                      <div className="mt-4 p-4 bg-gray-50 dark:bg-slate-800/50 border border-gray-200 dark:border-slate-700 rounded-lg space-y-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
                            Mobile Number <span className="text-red-500">*</span>
                          </label>
                          <Input
                            value={newBankAccount.mobileNumber}
                            onChange={(e) => {
                              const value = e.target.value.replace(/\D/g, '').slice(0, 10);
                              setNewBankAccount({ ...newBankAccount, mobileNumber: value });
                            }}
                            placeholder="Enter 10-digit mobile number"
                            maxLength={10}
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
                            IFSC Code <span className="text-red-500">*</span>
                          </label>
                          <Input
                            value={newBankAccount.ifsc}
                            onChange={(e) => {
                              const value = e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 11);
                              setNewBankAccount({ ...newBankAccount, ifsc: value });
                            }}
                            placeholder="Enter IFSC code"
                            maxLength={11}
                          />
                        </div>

                        <div>
                          <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
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
                            newBankAccount.ifsc.length !== 11 ||
                            newBankAccount.mobileNumber.length !== 10 ||
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
              <Card title="Payout route" padding="lg">
                <div>
                  <SelectField
                    label="Gateway (optional)"
                    value={payoutGateway}
                    onChange={(val) => setPayoutGateway(val)}
                    options={payoutGateways}
                    getOptionLabel={(gw) => gw.name}
                    getOptionValue={(gw) => gw.id}
                    placeholder="Default route"
                  />
                </div>
              </Card>
            )}

            {selectedAccount && (
              <Card title="Transfer mode" padding="lg">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
                  {['IMPS', 'NEFT'].map((method) => (
                    <button
                      key={method}
                      type="button"
                      onClick={() => setTransferMethod(method)}
                      className={`p-4 sm:p-5 border-2 rounded-xl transition-all ${
                        transferMethod === method
                          ? 'border-blue-500 bg-gradient-to-br from-blue-50 dark:from-blue-950/40 to-indigo-50 dark:to-indigo-950/40 shadow-md'
                          : 'border-gray-300 dark:border-slate-600 hover:border-gray-400 bg-white dark:bg-slate-900'
                      }`}
                    >
                      <p className="font-bold text-gray-900 dark:text-slate-100 text-base sm:text-lg">{method}</p>
                      {transferMethod === method && (
                        <FaCircleCheck className="text-blue-600 dark:text-blue-400 mt-2 mx-auto" size={20} />
                      )}
                    </button>
                  ))}
                </div>
              </Card>
            )}

            {selectedAccount && (
              <Card title="Amount" subtitle="Minimum ₹100" padding="lg">
                <div className="space-y-6">
                  <div>
                    <Input
                      label="Amount (INR)"
                      type="number"
                      icon={FaIndianRupeeSign}
                      value={amount}
                      onChange={(e) => setAmount(e.target.value)}
                      placeholder="Enter amount"
                      min="100"
                      max={maxEligibleAmount}
                      step="0.01"
                      size="lg"
                    />
                  </div>

                  {amount && parseFloat(amount) > 0 && (
                    <div className="p-6 bg-gray-50 dark:bg-slate-800/50 rounded-xl border border-gray-200 dark:border-slate-700">
                      <h4 className="text-sm font-semibold text-gray-700 dark:text-slate-300 mb-4 uppercase tracking-wide">
                        Summary
                      </h4>
                      <div className="space-y-3">
                        <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-slate-700">
                          <span className="text-gray-600 dark:text-slate-400">Payout</span>
                          <span className="font-semibold text-gray-900 dark:text-slate-100 text-lg">
                            {formatCurrency(parseFloat(amount))}
                          </span>
                        </div>
                        <div className="flex justify-between items-center py-2 border-b border-gray-200 dark:border-slate-700">
                          <span className="text-gray-600 dark:text-slate-400">Charge</span>
                          <span className="font-semibold text-red-600 dark:text-red-400">
                            {previewCharge != null ? `-${formatCurrency(previewCharge)}` : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between items-center pt-3 bg-red-50 dark:bg-red-950/40 p-3 rounded-lg">
                          <span className="text-lg font-bold text-gray-900 dark:text-slate-100">Total debit</span>
                          <span className="text-2xl font-bold text-red-600 dark:text-red-400">
                            {previewTotal != null ? formatCurrency(previewTotal) : '—'}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}

                  <Button
                    onClick={handlePayoutSubmit}
                    disabled={
                      payoutMaintenance ||
                      loading ||
                      !amount ||
                      parseFloat(amount) < 100
                    }
                    loading={loading}
                    variant="primary"
                    size="lg"
                    fullWidth
                  >
                    Pay now
                  </Button>
                </div>
              </Card>
            )}
          </div>
        )}
        </MaintenanceModuleLock>

        {showValidationModal && validatedBeneficiary && !payoutMaintenance && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
            <Card className="max-w-md w-full border-2 border-blue-200 dark:border-blue-800 my-auto" padding="lg" shadow="xl">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-slate-100 mb-4 sm:mb-6">Confirm Beneficiary</h2>

              <div className="p-4 bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 rounded-lg mb-6">
                <p className="text-sm text-gray-600 dark:text-slate-400 mb-2">Beneficiary Name:</p>
                <p className="text-xl font-bold text-gray-900 dark:text-slate-100">{validatedBeneficiary}</p>
                <p className="text-sm text-gray-600 dark:text-slate-400 mt-2">
                  Account: {newBankAccount.accountNumber}
                </p>
                {newBankAccount.mobileNumber && (
                  <p className="text-sm text-gray-600 dark:text-slate-400">Mobile: {newBankAccount.mobileNumber}</p>
                )}
                <p className="text-sm text-gray-600 dark:text-slate-400">
                  IFSC: {(validationData?.ifsc || newBankAccount.ifsc).toUpperCase()}
                </p>
                {(validationData?.bank_name ||
                  validationData?.verification_details?.bank_name ||
                  validationData?.verification_details?.ifsc_details?.bank) && (
                  <p className="text-sm text-gray-600 dark:text-slate-400">
                    Bank:{' '}
                    {validationData?.bank_name ||
                      validationData?.verification_details?.bank_name ||
                      validationData?.verification_details?.ifsc_details?.bank}
                  </p>
                )}
              </div>

              <div className="flex space-x-3">
                <Button
                  onClick={() => {
                    setShowValidationModal(false);
                    setValidationData(null);
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
          isOpen={showMPINModal && !payoutMaintenance}
          onClose={() => {
            setShowMPINModal(false);
            setMpinError('');
            payoutSubmitLockRef.current = false;
          }}
          onVerify={handleMPINVerify}
          title="Confirm payout"
          error={mpinError}
          loading={loading}
        />

        <FeedbackModal
          open={searchFeedbackModal.open}
          onClose={() => setSearchFeedbackModal((m) => ({ ...m, open: false }))}
          title={searchFeedbackModal.title}
          description={searchFeedbackModal.description}
          primaryAction={searchFeedbackModal.primaryAction}
        />
        <FeedbackModal
          open={formFeedbackModal.open}
          onClose={() => setFormFeedbackModal((m) => ({ ...m, open: false }))}
          title={formFeedbackModal.title}
          description={formFeedbackModal.description}
        />
        <PaymentFlowOverlay
          open={paymentFlow.open}
          phase={paymentFlow.phase}
          kind="payout"
          amount={paymentFlow.amount}
          subtitle={paymentFlow.subtitle}
          reference={paymentFlow.reference}
          details={paymentFlow.details}
          primaryAction={paymentFlow.primaryAction}
          secondaryAction={paymentFlow.secondaryAction}
          onClose={closePaymentFlow}
          secondaryLabel="Done"
        />
      </div>
    </>
  );
};

export default Payout;
