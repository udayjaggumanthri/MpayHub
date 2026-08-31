import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import {
  FaPlus,
  FaPenToSquare,
  FaTrash,
  FaToggleOn,
  FaToggleOff,
  FaCircleCheck,
  FaCircleExclamation,
  FaXmark,
  FaCreditCard,
  FaArrowRight,
  FaChartPie,
} from 'react-icons/fa6';
import {
  parseList,
  categoryShortLabel,
  GATEWAY_CATEGORIES,
  firstErrorMessage,
} from './gatewayAdminShared';
import GatewayFlowStepper from './GatewayFlowStepper';

const PaymentGatewaysAdmin = () => {
  const [gateways, setGateways] = useState([]);
  const [paymentApiMasters, setPaymentApiMasters] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingGateway, setEditingGateway] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    chargeRate: '',
    category: 'third-party',
    apiMasterId: '',
  });

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    const [gRes, aRes] = await Promise.all([
      adminAPI.listPaymentGateways(),
      adminAPI.listApiMasters(),
    ]);
    if (gRes.success) setGateways(parseList(gRes));
    if (aRes.success) {
      const masters = parseList(aRes).filter(
        (row) => row.provider_type === 'payments' && !row.is_deleted
      );
      setPaymentApiMasters(masters);
    }
  };

  const handleAddGateway = () => {
    if (paymentApiMasters.length === 0) {
      alert('Add at least one Payment API Master first.');
      return;
    }
    setFormData({
      name: '',
      chargeRate: '',
      category: 'third-party',
      apiMasterId: '',
    });
    setShowAddModal(true);
  };

  const handleEditGateway = (gateway) => {
    const apiMasterId =
      gateway.api_master && typeof gateway.api_master === 'object'
        ? gateway.api_master.id
        : gateway.api_master;
    setEditingGateway(gateway);
    setFormData({
      name: gateway.name,
      chargeRate: gateway.charge_rate?.toString?.() || '',
      category: gateway.category || 'third-party',
      apiMasterId: apiMasterId ? String(apiMasterId) : '',
    });
    setShowEditModal(true);
  };

  const handleToggleStatus = async (gatewayId) => {
    const result = await adminAPI.togglePaymentGatewayStatus(gatewayId);
    if (result.success) loadData();
  };

  const handleDeleteGateway = async (gatewayId) => {
    if (window.confirm('Are you sure you want to delete this gateway? This action cannot be undone.')) {
      const result = await adminAPI.deletePaymentGateway(gatewayId);
      if (result.success) {
        loadData();
      } else {
        alert(result.message || 'Failed to delete gateway');
      }
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.chargeRate) {
      alert('Please fill in all required fields');
      return;
    }
    if (!formData.apiMasterId) {
      alert('Please select a connected Payment API Master');
      return;
    }

    setLoading(true);
    const gatewayData = {
      name: formData.name,
      charge_rate: parseFloat(formData.chargeRate),
      category: formData.category,
      api_master_id: Number(formData.apiMasterId),
    };

    let result;
    if (showEditModal && editingGateway) {
      result = await adminAPI.updatePaymentGateway(editingGateway.id, gatewayData);
    } else {
      result = await adminAPI.createPaymentGateway(gatewayData);
    }

    setLoading(false);
    if (result.success) {
      setShowAddModal(false);
      setShowEditModal(false);
      setEditingGateway(null);
      loadData();
    } else {
      alert(firstErrorMessage(result, 'Failed to save gateway'));
    }
  };

  const gatewayFormFields = (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
          Gateway Name <span className="text-red-500">*</span>
        </label>
        <Input
          value={formData.name}
          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
          placeholder="e.g., Razorpay Production"
          required
        />
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
          Category <span className="text-red-500">*</span>
        </label>
        <select
          value={formData.category}
          onChange={(e) => setFormData({ ...formData, category: e.target.value })}
          className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 dark:text-slate-100 bg-white dark:bg-slate-900"
          required
        >
          {GATEWAY_CATEGORIES.map((cat) => (
            <option key={cat.value} value={cat.value}>
              {cat.label}
            </option>
          ))}
        </select>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
          Payment API Master <span className="text-red-500">*</span>
        </label>
        <select
          value={formData.apiMasterId}
          onChange={(e) => setFormData({ ...formData, apiMasterId: e.target.value })}
          className="w-full px-4 py-3 border border-gray-300 dark:border-slate-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 dark:text-slate-100 bg-white dark:bg-slate-900"
          required
        >
          <option value="">-- Select Payment API Master --</option>
          {paymentApiMasters.map((m) => (
            <option key={m.id} value={m.id}>
              {m.provider_name} ({m.provider_code}) [{m.status}]
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-500 dark:text-slate-400">Linked from the API Master module.</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
          Service Charge Rate (%) <span className="text-red-500">*</span>
        </label>
        <Input
          type="number"
          step="0.01"
          min="0"
          value={formData.chargeRate}
          onChange={(e) => setFormData({ ...formData, chargeRate: e.target.value })}
          placeholder="e.g., 1.0"
          required
        />
      </div>
    </>
  );

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-slate-50/80 dark:to-slate-900/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <GatewayFlowStepper
          currentStep="payment-gateways"
          subtitle="Step 2/3: Create payment gateways and link each gateway to a payment API master."
        />
        <header className="relative overflow-hidden rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-900 shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/[0.07] via-transparent to-violet-500/[0.06] pointer-events-none" />
          <div className="relative px-6 py-8 sm:px-8 sm:py-9 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600 dark:text-indigo-400 mb-2">
                Admin · Payments
              </p>
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-tight">Payment gateways</h1>
              <p className="mt-2 text-sm sm:text-base text-slate-600 dark:text-slate-400 max-w-xl leading-relaxed">
                Connect Razorpay, PayU, or internal rails. Configure service charges for payment processing.
              </p>
            </div>
            <Link
              to="/admin/pay-in-packages"
              className="inline-flex items-center gap-2 self-start rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-300 shadow-sm hover:border-indigo-200 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/60 hover:text-indigo-800 dark:hover:text-indigo-200 transition-colors"
            >
              <FaChartPie className="text-indigo-600 dark:text-indigo-400" size={18} />
              Pay-in packages &amp; fees
              <FaArrowRight size={14} className="text-slate-400 dark:text-slate-500" />
            </Link>
            <Link
              to="/admin/pay-in-qr-accounts"
              className="inline-flex items-center gap-2 self-start rounded-xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/40 px-4 py-3 text-sm font-semibold text-emerald-800 dark:text-emerald-300 shadow-sm hover:border-emerald-300 dark:hover:border-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/60 transition-colors"
            >
              QR collection accounts
              <FaArrowRight size={14} className="text-emerald-500" />
            </Link>
            <Link
              to="/admin/pay-in-qr-operations"
              className="inline-flex items-center gap-2 self-start rounded-xl border border-emerald-200 dark:border-emerald-800 bg-white dark:bg-slate-900 px-4 py-3 text-sm font-semibold text-emerald-800 dark:text-emerald-300 shadow-sm hover:border-emerald-300 dark:hover:border-emerald-700 hover:bg-emerald-50 dark:hover:bg-emerald-950/60 transition-colors"
            >
              QR operations queue
              <FaArrowRight size={14} className="text-emerald-500" />
            </Link>
            <Link
              to="/admin/api-master"
              className="inline-flex items-center gap-2 self-start rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-300 shadow-sm hover:border-indigo-200 hover:bg-indigo-50/50 dark:hover:bg-indigo-950/60 hover:text-indigo-800 dark:hover:text-indigo-200 transition-colors"
            >
              API Master
              <FaArrowRight size={14} className="text-slate-400 dark:text-slate-500" />
            </Link>
          </div>
        </header>

        <section className="rounded-2xl border border-slate-200/90 dark:border-slate-700/90 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
          <div className="flex flex-col gap-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/20">
                <FaCreditCard size={20} />
              </span>
              <div>
                <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Your gateways</h2>
                <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">Linked API credentials for payment processing.</p>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="rounded-full bg-white dark:bg-slate-900 px-3 py-1 text-xs font-semibold text-slate-600 dark:text-slate-400 ring-1 ring-slate-200 dark:ring-slate-700">
                {gateways.length} {gateways.length === 1 ? 'gateway' : 'gateways'}
              </span>
              <Button onClick={handleAddGateway} variant="primary" size="md" icon={FaPlus} iconPosition="left">
                Add gateway
              </Button>
            </div>
          </div>
          {paymentApiMasters.length === 0 ? (
            <div className="mx-6 mt-5 rounded-lg border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-800 dark:text-amber-300">
              No payment API master found. Create one in{' '}
              <Link to="/admin/api-master" className="font-semibold underline">
                API Master
              </Link>{' '}
              before adding gateways.
            </div>
          ) : null}

          <div className="overflow-x-auto">
            {gateways.length === 0 ? (
              <div className="px-6 py-16 text-center">
                <div className="mx-auto max-w-sm rounded-2xl border border-dashed border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50 px-6 py-10">
                  <FaCreditCard className="mx-auto text-slate-300 mb-3" size={36} />
                  <p className="text-slate-700 dark:text-slate-300 font-medium">No gateways yet</p>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Add a provider and bind it to an API Master record.
                  </p>
                  <Button
                    onClick={handleAddGateway}
                    variant="primary"
                    size="md"
                    icon={FaPlus}
                    iconPosition="left"
                    className="mt-5"
                  >
                    Add your first gateway
                  </Button>
                </div>
              </div>
            ) : (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900">
                    <th className="text-left py-3.5 px-5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      Gateway
                    </th>
                    <th className="text-left py-3.5 px-4 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 hidden lg:table-cell">
                      Type
                    </th>
                    <th className="text-left py-3.5 px-4 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 hidden md:table-cell">
                      API
                    </th>
                    <th className="text-right py-3.5 px-4 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 w-24">
                      Fee
                    </th>
                    <th className="text-center py-3.5 px-4 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 w-28">
                      Status
                    </th>
                    <th className="text-right py-3.5 px-5 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400 w-36">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                  {gateways.map((gateway) => (
                    <tr key={gateway.id} className="hover:bg-slate-50/80 dark:hover:bg-slate-800/80 transition-colors">
                      <td className="py-4 px-5 align-middle">
                        <div className="font-semibold text-slate-900 dark:text-slate-100">{gateway.name}</div>
                        <div className="mt-1 lg:hidden">
                          <span className="inline-flex text-xs font-medium text-slate-600 dark:text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-md">
                            {categoryShortLabel(gateway.category)}
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-4 align-middle hidden lg:table-cell">
                        <span className="inline-flex text-xs font-medium text-indigo-800 dark:text-indigo-300 bg-indigo-50 dark:bg-indigo-950/40 px-2.5 py-1 rounded-lg ring-1 ring-indigo-100 dark:ring-indigo-900">
                          {categoryShortLabel(gateway.category)}
                        </span>
                      </td>
                      <td className="py-4 px-4 align-middle hidden md:table-cell max-w-[200px]">
                        {gateway.api_master ? (
                          <div
                            className="truncate"
                            title={`${gateway.api_master.provider_name} (${gateway.api_master.provider_code})`}
                          >
                            <span className="font-medium text-slate-800 dark:text-slate-200">{gateway.api_master.provider_name}</span>
                            <span className="block text-xs text-slate-500 dark:text-slate-400 truncate">
                              {gateway.api_master.provider_code}
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-400 dark:text-slate-500">Not linked</span>
                        )}
                      </td>
                      <td className="py-4 px-4 align-middle text-right">
                        <span className="tabular-nums font-semibold text-slate-900 dark:text-slate-100">{gateway.charge_rate}%</span>
                      </td>
                      <td className="py-4 px-4 align-middle text-center">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
                            gateway.status === 'active'
                              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-800 dark:text-emerald-300 ring-1 ring-emerald-100 dark:ring-emerald-900'
                              : 'bg-red-50 dark:bg-red-950/40 text-red-800 dark:text-red-300 ring-1 ring-red-100 dark:ring-red-900'
                          }`}
                        >
                          {gateway.status === 'active' ? <FaCircleCheck size={12} /> : <FaCircleExclamation size={12} />}
                          {gateway.status === 'active' ? 'Active' : 'Down'}
                        </span>
                      </td>
                      <td className="py-4 px-5 align-middle">
                        <div className="flex items-center justify-end gap-0.5">
                          <button
                            type="button"
                            onClick={() => handleToggleStatus(gateway.id)}
                            className="rounded-lg p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-indigo-600 transition-colors"
                            title={gateway.status === 'active' ? 'Deactivate' : 'Activate'}
                          >
                            {gateway.status === 'active' ? <FaToggleOn size={22} /> : <FaToggleOff size={22} />}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleEditGateway(gateway)}
                            className="rounded-lg p-2 text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700 hover:text-indigo-600 transition-colors"
                            title="Edit"
                          >
                            <FaPenToSquare size={17} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteGateway(gateway.id)}
                            className="rounded-lg p-2 text-slate-600 dark:text-slate-400 hover:bg-red-50 dark:hover:bg-red-950/60 hover:text-red-600 transition-colors"
                            title="Delete"
                          >
                            <FaTrash size={17} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>
      </div>

      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-2xl w-full border-2 border-blue-200 dark:border-blue-800 my-auto" padding="lg" shadow="xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-slate-100">Add Payment Gateway</h2>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors"
              >
                <FaXmark size={24} />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-6">
              {gatewayFormFields}
              <div className="flex space-x-3 pt-4">
                <Button type="button" onClick={() => setShowAddModal(false)} variant="outline" size="lg" fullWidth>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" size="lg" fullWidth loading={loading}>
                  Add Gateway
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}

      {showEditModal && editingGateway && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-2xl w-full border-2 border-blue-200 dark:border-blue-800 my-auto" padding="lg" shadow="xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900 dark:text-slate-100">Edit Payment Gateway</h2>
              <button
                type="button"
                onClick={() => {
                  setShowEditModal(false);
                  setEditingGateway(null);
                }}
                className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400 transition-colors"
              >
                <FaXmark size={24} />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="space-y-6">
              {gatewayFormFields}
              <div className="flex space-x-3 pt-4">
                <Button
                  type="button"
                  onClick={() => {
                    setShowEditModal(false);
                    setEditingGateway(null);
                  }}
                  variant="outline"
                  size="lg"
                  fullWidth
                >
                  Cancel
                </Button>
                <Button type="submit" variant="primary" size="lg" fullWidth loading={loading}>
                  Update Gateway
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};

export default PaymentGatewaysAdmin;
