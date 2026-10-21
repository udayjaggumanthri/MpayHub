import React, { useCallback, useEffect, useState } from 'react';
import { adminAPI } from '../../services/api';
import { normalizeAssetUrl } from '../../utils/mediaUrl';
import Button from '../common/Button';
import Card from '../common/Card';
import Input from '../common/Input';

const emptyForm = () => ({
  legalName: 'Prajnadhara',
  companyLine: 'Infotech Pvt Ltd',
  address: '',
  phone: '',
  email: '',
  gstNumber: '',
  gstRatePercent: '18',
  declaration: '',
  invoiceNextNumber: '1',
});

const AssetRow = ({ label, preview, onFileChange, onRemove }) => (
  <div>
    <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-slate-300">{label}</label>
    <div className="flex flex-wrap items-center gap-4">
      <div className="flex h-20 w-40 items-center justify-center rounded-lg border border-gray-200 bg-white p-2 dark:border-slate-600">
        {preview ? (
          <img src={preview} alt={`${label} preview`} className="max-h-full max-w-full object-contain" />
        ) : (
          <span className="text-xs text-gray-400">No image</span>
        )}
      </div>
      <div className="space-y-2">
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp,image/gif"
          onChange={onFileChange}
          className="block text-sm text-gray-600 dark:text-slate-300"
        />
        {preview ? (
          <button type="button" onClick={onRemove} className="text-sm font-semibold text-red-600 hover:underline">
            Remove
          </button>
        ) : null}
      </div>
    </div>
  </div>
);

const InvoiceSettingsAdmin = () => {
  const [form, setForm] = useState(emptyForm);
  const [signaturePreview, setSignaturePreview] = useState('');
  const [stampPreview, setStampPreview] = useState('');
  const [signatureFile, setSignatureFile] = useState(null);
  const [stampFile, setStampFile] = useState(null);
  const [removeSignature, setRemoveSignature] = useState(false);
  const [removeStamp, setRemoveStamp] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    const res = await adminAPI.getInvoiceSettings();
    if (!res?.success) {
      setError(res?.message || 'Could not load invoice settings.');
      setLoading(false);
      return;
    }
    const s = res.data?.settings || {};
    setForm({
      legalName: s.legalName || '',
      companyLine: s.companyLine || '',
      address: s.address || '',
      phone: s.phone || '',
      email: s.email || '',
      gstNumber: s.gstNumber || '',
      gstRatePercent: String(s.gstRatePercent ?? '18'),
      declaration: s.declaration || '',
      invoiceNextNumber: String(s.invoiceNextNumber ?? '1'),
    });
    setSignaturePreview(normalizeAssetUrl(s.signatureUrl) || '');
    setStampPreview(normalizeAssetUrl(s.stampUrl) || '');
    setSignatureFile(null);
    setStampFile(null);
    setRemoveSignature(false);
    setRemoveStamp(false);
    setLoading(false);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const onChange = (key) => (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSave = async (e) => {
    e.preventDefault();
    setSaving(true);
    setMessage('');
    setError('');
    const fd = new FormData();
    Object.entries(form).forEach(([key, value]) => fd.append(key, value ?? ''));
    if (signatureFile) fd.append('signature', signatureFile);
    if (stampFile) fd.append('stamp', stampFile);
    if (removeSignature) fd.append('removeSignature', 'true');
    if (removeStamp) fd.append('removeStamp', 'true');
    const res = await adminAPI.patchInvoiceSettings(fd);
    setSaving(false);
    if (!res?.success) {
      setError(res?.message || 'Could not save invoice settings.');
      return;
    }
    setMessage('Invoice settings saved.');
    const s = res.data?.settings || {};
    setSignaturePreview(normalizeAssetUrl(s.signatureUrl) || '');
    setStampPreview(normalizeAssetUrl(s.stampUrl) || '');
    setSignatureFile(null);
    setStampFile(null);
    setRemoveSignature(false);
    setRemoveStamp(false);
  };

  if (loading) {
    return <p className="p-6 text-sm text-gray-500">Loading invoice settings…</p>;
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 sm:p-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900 dark:text-slate-100">Tax invoice settings</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-slate-400">
          Company branding, GST rate, stamp and signature used when Admin generates pay-in tax invoices.
        </p>
      </div>

      <Card>
        <form className="space-y-4 p-4 sm:p-6" onSubmit={handleSave}>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Legal name" value={form.legalName} onChange={onChange('legalName')} required />
            <Input label="Company line" value={form.companyLine} onChange={onChange('companyLine')} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-slate-300">Address</label>
            <textarea
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
              rows={3}
              value={form.address}
              onChange={onChange('address')}
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Input label="Phone" value={form.phone} onChange={onChange('phone')} />
            <Input label="Email" type="email" value={form.email} onChange={onChange('email')} />
            <Input label="GST number" value={form.gstNumber} onChange={onChange('gstNumber')} />
            <Input label="GST rate %" value={form.gstRatePercent} onChange={onChange('gstRatePercent')} />
            <Input label="Next invoice number" value={form.invoiceNextNumber} onChange={onChange('invoiceNextNumber')} />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700 dark:text-slate-300">Declaration</label>
            <textarea
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-800"
              rows={3}
              value={form.declaration}
              onChange={onChange('declaration')}
            />
          </div>
          <AssetRow
            label="Authorized signature"
            preview={removeSignature ? '' : (signatureFile ? URL.createObjectURL(signatureFile) : signaturePreview)}
            onFileChange={(e) => {
              setSignatureFile(e.target.files?.[0] || null);
              setRemoveSignature(false);
            }}
            onRemove={() => {
              setSignatureFile(null);
              setRemoveSignature(true);
              setSignaturePreview('');
            }}
          />
          <AssetRow
            label="Company stamp"
            preview={removeStamp ? '' : (stampFile ? URL.createObjectURL(stampFile) : stampPreview)}
            onFileChange={(e) => {
              setStampFile(e.target.files?.[0] || null);
              setRemoveStamp(false);
            }}
            onRemove={() => {
              setStampFile(null);
              setRemoveStamp(true);
              setStampPreview('');
            }}
          />
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {message ? <p className="text-sm text-emerald-700">{message}</p> : null}
          <Button type="submit" loading={saving}>
            Save invoice settings
          </Button>
        </form>
      </Card>
    </div>
  );
};

export default InvoiceSettingsAdmin;
