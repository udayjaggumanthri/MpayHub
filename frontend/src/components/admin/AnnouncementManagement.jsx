import React, { useState, useEffect, useCallback } from 'react';
import { FiX } from 'react-icons/fi';
import {
  FaPlus,
  FaPen,
  FaTrash,
  FaCircleExclamation,
  FaMagnifyingGlass,
  FaList,
  FaTableCells,
  FaChevronLeft,
  FaChevronRight,
  FaEye,
  FaChevronDown,
  FaChevronUp,
} from 'react-icons/fa6';
import { adminAPI } from '../../services/api';
import {
  ANNOUNCEMENT_IMAGE_MAX_BYTES,
  parseAnnouncementListResponse,
  getStoredAnnouncementAdminViewMode,
  setStoredAnnouncementAdminViewMode,
} from '../../utils/announcements';

const availableRoles = ['All', 'Admin', 'Master Distributor', 'Distributor', 'Retailer'];

const PAGE_SIZE_OPTIONS = [12, 24, 48];

const mapFromApi = (item) => ({
  id: item.id,
  title: item.title ?? '',
  message: item.message ?? '',
  priority: item.priority,
  targetRoles: Array.isArray(item.target_roles) ? item.target_roles : [],
  createdAt: item.created_at ? new Date(item.created_at) : new Date(),
  is_active: item.is_active !== false,
  image_url: item.image_url || null,
});

const emptyForm = () => ({
  title: '',
  message: '',
  priority: 'high',
  targetRoles: [],
});

const formatCreated = (d) =>
  d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });

const displayTitle = (a) => {
  const t = (a.title || '').trim();
  if (t) return t;
  if (a.image_url) return 'Image announcement';
  return 'Announcement';
};

const CompactRowActions = ({ announcement, onView, onToggleActive, onEdit, onDelete }) => (
  <div className="flex items-center justify-center gap-1 flex-shrink-0">
    <button
      type="button"
      onClick={() => onView(announcement)}
      className="p-1.5 text-slate-600 hover:bg-slate-100 rounded-lg text-xs font-medium"
      title="View full content"
    >
      <FaEye size={16} />
    </button>
    <button
      type="button"
      onClick={() => onEdit(announcement)}
      className="p-1.5 text-blue-600 hover:bg-blue-50 rounded-lg"
      title="Edit"
    >
      <FaPen size={16} />
    </button>
    <button
      type="button"
      onClick={() => onToggleActive(announcement)}
      className={`px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wide ${
        announcement.is_active
          ? 'text-amber-800 bg-amber-100 hover:bg-amber-200'
          : 'text-emerald-800 bg-emerald-100 hover:bg-emerald-200'
      }`}
      title={announcement.is_active ? 'Deactivate' : 'Activate'}
    >
      {announcement.is_active ? 'Off' : 'On'}
    </button>
    <button
      type="button"
      onClick={() => onDelete(announcement.id)}
      className="p-1.5 text-red-600 hover:bg-red-50 rounded-lg"
      title="Delete"
    >
      <FaTrash size={16} />
    </button>
  </div>
);

