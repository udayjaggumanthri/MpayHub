import React, { useState } from 'react';
import { FiX } from 'react-icons/fi';
import { FaPlus, FaPen, FaTrash, FaPaperPlane, FaCircleExclamation } from 'react-icons/fa6';

const AnnouncementManagement = () => {
  const [announcements, setAnnouncements] = useState([
    {
      id: 'ann001',
      title: 'SLPE Gold Travel – Limit Increased!',
      message: 'Transaction limit has been increased for all merchants. Please check your new limits in the dashboard.',
      priority: 'high',
      targetRoles: ['Retailer', 'Distributor'],
      createdAt: new Date('2025-01-15'),
      status: 'active',
    },
    {
      id: 'ann002',
      title: 'New Feature: FastTag Payments',
      message: 'You can now pay FastTag bills directly from the dashboard. This feature is available for all users.',
      priority: 'medium',
      targetRoles: ['All'],
      createdAt: new Date('2025-01-10'),
      status: 'active',
    },
  ]);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingAnnouncement, setEditingAnnouncement] = useState(null);
  const [formData, setFormData] = useState({
    title: '',
    message: '',
    priority: 'high',
    targetRoles: [],
  });

  const availableRoles = ['All', 'Admin', 'Master Distributor', 'Distributor', 'Retailer'];

  const handleInputChange = (field, value) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleRoleToggle = (role) => {
    setFormData((prev) => {
      const roles = prev.targetRoles.includes(role)
        ? prev.targetRoles.filter((r) => r !== role)
        : [...prev.targetRoles, role];
      return { ...prev, targetRoles: roles };
    });
  };

  const handleCreate = () => {
    setFormData({
      title: '',
      message: '',
      priority: 'high',
      targetRoles: [],
    });
    setEditingAnnouncement(null);
    setShowCreateModal(true);
  };

  const handleEdit = (announcement) => {
    setFormData({
      title: announcement.title,
      message: announcement.message,
      priority: announcement.priority,
      targetRoles: announcement.targetRoles,
    });
    setEditingAnnouncement(announcement);
    setShowCreateModal(true);
  };

  const handleSave = () => {
    if (!formData.title.trim() || !formData.message.trim()) {
      alert('Please fill in all required fields');
      return;
    }

    if (formData.targetRoles.length === 0) {
      alert('Please select at least one target role');
      return;
    }

    if (editingAnnouncement) {
      // Update existing announcement
      setAnnouncements((prev) =>
        prev.map((ann) =>
          ann.id === editingAnnouncement.id
            ? {
                ...ann,
                title: formData.title,
                message: formData.message,
                priority: formData.priority,
                targetRoles: formData.targetRoles,
              }
            : ann
        )
      );
    } else {
      // Create new announcement
      const newAnnouncement = {
        id: `ann${String(announcements.length + 1).padStart(3, '0')}`,
        title: formData.title,
        message: formData.message,
        priority: formData.priority,
        targetRoles: formData.targetRoles,
        createdAt: new Date(),
        status: 'active',
      };
      setAnnouncements((prev) => [newAnnouncement, ...prev]);
    }

    // In real app, this would call an API to save to backend
    console.log('Saving announcement:', formData);

    setShowCreateModal(false);
    setFormData({
      title: '',
      message: '',
      priority: 'high',
      targetRoles: [],
    });
    setEditingAnnouncement(null);
  };

  const handleDelete = (id) => {
    if (window.confirm('Are you sure you want to delete this announcement?')) {
      setAnnouncements((prev) => prev.filter((ann) => ann.id !== id));
      // In real app, this would call an API to delete from backend
      console.log('Deleting announcement:', id);
    }
  };

  const handlePush = (announcement) => {
    // In real app, this would call an API to push announcement to selected roles
    alert(`Pushing announcement "${announcement.title}" to: ${announcement.targetRoles.join(', ')}`);
    console.log('Pushing announcement:', announcement);
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-800 border-red-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'low':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white rounded-xl shadow-sm p-6 border border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Announcement Management</h1>
            <p className="text-sm text-gray-600 mt-1">
              Create and push announcements to specific user roles
            </p>
          </div>
          <button
            onClick={handleCreate}
            className="flex items-center space-x-2 px-5 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-600 text-white rounded-xl hover:from-blue-700 hover:to-indigo-700 transition-all shadow-lg hover:shadow-xl transform hover:scale-105"
          >
            <FaPlus size={20} />
            <span className="font-semibold">Create Announcement</span>
          </button>
        </div>
      </div>

      {/* Announcements List */}
      <div className="bg-white rounded-xl shadow-sm border border-gray-200">
        <div className="p-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Active Announcements</h2>
          {announcements.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              <FaCircleExclamation size={56} className="mx-auto mb-4 text-gray-300" />
              <p>No announcements created yet</p>
              <p className="text-sm mt-2">Click "Create Announcement" to get started</p>
            </div>
          ) : (
            <div className="space-y-4">
              {announcements.map((announcement) => (
                <div
                  key={announcement.id}
                  className="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-2">
                        <h3 className="text-lg font-semibold text-gray-900">
                          {announcement.title}
                        </h3>
                        <span
                          className={`px-2 py-1 rounded-full text-xs font-semibold border ${getPriorityColor(
                            announcement.priority
                          )}`}
                        >
                          {announcement.priority.toUpperCase()}
                        </span>
                      </div>
                      <p className="text-gray-600 mb-3">{announcement.message}</p>
                      <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500">
                        <span className="font-medium">Target Roles:</span>
                        {announcement.targetRoles.map((role) => (
                          <span
                            key={role}
                            className="px-2 py-1 bg-gray-100 rounded text-gray-700"
                          >
                            {role}
                          </span>
                        ))}
                        <span className="ml-2">
                          • Created: {announcement.createdAt.toLocaleDateString('en-IN')}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2 ml-4">
                      <button
                        onClick={() => handlePush(announcement)}
                        className="p-2.5 text-green-600 hover:bg-gradient-to-br hover:from-green-50 hover:to-emerald-50 rounded-xl transition-all hover:scale-110 shadow-sm hover:shadow-md"
                        title="Push to users"
                      >
                        <FaPaperPlane size={20} />
                      </button>
                      <button
                        onClick={() => handleEdit(announcement)}
                        className="p-2.5 text-blue-600 hover:bg-gradient-to-br hover:from-blue-50 hover:to-indigo-50 rounded-xl transition-all hover:scale-110 shadow-sm hover:shadow-md"
                        title="Edit"
                      >
                        <FaPen size={20} />
                      </button>
                      <button
                        onClick={() => handleDelete(announcement.id)}
                        className="p-2.5 text-red-600 hover:bg-gradient-to-br hover:from-red-50 hover:to-pink-50 rounded-xl transition-all hover:scale-110 shadow-sm hover:shadow-md"
                        title="Delete"
                      >
                        <FaTrash size={20} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Create/Edit Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">
                  {editingAnnouncement ? 'Edit Announcement' : 'Create New Announcement'}
                </h2>
                <button
                  onClick={() => {
                    setShowCreateModal(false);
                    setEditingAnnouncement(null);
                    setFormData({
                      title: '',
                      message: '',
                      priority: 'high',
                      targetRoles: [],
                    });
                  }}
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <FiX size={24} />
                </button>
              </div>

              <div className="space-y-4">
                {/* Title */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Title <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => handleInputChange('title', e.target.value)}
                    placeholder="e.g., SLPE Gold Travel – Limit Increased!"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                {/* Message */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Message <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={formData.message}
                    onChange={(e) => handleInputChange('message', e.target.value)}
                    placeholder="Enter the announcement message..."
                    rows={4}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                {/* Priority */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Priority <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={formData.priority}
                    onChange={(e) => handleInputChange('priority', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="high">High (Shows as pop-up on login)</option>
                    <option value="medium">Medium (Shows in notification bell)</option>
                    <option value="low">Low (Shows in notification bell)</option>
                  </select>
                </div>

                {/* Target Roles */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Target Roles <span className="text-red-500">*</span>
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {availableRoles.map((role) => (
                      <label
                        key={role}
                        className="flex items-center space-x-2 p-3 border border-gray-300 rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
                      >
                        <input
                          type="checkbox"
                          checked={formData.targetRoles.includes(role)}
                          onChange={() => handleRoleToggle(role)}
                          className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                        />
                        <span className="text-sm text-gray-700">{role}</span>
                      </label>
                    ))}
                  </div>
                  {formData.targetRoles.length === 0 && (
                    <p className="text-sm text-red-500 mt-1">
                      Please select at least one target role
                    </p>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end space-x-3 mt-6 pt-6 border-t border-gray-200">
                <button
                  onClick={() => {
                    setShowCreateModal(false);
                    setEditingAnnouncement(null);
                    setFormData({
                      title: '',
                      message: '',
                      priority: 'high',
                      targetRoles: [],
                    });
                  }}
                  className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                >
                  {editingAnnouncement ? 'Update' : 'Create'} Announcement
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default AnnouncementManagement;
