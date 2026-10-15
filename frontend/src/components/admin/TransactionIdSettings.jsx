import React, { useEffect, useState } from 'react';
import { adminAPI } from '../../services/api';
import Button from '../common/Button';
import Card from '../common/Card';

const FIELDS = [
  ['load_money', 'Load money'],
  ['payin', 'Pay in'],
  ['payout', 'Pay out'],
  ['wallet_transfer', 'Wallet transfer'],
  ['bbps', 'BBPS'],
];

const TransactionIdSettings = () => {
  const [form, setForm] = useState({
    load_money: 'PMLM',
    payin: 'PMPI',
    payout: 'PMPO',
    wallet_transfer: 'PMWT',
    bbps: 'PMBBPS',
  });
  const [examples, setExamples] = useState({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  const load = async () => {
    const result = await adminAPI.getTransactionIdSettings();
    const data = result?.data || {};
    if (result?.success === false) {
      setError(result.message || 'Could not load prefixes.');
      return;
    }
    setForm({
      load_money: data.load_money || 'PMLM',
      payin: data.payin || 'PMPI',
      payout: data.payout || 'PMPO',
      wallet_transfer: data.wallet_transfer || 'PMWT',
      bbps: data.bbps || 'PMBBPS',
    });
    setExamples(data.examples || {});
  };

  useEffect(() => {
    load();
  }, []);

  const save = async (event) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    setMessage('');
    const result = await adminAPI.patchTransactionIdSettings(form);
    setSaving(false);
    if (result?.success === false) {
      setError(result.message || 'Could not save prefixes.');
      return;
    }
    const data = result?.data || {};
    setExamples(data.examples || {});
    setMessage('Saved. New transactions use these prefixes. Existing IDs stay the same.');
  };

  return (
    <div className="max-w-3xl space-y-4 p-4 sm:p-6">
      <div>
        <h1 className="text-2xl font-bold text-slate-900 dark:text-slate-100">Transaction IDs</h1>
        <p className="mt-1 text-sm text-slate-500">
          These letters sit at the front of a new transaction ID, followed by the date and five digits. Reports still search the full ID.
        </p>
      </div>
      <Card>
        <form onSubmit={save} className="space-y-4 p-4">
          {FIELDS.map(([key, label]) => (
            <label key={key} className="block">
              <span className="text-sm font-medium text-slate-700 dark:text-slate-300">{label}</span>
              <input
                value={form[key]}
                onChange={(e) => setForm((prev) => ({ ...prev, [key]: e.target.value.toUpperCase() }))}
                maxLength={12}
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm uppercase dark:border-slate-600 dark:bg-slate-900"
              />
              <span className="mt-1 block text-xs text-slate-500">Example: {examples[key] || `${form[key]}YYYYMMDD00000`}</span>
            </label>
          ))}
          {error && <p className="text-sm text-rose-600">{error}</p>}
          {message && <p className="text-sm text-emerald-700">{message}</p>}
          <Button type="submit" variant="primary" loading={saving}>Save prefixes</Button>
        </form>
      </Card>
    </div>
  );
};

export default TransactionIdSettings;
