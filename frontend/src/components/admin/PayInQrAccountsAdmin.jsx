import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { adminAPI } from '../../services/api';
import Card from '../common/Card';
import Input from '../common/Input';
import Button from '../common/Button';
import LoadingSpinner from '../common/LoadingSpinner';
import GatewayFlowStepper from './GatewayFlowStepper';
import { firstErrorMessage } from './gatewayAdminShared';
import { formatCurrency } from '../../utils/formatters';
import {
  FaPlus,
  FaPenToSquare,
  FaTrash,
  FaToggleOn,
  FaToggleOff,
  FaQrcode,
  FaXmark,
  FaArrowRight,
  FaDownload,
} from 'react-icons/fa6';
import { downloadFromUrl } from '../../utils/downloadFile';
import { normalizeAssetUrl } from '../../utils/mediaUrl';

const emptyForm = () => ({
  display_name: '',
  account_display_name: '',
  upi_vpa: '',
  bank_details: '',
  sort_order: '0',
  daily_limit_24h: '100000',
  max_per_txn: '',
  charge_rate: '0',
  status: 'active',
});

const PayInQrAccountsAdmin = () => {
  const [rows, setRows] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState('');
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(emptyForm());
  const [qrImage, setQrImage] = useState(null);
  const [preview, setPreview] = useState('');
  const [saving, setSaving] = useState(false);
  const [unlinkedQrCount, setUnlinkedQrCount] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError('');
    const res = await adminAPI.listPayInQrAccounts({ page, page_size: 20, search: search.trim() || undefined });
    setLoading(false);
    if (res.success) {
      setRows(res.data?.results || []);
      setTotal(res.data?.total || 0);
    } else {
      setRows([]);
      setTotal(0);
      setLoadError(res.message || 'Could not load QR accounts. Check that the backend is migrated and you are logged in as Admin.');
    }
  }, [page, search]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!rows.length) {
      setUnlinkedQrCount(0);
      return undefined;
    }
    let mounted = true;
    adminAPI.listPayInPackages({ page_size: 200 }).then((res) => {
      if (!mounted || !res.success) return;
      const packages = res.data?.results || (Array.isArray(res.data) ? res.data : []);
      const linkedIds = new Set();
      packages.forEach((pkg) => {
        (pkg.package_qr_accounts || []).forEach((q) => linkedIds.add(String(q.id)));
      });
      const unlinked = rows.filter((r) => !linkedIds.has(String(r.id))).length;
      setUnlinkedQrCount(unlinked);
    });
    return () => {
      mounted = false;
    };
  }, [rows]);

  const openCreate = () => {
    setEditing(null);
    setForm(emptyForm());
    setQrImage(null);
    setPreview('');
    setModalOpen(true);
  };

  const handleDownloadQrImage = async (row) => {
    if (!row?.qr_image_url) return;
    const safeName = String(row.display_name || 'qr-account')
      .replace(/[^\w.-]+/g, '-')
      .replace(/^-+|-+$/g, '') || 'qr-account';
    try {
      await downloadFromUrl(normalizeAssetUrl(row.qr_image_url), `${safeName}.png`);
    } catch {
      alert('Could not download QR image. Please try again.');
    }
  };

  const openEdit = (row) => {
    setEditing(row);
    setForm({
      display_name: row.display_name || '',
      account_display_name: row.account_display_name || '',
      upi_vpa: row.upi_vpa || '',
      bank_details: typeof row.bank_details === 'string' ? row.bank_details : JSON.stringify(row.bank_details || ''),
      sort_order: String(row.sort_order ?? 0),
      daily_limit_24h: row.daily_limit_24h != null ? String(row.daily_limit_24h) : '100000',
      max_per_txn: row.max_per_txn != null ? String(row.max_per_txn) : '',
      charge_rate: row.charge_rate != null ? String(row.charge_rate) : '0',
      status: row.status || 'active',
    });
    setQrImage(null);
    setPreview(row.qr_image_url || '');
    setModalOpen(true);
  };

  const buildFormData = () => {
    const fd = new FormData();
    fd.append('display_name', form.display_name.trim());
    fd.append('account_display_name', form.account_display_name.trim());
    fd.append('upi_vpa', form.upi_vpa.trim());
    const bankRaw = form.bank_details.trim();
    if (bankRaw) fd.append('bank_details', bankRaw);
    fd.append('sort_order', form.sort_order || '0');
    fd.append('status', form.status);
    if (form.daily_limit_24h) fd.append('daily_limit_24h', form.daily_limit_24h);
    if (form.max_per_txn) fd.append('max_per_txn', form.max_per_txn);
    if (form.charge_rate !== '') fd.append('charge_rate', form.charge_rate || '0');
    if (qrImage) fd.append('qr_image', qrImage);
    return fd;
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (!form.display_name.trim()) {
      alert('Display name is required');
      return;
    }
    if (!editing && !qrImage) {
      alert('QR image is required for new accounts');
      return;
    }
    setSaving(true);
    const fd = buildFormData();
    const res = editing
      ? await adminAPI.updatePayInQrAccount(editing.id, fd)
      : await adminAPI.createPayInQrAccount(fd);
    setSaving(false);
    if (!res.success) {
      alert(firstErrorMessage(res, 'Could not save QR account'));
      return;
    }
    setModalOpen(false);
    load();
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Remove this QR account?')) return;
    const res = await adminAPI.deletePayInQrAccount(id);
    if (res.success) load();
    else alert(res.message || 'Delete failed');
  };

  const handleToggle = async (id) => {
    const res = await adminAPI.togglePayInQrAccountStatus(id);
    if (res.success) load();
    else alert(res.message || 'Could not update status');
  };

  const totalPages = Math.max(1, Math.ceil(total / 20));

  return (
    <div className="min-h-[calc(100vh-6rem)] bg-gradient-to-b from-slate-50 dark:from-slate-900 via-white dark:via-slate-900 to-slate-50/80 dark:to-slate-900/80">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <GatewayFlowStepper
          currentStep="qr-accounts"
          subtitle="Upload UPI QR codes and set daily collection limits. Link accounts to pay-in packages next."
        />

        <header className="relative overflow-hidden rounded-2xl border border-slate-200/80 dark:border-slate-700/80 bg-white dark:bg-slate-900 shadow-sm">
          <div className="absolute inset-0 bg-gradient-to-br from-emerald-500/[0.07] via-transparent to-teal-500/[0.06] pointer-events-none" />
          <div className="relative px-6 py-8 sm:px-8 sm:py-9 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-emerald-600 dark:text-emerald-400 mb-2">
                Admin · Manual QR pay-in
              </p>
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-slate-100 tracking-tight flex items-center gap-2">
                <FaQrcode className="text-emerald-600 dark:text-emerald-400" />
                QR collection accounts
              </h1>
              <p className="mt-2 text-sm sm:text-base text-slate-600 dark:text-slate-400 max-w-xl leading-relaxed">
                Manage UPI QR images shown on Load Money. Retailers pay externally and submit UTR + screenshot for admin review.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link
                to="/admin/pay-in-qr-operations"
                className="inline-flex items-center gap-2 rounded-xl border border-emerald-200 dark:border-emerald-800 bg-emerald-50/50 dark:bg-emerald-950/40 px-4 py-3 text-sm font-semibold text-emerald-800 dark:text-emerald-300 shadow-sm hover:border-emerald-300 dark:hover:border-emerald-700 transition-colors"
              >
                QR operations queue
                <FaArrowRight size={14} />
              </Link>
              <Link
                to="/admin/pay-in-packages"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 px-4 py-3 text-sm font-semibold text-slate-700 dark:text-slate-300 shadow-sm hover:border-indigo-200 transition-colors"
              >
                Pay-in packages
                <FaArrowRight size={14} className="text-slate-400 dark:text-slate-500" />
              </Link>
            </div>
          </div>
        </header>

        {unlinkedQrCount > 0 ? (
          <div className="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-900 dark:text-amber-300 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <span>
              <strong>{unlinkedQrCount}</strong> QR account{unlinkedQrCount === 1 ? '' : 's'} not linked to any pay-in package.
              Retailers cannot use them on Load Money until linked.
            </span>
            <Link
              to="/admin/pay-in-packages"
              className="inline-flex items-center gap-2 shrink-0 rounded-lg bg-amber-600 px-3 py-2 text-xs font-semibold text-white hover:bg-amber-700"
            >
              Link in pay-in packages
              <FaArrowRight size={12} />
            </Link>
          </div>
        ) : null}

        <section className="rounded-2xl border border-slate-200/90 dark:border-slate-700/90 bg-white dark:bg-slate-900 shadow-sm overflow-hidden">
          <div className="flex flex-col gap-4 border-b border-slate-100 dark:border-slate-800 bg-slate-50/80 dark:bg-slate-800/50 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <div>
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Your QR accounts</h2>
              <p className="text-sm text-slate-600 dark:text-slate-400 mt-0.5">{total} account{total === 1 ? '' : 's'} configured</p>
            </div>
            <Button onClick={openCreate} variant="primary" size="md" icon={FaPlus}>
              Add QR account
            </Button>
          </div>

          <div className="px-5 py-4 sm:px-6 flex flex-col sm:flex-row gap-3 border-b border-slate-100 dark:border-slate-800">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search name, UPI, account…"
              className="flex-1"
            />
            <Button onClick={() => { setPage(1); load(); }} variant="outline">
              Search
            </Button>
          </div>

          {loadError ? (
            <div className="mx-6 my-6 rounded-lg border border-red-200 dark:border-red-800 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-sm text-red-800 dark:text-red-300">
              {loadError}
            </div>
          ) : null}

          {loading ? (
            <div className="py-16">
              <LoadingSpinner text="Loading QR accounts…" />
            </div>
          ) : rows.length === 0 ? (
            <div className="px-6 py-16 text-center">
              <FaQrcode className="mx-auto text-slate-300 mb-3" size={40} />
              <p className="text-slate-600 dark:text-slate-400 font-medium">No QR accounts yet</p>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-1 max-w-md mx-auto">
                Create a QR collection account, then link it to a pay-in package so retailers can select it on Load Money.
              </p>
              <Button onClick={openCreate} variant="primary" className="mt-5" icon={FaPlus}>
                Add first QR account
              </Button>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[800px] text-sm">
                <thead>
                  <tr className="border-b bg-gray-50 dark:bg-slate-800/50 text-left text-xs uppercase text-gray-600 dark:text-slate-400">
                    <th className="px-5 py-3">QR</th>
                    <th className="px-3 py-3">Name</th>
                    <th className="px-3 py-3">UPI</th>
                    <th className="px-3 py-3">24h limit</th>
                    <th className="px-3 py-3">Used today</th>
                    <th className="px-3 py-3">Status</th>
                    <th className="px-3 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-b hover:bg-gray-50 dark:hover:bg-slate-800">
                      <td className="px-5 py-3">
                        {row.qr_image_url ? (
                          <img src={normalizeAssetUrl(row.qr_image_url)} alt="" className="h-12 w-12 rounded border object-contain bg-white dark:bg-slate-900" />
                        ) : (
                          <span className="inline-flex h-12 w-12 items-center justify-center rounded border bg-slate-50 dark:bg-slate-800/50 text-slate-400 dark:text-slate-500">
                            <FaQrcode />
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-3 font-medium text-gray-900 dark:text-slate-100">{row.display_name}</td>
                      <td className="px-3 py-3 font-mono text-xs">{row.upi_vpa || '—'}</td>
                      <td className="px-3 py-3">
                        {row.daily_limit_24h != null ? formatCurrency(parseFloat(row.daily_limit_24h)) : '—'}
                      </td>
                      <td className="px-3 py-3">{formatCurrency(parseFloat(row.daily_used || 0))}</td>
                      <td className="px-3 py-3 capitalize">{row.status}</td>
                      <td className="px-3 py-3">
                        <div className="flex justify-end gap-2">
                          {row.qr_image_url ? (
                            <button
                              type="button"
                              onClick={() => handleDownloadQrImage(row)}
                              className="text-emerald-600 dark:text-emerald-400 hover:text-emerald-800 dark:hover:text-emerald-200"
                              title="Download QR"
                            >
                              <FaDownload />
                            </button>
                          ) : null}
                          <button type="button" onClick={() => openEdit(row)} className="text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-200" title="Edit">
                            <FaPenToSquare />
                          </button>
                          <button type="button" onClick={() => handleToggle(row.id)} className="text-gray-600 dark:text-slate-400 hover:text-gray-900 dark:hover:text-slate-100" title="Toggle status">
                            {row.status === 'active' ? <FaToggleOn size={20} /> : <FaToggleOff size={20} />}
                          </button>
                          <button type="button" onClick={() => handleDelete(row.id)} className="text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200" title="Delete">
                            <FaTrash />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex justify-center gap-2 py-4 border-t border-slate-100 dark:border-slate-800">
              <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)} variant="outline" size="sm">
                Prev
              </Button>
              <span className="text-sm text-gray-600 dark:text-slate-400 self-center">
                Page {page} / {totalPages}
              </span>
              <Button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} variant="outline" size="sm">
                Next
              </Button>
            </div>
          )}
        </section>
      </div>

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <Card className="w-full max-w-lg max-h-[90vh] overflow-y-auto" padding="lg">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-bold">{editing ? 'Edit QR account' : 'New QR account'}</h2>
              <button type="button" onClick={() => setModalOpen(false)} className="text-gray-400 dark:text-slate-500 hover:text-gray-600 dark:hover:text-slate-400">
                <FaXmark size={22} />
              </button>
            </div>
            <form onSubmit={handleSave} className="space-y-4">
              <Input label="Display name *" value={form.display_name} onChange={(e) => setForm({ ...form, display_name: e.target.value })} required />
              <Input label="Account display name" value={form.account_display_name} onChange={(e) => setForm({ ...form, account_display_name: e.target.value })} />
              <Input label="UPI VPA" value={form.upi_vpa} onChange={(e) => setForm({ ...form, upi_vpa: e.target.value })} placeholder="merchant@upi" />
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-1">QR image {editing ? '(optional)' : '*'}</label>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    setQrImage(f || null);
                    setPreview(f ? URL.createObjectURL(f) : preview);
                  }}
                  className="text-sm w-full"
                />
                {preview ? <img src={preview} alt="QR preview" className="mt-2 h-32 rounded border" /> : null}
              </div>
              <Input label="Minimum fee % (package floor)" type="number" step="0.0001" min="0" value={form.charge_rate} onChange={(e) => setForm({ ...form, charge_rate: e.target.value })} helperText="Packages cannot set a QR rail fee below this value." />
              <Input label="24h daily limit (INR)" type="number" value={form.daily_limit_24h} onChange={(e) => setForm({ ...form, daily_limit_24h: e.target.value })} />
              <Input label="Max per txn (INR)" type="number" value={form.max_per_txn} onChange={(e) => setForm({ ...form, max_per_txn: e.target.value })} />
              <Input label="Sort order" type="number" value={form.sort_order} onChange={(e) => setForm({ ...form, sort_order: e.target.value })} />
              <div className="flex gap-3 pt-2">
                <Button type="button" variant="outline" fullWidth onClick={() => setModalOpen(false)}>
                  Cancel
                </Button>
                <Button type="submit" variant="primary" fullWidth loading={saving}>
                  Save
                </Button>
              </div>
            </form>
          </Card>
        </div>
      )}
    </div>
  );
};

export default PayInQrAccountsAdmin;
