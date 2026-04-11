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
  VisibleRolesSummary,
  GATEWAY_CATEGORIES,
  VISIBLE_ROLES,
} from './gatewayAdminShared';

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
    visibleToRoles: [],
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
    setFormData({
      name: '',
      chargeRate: '',
      category: 'third-party',
      apiMasterId: '',
      visibleToRoles: [],
    });
    setShowAddModal(true);
  };

  const handleEditGateway = (gateway) => {
    setEditingGateway(gateway);
    setFormData({
      name: gateway.name,
      chargeRate: gateway.charge_rate?.toString?.() || '',
      category: gateway.category || 'third-party',
      apiMasterId: gateway.api_master?.id ? String(gateway.api_master.id) : '',
      visibleToRoles: [...(gateway.visible_to_roles || [])],
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

  const handleRoleToggle = (role) => {
    const currentRoles = formData.visibleToRoles;
    if (currentRoles.includes(role)) {
      setFormData({ ...formData, visibleToRoles: currentRoles.filter((r) => r !== role) });
    } else {
      setFormData({ ...formData, visibleToRoles: [...currentRoles, role] });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.chargeRate || formData.visibleToRoles.length === 0) {
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
      visible_to_roles: formData.visibleToRoles,
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
      alert(result.message || 'Failed to save gateway');
    }
  };

  const gatewayFormFields = (
    <>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
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
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Category <span className="text-red-500">*</span>
        </label>
        <select
          value={formData.category}
          onChange={(e) => setFormData({ ...formData, category: e.target.value })}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
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
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Payment API Master <span className="text-red-500">*</span>
        </label>
        <select
          value={formData.apiMasterId}
          onChange={(e) => setFormData({ ...formData, apiMasterId: e.target.value })}
          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-gray-900 bg-white"
          required
        >
          <option value="">-- Select Payment API Master --</option>
          {paymentApiMasters.map((m) => (
            <option key={m.id} value={m.id}>
              {m.provider_name} ({m.provider_code}) [{m.status}]
            </option>
          ))}
        </select>
        <p className="mt-1 text-xs text-gray-500">Linked from the API Master module.</p>
      </div>
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
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
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-3">
          Visible To Roles <span className="text-red-500">*</span>
        </label>
        <div className="space-y-2">
          {VISIBLE_ROLES.map((role) => (
            <label key={role} className="flex items-center space-x-2 cursor-pointer">
              <input
                type="checkbox"
                checked={formData.visibleToRoles.includes(role)}
                onChange={() => handleRoleToggle(role)}
                className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
              />
              <span className="text-gray-700">{role}</span>
            </label>
          ))}
        </div>
      </div>
    </>
  );

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 via-white to-slate-50/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <header className="relative overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-br from-indigo-500/[0.07] via-transparent to-violet-500/[0.06] pointer-events-none" />
          <div className="relative px-6 py-8 sm:px-8 sm:py-9 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600 mb-2">
                Admin · Payments
              </p>
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">Payment gateways</h1>
              <p className="mt-2 text-sm sm:text-base text-slate-600 max-w-xl leading-relaxed">
                Connect Razorpay, PayU, or internal rails. Control service charge and which roles can use checkout.
              </p>
            </div>
            <Link
              to="/admin/pay-in-packages"
              className="inline-flex items-center gap-2 self-start rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm font-semibold text-slate-700 shadow-sm hover:border-indigo-200 hover:bg-indigo-50/50 hover:text-indigo-800 transition-colors"
            >
              <FaChartPie className="text-indigo-600" size={18} />
              Pay-in packages &amp; fees
              <FaArrowRight size={14} className="text-slate-400" />
            </Link>
          </div>
        </header>

        <section className="rounded-2xl border border-slate-200/90 bg-white shadow-sm overflow-hidden">
          <div className="flex flex-col gap-4 border-b border-slate-100 bg-slate-50/80 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div className="flex items-start gap-3">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/20">
                <FaCreditCard size={20} />
              </span>
              <div>
                <h2 className="text-lg font-bold text-slate-900">Your gateways</h2>
                <p className="text-sm text-slate-600 mt-0.5">Linked API credentials and visibility by role.</p>
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
                {gateways.length} {gateways.length === 1 ? 'gateway' : 'gateways'}
              </span>
              <Button onClick={handleAddGateway} variant="primary" size="md" icon={FaPlus} iconPosition="left">
                Add gateway
              </Button>
            </div>
          </div>

          <div className="overflow-x-auto">
            {gateways.length === 0 ? (
              <div className="px-6 py-16 text-center">
                <div className="mx-auto max-w-sm rounded-2xl border border-dashed border-slate-200 bg-slate-50/50 px-6 py-10">
                  <FaCreditCard className="mx-auto text-slate-300 mb-3" size={36} />
                  <p className="text-slate-700 font-medium">No gateways yet</p>
                  <p className="text-sm text-slate-500 mt-1">
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
                  <tr className="border-b border-slate-200 bg-white">
                    <th className="text-left py-3.5 px-5 text-xs font-semibold uppercase tracking-wide text-slate-500">
                      Gateway
                    </th>
                    <th className="text-left py-3.5 px-4 text-xs font-semibold uppercase tracking-wide text-slate-500 hidden lg:table-cell">
                      Type
                    </th>
                    <th className="text-left py-3.5 px-4 text-xs font-semibold uppercase tracking-wide text-slate-500 hidden md:table-cell">
                      API
                    </th>
                    <th className="text-right py-3.5 px-4 text-xs font-semibold uppercase tracking-wide text-slate-500 w-24">
                      Fee
                    </th>
                    <th className="text-left py-3.5 px-4 text-xs font-semibold uppercase tracking-wide text-slate-500 min-w-[140px]">
                      Visible to
                    </th>
                    <th className="text-center py-3.5 px-4 text-xs font-semibold uppercase tracking-wide text-slate-500 w-28">
                      Status
                    </th>
                    <th className="text-right py-3.5 px-5 text-xs font-semibold uppercase tracking-wide text-slate-500 w-36">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {gateways.map((gateway) => (
                    <tr key={gateway.id} className="hover:bg-slate-50/80 transition-colors">
                      <td className="py-4 px-5 align-middle">
                        <div className="font-semibold text-slate-900">{gateway.name}</div>
                        <div className="mt-1 lg:hidden">
                          <span className="inline-flex text-xs font-medium text-slate-600 bg-slate-100 px-2 py-0.5 rounded-md">
                            {categoryShortLabel(gateway.category)}
                          </span>
                        </div>
                      </td>
                      <td className="py-4 px-4 align-middle hidden lg:table-cell">
                        <span className="inline-flex text-xs font-medium text-indigo-800 bg-indigo-50 px-2.5 py-1 rounded-lg ring-1 ring-indigo-100">
                          {categoryShortLabel(gateway.category)}
                        </span>
                      </td>
                      <td className="py-4 px-4 align-middle hidden md:table-cell max-w-[200px]">
                        {gateway.api_master ? (
                          <div
                            className="truncate"
                            title={`${gateway.api_master.provider_name} (${gateway.api_master.provider_code})`}
                          >
                            <span className="font-medium text-slate-800">{gateway.api_master.provider_name}</span>
                            <span className="block text-xs text-slate-500 truncate">
                              {gateway.api_master.provider_code}
                            </span>
                          </div>
                        ) : (
                          <span className="text-slate-400">Not linked</span>
                        )}
                      </td>
                      <td className="py-4 px-4 align-middle text-right">
                        <span className="tabular-nums font-semibold text-slate-900">{gateway.charge_rate}%</span>
                      </td>
                      <td className="py-4 px-4 align-middle">
                        <VisibleRolesSummary roles={gateway.visible_to_roles} />
                      </td>
                      <td className="py-4 px-4 align-middle text-center">
                        <span
                          className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${
                            gateway.status === 'active'
                              ? 'bg-emerald-50 text-emerald-800 ring-1 ring-emerald-100'
                              : 'bg-red-50 text-red-800 ring-1 ring-red-100'
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
                            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 hover:text-indigo-600 transition-colors"
                            title={gateway.status === 'active' ? 'Deactivate' : 'Activate'}
                          >
                            {gateway.status === 'active' ? <FaToggleOn size={22} /> : <FaToggleOff size={22} />}
                          </button>
                          <button
                            type="button"
                            onClick={() => handleEditGateway(gateway)}
                            className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 hover:text-indigo-600 transition-colors"
                            title="Edit"
                          >
                            <FaPenToSquare size={17} />
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteGateway(gateway.id)}
                            className="rounded-lg p-2 text-slate-600 hover:bg-red-50 hover:text-red-600 transition-colors"
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
          <Card className="max-w-2xl w-full border-2 border-blue-200 my-auto" padding="lg" shadow="xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900">Add Payment Gateway</h2>
              <button
                type="button"
                onClick={() => setShowAddModal(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
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
          <Card className="max-w-2xl w-full border-2 border-blue-200 my-auto" padding="lg" shadow="xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900">Edit Payment Gateway</h2>
              <button
                type="button"
                onClick={() => {
                  setShowEditModal(false);
                  setEditingGateway(null);
                }}
                className="text-gray-400 hover:text-gray-600 transition-colors"
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