const AnnouncementManagement = () => {
  const [announcements, setAnnouncements] = useState([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [saveError, setSaveError] = useState('');

  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [filterPriority, setFilterPriority] = useState('');
  const [filterStatus, setFilterStatus] = useState('all');
  const [filterRole, setFilterRole] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [filtersExpanded, setFiltersExpanded] = useState(false);

  const [viewMode, setViewMode] = useState(() => getStoredAnnouncementAdminViewMode());
  const [viewDetailAnnouncement, setViewDetailAnnouncement] = useState(null);

  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingAnnouncement, setEditingAnnouncement] = useState(null);
  const [formData, setFormData] = useState(emptyForm);
  const [imageFile, setImageFile] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [removeImage, setRemoveImage] = useState(false);
  const [saving, setSaving] = useState(false);

  const revokePreview = useCallback(() => {
    if (imagePreview && imagePreview.startsWith('blob:')) {
      URL.revokeObjectURL(imagePreview);
    }
  }, [imagePreview]);

  useEffect(() => {
    const t = setTimeout(() => {
      setDebouncedSearch(searchInput.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(t);
  }, [searchInput]);

  const loadAnnouncements = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    const params = {
      page,
      page_size: pageSize,
    };
    if (debouncedSearch) params.search = debouncedSearch;
    if (filterPriority) params.priority = filterPriority;
    if (filterStatus === 'active') params.is_active = true;
    if (filterStatus === 'inactive') params.is_active = false;
    if (dateFrom) params.created_after = dateFrom;
    if (dateTo) params.created_before = dateTo;
    if (filterRole) params.target_role = filterRole;

    const result = await adminAPI.listAnnouncements(params);
    setLoading(false);
    if (!result.success) {
      setLoadError(result.message || 'Failed to load announcements');
      setAnnouncements([]);
      setTotalCount(0);
      return;
    }
    const { list, totalCount: count } = parseAnnouncementListResponse(result);
    const mapped = list.map(mapFromApi);
    setAnnouncements(mapped);
    setTotalCount(count);

    const totalPages = Math.max(1, Math.ceil(count / pageSize));
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [
    page,
    pageSize,
    debouncedSearch,
    filterPriority,
    filterStatus,
    filterRole,
    dateFrom,
    dateTo,
  ]);

  useEffect(() => {
    loadAnnouncements();
  }, [loadAnnouncements]);

  useEffect(() => {
    return () => {
      revokePreview();
    };
  }, [revokePreview]);

  const setViewAndPersist = (mode) => {
    const next = mode === 'grid' ? 'grid' : 'list';
    setViewMode(next);
    setStoredAnnouncementAdminViewMode(next);
  };

  const clearFilters = () => {
    setSearchInput('');
    setDebouncedSearch('');
    setFilterPriority('');
    setFilterStatus('all');
    setFilterRole('');
    setDateFrom('');
    setDateTo('');
    setPage(1);
  };

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

  const resetModalState = () => {
    revokePreview();
    setImagePreview(null);
    setImageFile(null);
    setRemoveImage(false);
    setFormData(emptyForm());
    setEditingAnnouncement(null);
    setSaveError('');
  };

  const handleCreate = () => {
    resetModalState();
    setShowCreateModal(true);
  };

  const handleEdit = (announcement) => {
    setViewDetailAnnouncement(null);
    resetModalState();
    setFormData({
      title: announcement.title,
      message: announcement.message,
      priority: announcement.priority,
      targetRoles: [...announcement.targetRoles],
    });
    setEditingAnnouncement(announcement);
    if (announcement.image_url) {
      setImagePreview(announcement.image_url);
    }
    setShowCreateModal(true);
  };

  const handleImageChange = (e) => {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    if (file.size > ANNOUNCEMENT_IMAGE_MAX_BYTES) {
      alert('Image must be 5 MB or smaller.');
      return;
    }
    revokePreview();
    setImageFile(file);
    setRemoveImage(false);
    setImagePreview(URL.createObjectURL(file));
  };

  const handleClearImage = () => {
    revokePreview();
    setImageFile(null);
    setImagePreview(null);
    if (editingAnnouncement?.image_url) {
      setRemoveImage(true);
    }
  };

  const hasContent = () => {
    const msg = formData.message.trim();
    const hasNew = !!imageFile;
    const keptServerImage =
      !!editingAnnouncement?.image_url && !removeImage && !imageFile;
    return Boolean(msg || hasNew || keptServerImage);
  };

  const handleSave = async () => {
    setSaveError('');
    if (!hasContent()) {
      setSaveError('Add a message, an image, or both.');
      return;
    }
    if (formData.targetRoles.length === 0) {
      setSaveError('Please select at least one target role.');
      return;
    }

    setSaving(true);
    const hasNewFile = !!imageFile;
    const clearingImage = Boolean(
      editingAnnouncement?.image_url && removeImage && !imageFile
    );

    let result;
    if (editingAnnouncement) {
      if (hasNewFile || clearingImage) {
        const fd = new FormData();
        fd.append('title', formData.title.trim());
        fd.append('message', formData.message.trim());
        fd.append('priority', formData.priority);
        fd.append('target_roles', JSON.stringify(formData.targetRoles));
        fd.append('is_active', editingAnnouncement.is_active ? 'true' : 'false');
        if (hasNewFile) fd.append('image', imageFile);
        if (clearingImage) fd.append('remove_image', 'true');
        result = await adminAPI.updateAnnouncement(editingAnnouncement.id, fd);
      } else {
        result = await adminAPI.updateAnnouncement(editingAnnouncement.id, {
          title: formData.title.trim(),
          message: formData.message.trim(),
          priority: formData.priority,
          target_roles: formData.targetRoles,
          is_active: editingAnnouncement.is_active,
        });
      }
    } else if (hasNewFile) {
      const fd = new FormData();
      fd.append('title', formData.title.trim());
      fd.append('message', formData.message.trim());
      fd.append('priority', formData.priority);
      fd.append('target_roles', JSON.stringify(formData.targetRoles));
      fd.append('is_active', 'true');
      fd.append('image', imageFile);
      result = await adminAPI.createAnnouncement(fd);
    } else {
      result = await adminAPI.createAnnouncement({
        title: formData.title.trim(),
        message: formData.message.trim(),
        priority: formData.priority,
        target_roles: formData.targetRoles,
        is_active: true,
      });
    }

    setSaving(false);
    if (!result.success) {
      const errs = result.errors?.length ? result.errors.join(' ') : '';
      setSaveError([result.message, errs].filter(Boolean).join(' ') || 'Save failed');
      return;
    }

    setShowCreateModal(false);
    resetModalState();
    loadAnnouncements();
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this announcement?')) return;
    const result = await adminAPI.deleteAnnouncement(id);
    if (!result.success) {
      alert(result.message || 'Delete failed');
      return;
    }
    setViewDetailAnnouncement((cur) => (cur?.id === id ? null : cur));
    loadAnnouncements();
  };

  const handleToggleActive = async (announcement) => {
    const result = await adminAPI.patchAnnouncement(announcement.id, {
      is_active: !announcement.is_active,
    });
    if (!result.success) {
      alert(result.message || 'Update failed');
      return;
    }
    setViewDetailAnnouncement((cur) =>
      cur?.id === announcement.id ? { ...cur, is_active: !announcement.is_active } : cur
    );
    loadAnnouncements();
  };

  const getPriorityColor = (priority) => {
    switch (priority) {
      case 'high':
        return 'bg-red-50 text-red-800 border-red-200';
      case 'medium':
        return 'bg-amber-50 text-amber-900 border-amber-200';
      case 'low':
        return 'bg-blue-50 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-50 text-gray-800 border-gray-200';
    }
  };

  const totalPages = Math.max(1, Math.ceil(totalCount / pageSize));

  const hasActiveFilters =
    debouncedSearch ||
    filterPriority ||
    filterStatus !== 'all' ||
    filterRole ||
    dateFrom ||
    dateTo;

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow-sm px-4 py-3 border border-gray-200">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold text-gray-900">Announcement Management</h1>
            <p className="text-xs text-gray-500 mt-0.5">
              Directory alerts — compact list; use View for full detail
            </p>
          </div>
          <button
            type="button"
            onClick={handleCreate}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-semibold hover:bg-blue-700 shadow-sm"
          >
            <FaPlus size={16} />
            Create
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        {/* Compact toolbar */}
        <div className="px-3 py-2 border-b border-gray-100 bg-gray-50/80">
          <div className="flex flex-wrap items-center gap-2">
            <div className="relative flex-1 min-w-[160px] max-w-md">
              <FaMagnifyingGlass className="absolute left-2 top-1/2 -translate-y-1/2 text-gray-400" size={14} />
              <input
                type="search"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search title or message…"
                className="w-full pl-8 pr-2 py-1.5 text-sm border border-gray-200 rounded-md bg-white focus:ring-1 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
            <select
              value={filterPriority}
              onChange={(e) => {
                setFilterPriority(e.target.value);
                setPage(1);
              }}
              className="text-sm border border-gray-200 rounded-md py-1.5 px-2 bg-white max-w-[120px]"
              title="Priority"
            >
              <option value="">All pri.</option>
              <option value="high">High</option>
              <option value="medium">Med</option>
              <option value="low">Low</option>
            </select>
            <select
              value={filterStatus}
              onChange={(e) => {
                setFilterStatus(e.target.value);
                setPage(1);
              }}
              className="text-sm border border-gray-200 rounded-md py-1.5 px-2 bg-white"
            >
              <option value="all">All status</option>
              <option value="active">Active</option>
              <option value="inactive">Inactive</option>
            </select>
            <select
              value={pageSize}
              onChange={(e) => {
                setPageSize(Number(e.target.value));
                setPage(1);
              }}
              className="text-sm border border-gray-200 rounded-md py-1.5 px-2 bg-white"
            >
              {PAGE_SIZE_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n}/page
                </option>
              ))}
            </select>
            <div className="flex rounded-md border border-gray-200 p-0.5 bg-white ml-auto">
              <button
                type="button"
                onClick={() => setViewAndPersist('list')}
                className={`p-1.5 rounded ${viewMode === 'list' ? 'bg-slate-100 text-blue-700' : 'text-gray-500'}`}
                title="List view"
              >
                <FaList size={15} />
              </button>
              <button
                type="button"
                onClick={() => setViewAndPersist('grid')}
                className={`p-1.5 rounded ${viewMode === 'grid' ? 'bg-slate-100 text-blue-700' : 'text-gray-500'}`}
                title="Grid view"
              >
                <FaTableCells size={15} />
              </button>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setFiltersExpanded((e) => !e)}
            className="mt-1.5 flex items-center gap-1 text-xs text-blue-600 font-medium hover:text-blue-800"
          >
            {filtersExpanded ? <FaChevronUp size={12} /> : <FaChevronDown size={12} />}
            {filtersExpanded ? 'Hide' : 'More filters'} (dates, role)
          </button>

          {filtersExpanded && (
            <div className="mt-2 flex flex-wrap items-end gap-2 pt-2 border-t border-gray-200/80">
              <select
                value={filterRole}
                onChange={(e) => {
                  setFilterRole(e.target.value);
                  setPage(1);
                }}
                className="text-sm border border-gray-200 rounded-md py-1.5 px-2 bg-white min-w-[140px]"
              >
                <option value="">Any role</option>
                {availableRoles.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              <div className="flex items-center gap-1">
                <input
                  type="date"
                  value={dateFrom}
                  onChange={(e) => {
                    setDateFrom(e.target.value);
                    setPage(1);
                  }}
                  className="text-sm border border-gray-200 rounded-md py-1.5 px-2"
                  title="Created from"
                />
                <span className="text-gray-400 text-xs">→</span>
                <input
                  type="date"
                  value={dateTo}
                  onChange={(e) => {
                    setDateTo(e.target.value);
                    setPage(1);
                  }}
                  className="text-sm border border-gray-200 rounded-md py-1.5 px-2"
                  title="Created to"
                />
              </div>
              <button
                type="button"
                onClick={clearFilters}
                disabled={!hasActiveFilters && !searchInput}
                className="text-xs px-2 py-1.5 rounded-md border border-gray-300 text-gray-700 hover:bg-gray-50 disabled:opacity-40"
              >
                Clear all
              </button>
              <span className="text-[10px] text-gray-400">UTC date range</span>
            </div>
          )}
        </div>

        <div className="px-3 py-2 flex items-center justify-between gap-2 border-b border-gray-50">
          <h3 className="text-sm font-semibold text-gray-800">Announcements</h3>
          {!loading && !loadError && (
            <p className="text-xs text-gray-500">
              {totalCount === 0
                ? '0 rows'
                : `${(page - 1) * pageSize + 1}–${Math.min(page * pageSize, totalCount)} of ${totalCount}`}
            </p>
          )}
        </div>

        <div className="p-3">
          {loading && <div className="text-center py-8 text-sm text-gray-500">Loading…</div>}
          {!loading && loadError && (
            <div className="text-center py-6 text-red-600 text-sm">{loadError}</div>
          )}
          {!loading && !loadError && announcements.length === 0 && (
            <div className="text-center py-10 text-gray-500">
              <FaCircleExclamation size={40} className="mx-auto mb-2 text-gray-300" />
              <p className="text-sm">No matching announcements</p>
            </div>
          )}

          {!loading && !loadError && announcements.length > 0 && viewMode === 'list' && (
            <div className="overflow-x-auto rounded-lg border border-gray-200">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 text-left text-[10px] uppercase tracking-wider text-gray-500 border-b border-gray-200">
                    <th className="px-2 py-2 w-14 font-semibold">Img</th>
                    <th className="px-2 py-2 font-semibold min-w-[140px]">Title</th>
                    <th className="px-2 py-2 font-semibold whitespace-nowrap hidden sm:table-cell">Created</th>
                    <th className="px-2 py-2 font-semibold">Priority</th>
                    <th className="px-2 py-2 font-semibold">Status</th>
                    <th className="px-2 py-2 font-semibold text-center w-[140px]">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {announcements.map((a) => (
                    <tr
                      key={a.id}
                      className={`hover:bg-gray-50/80 ${!a.is_active ? 'bg-amber-50/40' : ''}`}
                    >
                      <td className="px-2 py-2 align-middle">
                        {a.image_url ? (
                          <button
                            type="button"
                            onClick={() => setViewDetailAnnouncement(a)}
                            className="block w-11 h-11 rounded border border-gray-200 overflow-hidden bg-gray-50 focus:ring-2 focus:ring-blue-400"
                            title="View"
                          >
                            <img src={a.image_url} alt="" className="w-full h-full object-cover" />
                          </button>
                        ) : (
                          <div className="w-11 h-11 rounded border border-dashed border-gray-200 bg-gray-50 flex items-center justify-center text-[9px] text-gray-400">
                            —
                          </div>
                        )}
                      </td>
                      <td className="px-2 py-2 align-middle">
                        <button
                          type="button"
                          onClick={() => setViewDetailAnnouncement(a)}
                          className="text-left font-medium text-gray-900 hover:text-blue-700 line-clamp-2"
                        >
                          {displayTitle(a)}
                        </button>
                        <p className="sm:hidden text-[10px] text-gray-500 mt-0.5">
                          {formatCreated(a.createdAt)}
                        </p>
                      </td>
                      <td className="px-2 py-2 align-middle text-gray-600 text-xs whitespace-nowrap hidden sm:table-cell">
                        {formatCreated(a.createdAt)}
                      </td>
                      <td className="px-2 py-2 align-middle">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-[10px] font-bold border uppercase ${getPriorityColor(
                            a.priority
                          )}`}
                        >
                          {a.priority}
                        </span>
                      </td>
                      <td className="px-2 py-2 align-middle">
                        <span
                          className={`inline-block px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            a.is_active
                              ? 'bg-emerald-100 text-emerald-800'
                              : 'bg-gray-200 text-gray-700'
                          }`}
                        >
                          {a.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-1 py-1 align-middle">
                        <CompactRowActions
                          announcement={a}
                          onView={setViewDetailAnnouncement}
                          onToggleActive={handleToggleActive}
                          onEdit={handleEdit}
                          onDelete={handleDelete}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {!loading && !loadError && announcements.length > 0 && viewMode === 'grid' && (
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-2">
              {announcements.map((a) => (
                <div
                  key={a.id}
                  className={`rounded-lg border p-2 flex flex-col gap-1.5 ${
                    a.is_active ? 'border-gray-200 bg-white' : 'border-amber-200 bg-amber-50/50'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setViewDetailAnnouncement(a)}
                    className="aspect-[4/3] w-full rounded-md border border-gray-100 bg-gray-50 overflow-hidden flex items-center justify-center focus:ring-2 focus:ring-blue-400"
                  >
                    {a.image_url ? (
                      <img src={a.image_url} alt="" className="w-full h-full object-cover" />
                    ) : (
                      <span className="text-[10px] text-gray-400">No image</span>
                    )}
                  </button>
                  <p className="text-xs font-semibold text-gray-900 line-clamp-2 leading-snug min-h-[2rem]">
                    {displayTitle(a)}
                  </p>
                  <div className="flex items-center justify-between gap-1 flex-wrap">
                    <span
                      className={`px-1.5 py-0.5 rounded text-[9px] font-bold border uppercase ${getPriorityColor(
                        a.priority
                      )}`}
                    >
                      {a.priority}
                    </span>
                    <span className="text-[10px] text-gray-500">
                      {a.createdAt.toLocaleDateString('en-IN', { day: '2-digit', month: '2-digit' })}
                    </span>
                  </div>
                  <span
                    className={`text-[9px] font-bold uppercase tracking-wide w-fit px-1.5 py-0.5 rounded ${
                      a.is_active ? 'bg-emerald-100 text-emerald-800' : 'bg-gray-200 text-gray-700'
                    }`}
                  >
                    {a.is_active ? 'Active' : 'Off'}
                  </span>
                  <div className="pt-1 border-t border-gray-100 mt-auto">
                    <CompactRowActions
                      announcement={a}
                      onView={setViewDetailAnnouncement}
                      onToggleActive={handleToggleActive}
                      onEdit={handleEdit}
                      onDelete={handleDelete}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          {!loading && !loadError && totalCount > 0 && (
            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-gray-100">
              <p className="text-xs text-gray-600">
                Page <strong>{page}</strong> / {totalPages}
              </p>
              <div className="flex gap-1">
                <button
                  type="button"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-gray-200 text-xs font-medium disabled:opacity-40"
                >
                  <FaChevronLeft size={12} />
                  Prev
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md border border-gray-200 text-xs font-medium disabled:opacity-40"
                >
                  Next
                  <FaChevronRight size={12} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Read-only view modal */}
      {viewDetailAnnouncement && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/50"
          role="presentation"
          onClick={() => setViewDetailAnnouncement(null)}
        >
          <div
            className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] overflow-y-auto"
            role="dialog"
            aria-modal="true"
            aria-labelledby="ann-view-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="sticky top-0 flex items-center justify-between px-4 py-3 border-b border-gray-100 bg-white">
              <h2 id="ann-view-title" className="text-lg font-bold text-gray-900 pr-4">
                {displayTitle(viewDetailAnnouncement)}
              </h2>
              <button
                type="button"
                onClick={() => setViewDetailAnnouncement(null)}
                className="p-1 rounded-lg text-gray-500 hover:bg-gray-100"
                aria-label="Close"
              >
                <FiX size={22} />
              </button>
            </div>
            <div className="p-4 space-y-3 text-sm">
              <div className="flex flex-wrap gap-2 text-xs">
                <span
                  className={`px-2 py-0.5 rounded font-bold border uppercase ${getPriorityColor(
                    viewDetailAnnouncement.priority
                  )}`}
                >
                  {viewDetailAnnouncement.priority}
                </span>
                <span
                  className={`px-2 py-0.5 rounded-full font-semibold ${
                    viewDetailAnnouncement.is_active
                      ? 'bg-emerald-100 text-emerald-800'
                      : 'bg-gray-200 text-gray-700'
                  }`}
                >
                  {viewDetailAnnouncement.is_active ? 'Active' : 'Inactive'}
                </span>
                <span className="text-gray-500">{formatCreated(viewDetailAnnouncement.createdAt)}</span>
              </div>
              {viewDetailAnnouncement.image_url && (
                <div className="rounded-lg border border-gray-100 overflow-hidden bg-gray-50">
                  <img
                    src={viewDetailAnnouncement.image_url}
                    alt=""
                    className="w-full max-h-64 object-contain"
                  />
                </div>
              )}
              {(viewDetailAnnouncement.message || '').trim() ? (
                <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {viewDetailAnnouncement.message}
                </p>
              ) : (
                <p className="text-gray-400 italic text-sm">No message text</p>
              )}
              <div>
                <p className="text-xs font-semibold text-gray-500 mb-1">Target roles</p>
                <div className="flex flex-wrap gap-1">
                  {viewDetailAnnouncement.targetRoles.map((role) => (
                    <span key={role} className="text-xs px-2 py-0.5 bg-gray-100 rounded text-gray-700">
                      {role}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-100">
                <button
                  type="button"
                  onClick={() => {
                    const v = viewDetailAnnouncement;
                    setViewDetailAnnouncement(null);
                    handleEdit(v);
                  }}
                  className="px-3 py-2 text-sm font-medium rounded-lg bg-blue-600 text-white hover:bg-blue-700"
                >
                  Edit
                </button>
                <button
                  type="button"
                  onClick={() => setViewDetailAnnouncement(null)}
                  className="px-3 py-2 text-sm font-medium rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black bg-opacity-50">
          <div className="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-2xl font-bold text-gray-900">
                  {editingAnnouncement ? 'Edit announcement' : 'Create new announcement'}
                </h2>
                <button
                  type="button"
                  onClick={() => {
                    setShowCreateModal(false);
                    resetModalState();
                  }}
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                >
                  <FiX size={24} />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Title <span className="text-gray-400 font-normal">(optional)</span>
                  </label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) => handleInputChange('title', e.target.value)}
                    placeholder="e.g. SLPE Gold Travel – limit increased"
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Message{' '}
                    <span className="text-gray-400 font-normal">(optional if image is set)</span>
                  </label>
                  <textarea
                    value={formData.message}
                    onChange={(e) => handleInputChange('message', e.target.value)}
                    placeholder="Announcement text…"
                    rows={4}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Image <span className="text-gray-400 font-normal">(optional)</span>
                  </label>
                  <p className="text-xs text-gray-500 mb-2">
                    JPG, PNG, WebP, or GIF — max 5 MB. You can use text only, image only, or both.
                  </p>
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp,image/gif,.jpg,.jpeg,.png,.webp,.gif"
                    onChange={handleImageChange}
                    className="block w-full text-sm text-gray-600 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                  />
                  {imagePreview && (
                    <div className="mt-3 relative inline-block">
                      <img
                        src={imagePreview}
                        alt="Preview"
                        className="max-h-40 rounded-lg border border-gray-200 object-contain bg-gray-50"
                      />
                      <button
                        type="button"
                        onClick={handleClearImage}
                        className="mt-2 text-sm text-red-600 hover:text-red-800 font-medium"
                      >
                        Remove image
                      </button>
                    </div>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Priority <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={formData.priority}
                    onChange={(e) => handleInputChange('priority', e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    <option value="high">High (pop-up on login)</option>
                    <option value="medium">Medium (notification bell)</option>
                    <option value="low">Low (notification bell)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Target roles <span className="text-red-500">*</span>
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
                    <p className="text-sm text-red-500 mt-1">Select at least one target role</p>
                  )}
                </div>

                {saveError && (
                  <p className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                    {saveError}
                  </p>
                )}
              </div>

              <div className="flex items-center justify-end space-x-3 mt-6 pt-6 border-t border-gray-200">
                <button
                  type="button"
                  disabled={saving}
                  onClick={() => {
                    setShowCreateModal(false);
                    resetModalState();
                  }}
                  className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={saving}
                  onClick={handleSave}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
                >
                  {saving ? 'Saving…' : editingAnnouncement ? 'Update' : 'Create'}
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
