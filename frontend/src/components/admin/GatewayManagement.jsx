import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import {
  getAllPaymentGateways,
  addPaymentGateway,
  updatePaymentGateway,
  deletePaymentGateway,
  toggleGatewayStatus,
} from '../../services/mockData';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import { FaPlus, FaPenToSquare, FaTrash, FaToggleOn, FaToggleOff, FaCircleCheck, FaCircleExclamation, FaXmark } from 'react-icons/fa6';

const GatewayManagement = () => {
  const { user } = useAuth();
  const [gateways, setGateways] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingGateway, setEditingGateway] = useState(null);
  const [formData, setFormData] = useState({
    name: '',
    chargeRate: '',
    category: 'third-party',
    visibleToRoles: [],
  });

  const roles = ['Admin', 'Master Distributor', 'Distributor', 'Retailer'];
  const categories = [
    { value: 'slpe-gold', label: 'SLPE Gold Travel' },
    { value: 'slpe-silver', label: 'SLPE Silver Prime Edu' },
    { value: 'third-party', label: 'Third Party (Razorpay, PayU, etc.)' },
  ];

  useEffect(() => {
    loadGateways();
  }, []);

  const loadGateways = () => {
    const result = getAllPaymentGateways();
    if (result.success) {
      setGateways(result.gateways);
    }
  };

  const handleAddGateway = () => {
    setFormData({
      name: '',
      chargeRate: '',
      category: 'third-party',
      visibleToRoles: [],
    });
    setShowAddModal(true);
  };

  const handleEditGateway = (gateway) => {
    setEditingGateway(gateway);
    setFormData({
      name: gateway.name,
      chargeRate: gateway.chargeRate.toString(),
      category: gateway.category || 'third-party',
      visibleToRoles: [...gateway.visibleToRoles],
    });
    setShowEditModal(true);
  };

  const handleToggleStatus = (gatewayId) => {
    const result = toggleGatewayStatus(gatewayId);
    if (result.success) {
      loadGateways();
    }
  };

  const handleDeleteGateway = (gatewayId) => {
    if (window.confirm('Are you sure you want to delete this gateway? This action cannot be undone.')) {
      const result = deletePaymentGateway(gatewayId);
      if (result.success) {
        loadGateways();
      } else {
        alert(result.message || 'Failed to delete gateway');
      }
    }
  };

  const handleRoleToggle = (role) => {
    const currentRoles = formData.visibleToRoles;
    if (currentRoles.includes(role)) {
      setFormData({
        ...formData,
        visibleToRoles: currentRoles.filter((r) => r !== role),
      });
    } else {
      setFormData({
        ...formData,
        visibleToRoles: [...currentRoles, role],
      });
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!formData.name || !formData.chargeRate || formData.visibleToRoles.length === 0) {
      alert('Please fill in all required fields');
      return;
    }

    setLoading(true);
    const gatewayData = {
      name: formData.name,
      chargeRate: parseFloat(formData.chargeRate),
      category: formData.category,
      visibleToRoles: formData.visibleToRoles,
    };

    let result;
    if (showEditModal && editingGateway) {
      result = updatePaymentGateway(editingGateway.id, gatewayData);
    } else {
      result = addPaymentGateway(gatewayData);
    }

    setLoading(false);
    if (result.success) {
      setShowAddModal(false);
      setShowEditModal(false);
      setEditingGateway(null);
      loadGateways();
    } else {
      alert(result.message || 'Failed to save gateway');
    }
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 px-4 sm:px-0">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">Payment Gateway Management</h1>
          <p className="mt-1 sm:mt-2 text-sm sm:text-base text-gray-600">
            Configure and manage payment gateways, service charges, and role-based visibility
          </p>
        </div>
        <Button
          onClick={handleAddGateway}
          variant="primary"
          size="lg"
          icon={FaPlus}
          iconPosition="left"
          className="mt-4 sm:mt-0"
        >
          Add Gateway
        </Button>
      </div>

      {/* Gateways List */}
      <Card padding="lg">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Gateway Name</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Category</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Service Charge</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Visible To</th>
                <th className="text-left py-3 px-4 font-semibold text-gray-700">Status</th>
                <th className="text-right py-3 px-4 font-semibold text-gray-700">Actions</th>
              </tr>
            </thead>
            <tbody>
              {gateways.length === 0 ? (
                <tr>
                  <td colSpan="6" className="text-center py-8 text-gray-500">
                    No gateways configured. Click "Add Gateway" to get started.
                  </td>
                </tr>
              ) : (
                gateways.map((gateway) => (
                  <tr key={gateway.id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-4 px-4">
                      <div className="font-semibold text-gray-900">{gateway.name}</div>
                    </td>
                    <td className="py-4 px-4">
                      <span className="px-2 py-1 text-xs font-medium rounded-full bg-blue-100 text-blue-700">
                        {categories.find((c) => c.value === gateway.category)?.label || gateway.category}
                      </span>
                    </td>
                    <td className="py-4 px-4">
                      <span className="font-semibold text-gray-900">{gateway.chargeRate}%</span>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex flex-wrap gap-1">
                        {gateway.visibleToRoles.map((role) => (
                          <span
                            key={role}
                            className="px-2 py-0.5 text-xs rounded bg-gray-100 text-gray-700"
                          >
                            {role}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center space-x-2">
                        {gateway.status === 'active' ? (
                          <>
                            <FaCircleCheck className="text-green-600" size={16} />
                            <span className="text-green-600 font-medium">Active</span>
                          </>
                        ) : (
                          <>
                            <FaCircleExclamation className="text-red-600" size={16} />
                            <span className="text-red-600 font-medium">Down</span>
                          </>
                        )}
                      </div>
                    </td>
                    <td className="py-4 px-4">
                      <div className="flex items-center justify-end space-x-2">
                        <button
                          onClick={() => handleToggleStatus(gateway.id)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title={gateway.status === 'active' ? 'Mark as Down' : 'Mark as Active'}
                        >
                          {gateway.status === 'active' ? (
                            <FaToggleOn size={20} />
                          ) : (
                            <FaToggleOff size={20} />
                          )}
                        </button>
                        <button
                          onClick={() => handleEditGateway(gateway)}
                          className="p-2 text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                          title="Edit Gateway"
                        >
                          <FaPenToSquare size={18} />
                        </button>
                        <button
                          onClick={() => handleDeleteGateway(gateway.id)}
                          className="p-2 text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Delete Gateway"
                        >
                          <FaTrash size={18} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Add Gateway Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-2xl w-full border-2 border-blue-200 my-auto" padding="lg" shadow="xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900">Add Payment Gateway</h2>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <FaXmark size={24} />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Gateway Name <span className="text-red-500">*</span>
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., SLPE Gold Travel - Lite"
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
                  {categories.map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </select>
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
                <p className="mt-1 text-sm text-gray-500">
                  This percentage will be charged on each transaction amount
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-3">
                  Visible To Roles <span className="text-red-500">*</span>
                </label>
                <div className="space-y-2">
                  {roles.map((role) => (
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
                <p className="mt-2 text-sm text-gray-500">
                  Select which roles can see and use this gateway
                </p>
              </div>

              <div className="flex space-x-3 pt-4">
                <Button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  variant="outline"
                  size="lg"
                  fullWidth
                >
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

      {/* Edit Gateway Modal */}
      {showEditModal && editingGateway && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50 overflow-y-auto">
          <Card className="max-w-2xl w-full border-2 border-blue-200 my-auto" padding="lg" shadow="xl">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-xl sm:text-2xl font-bold text-gray-900">Edit Payment Gateway</h2>
              <button
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
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Gateway Name <span className="text-red-500">*</span>
                </label>
                <Input
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., SLPE Gold Travel - Lite"
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
                  {categories.map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </select>
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
                  {roles.map((role) => (
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

export default GatewayManagement;
