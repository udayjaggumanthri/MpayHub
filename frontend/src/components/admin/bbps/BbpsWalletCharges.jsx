import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FaMagnifyingGlass, FaXmark } from 'react-icons/fa6';
import { billAvenueAdminAPI } from '../../../services/api';
import { formatCurrency } from '../../../utils/formatters';

const fieldClass =
  'h-10 w-full rounded-lg border border-slate-300 bg-white px-2.5 text-sm text-slate-900 outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400 dark:border-slate-600 dark:bg-slate-950 dark:text-slate-100 dark:focus:ring-blue-900/40 dark:disabled:bg-slate-800 dark:disabled:text-slate-500';

const moneyInput = (value) => {
  if (value === '' || value == null) return '';
  const amount = Number(value);
  if (!Number.isFinite(amount)) return '';
  return amount.toFixed(2);
};

const emptyDraft = (row) => {
  const custom = !!row?.has_override;
  return {
    useDefault: !custom,
    mode: custom ? (row.mode || 'FLAT') : (row?.effective_mode || row?.mode || 'FLAT'),
    flat: moneyInput(custom ? row?.flat : (row?.effective_flat ?? row?.flat)),
    percent: moneyInput(custom ? row?.percent : (row?.effective_percent ?? row?.percent)),
  };
};

const previewOnHundred = (mode, flat, percent) => {
  if (String(mode || 'FLAT').toUpperCase() === 'PERCENT') {
    return (100 * (Number(percent) || 0)) / 100;
  }
  return Number(flat) || 0;
};

const rowIsDirty = (row, draft) => {
  if (!row || !draft) return false;
  if (Boolean(draft.useDefault) === Boolean(!row.has_override)) {
    if (draft.useDefault) return false;
  } else {
    return true;
  }
  return (
    String(draft.mode || '').toUpperCase() !== String(row.mode || '').toUpperCase()
    || Number(draft.flat) !== Number(row.flat)
    || Number(draft.percent) !== Number(row.percent)
  );
};

const BbpsWalletCharges = () => {
  const [catalog, setCatalog] = useState(null);
  const [defaultDraft, setDefaultDraft] = useState({ mode: 'FLAT', flat: '0', percent: '0' });
  const [drafts, setDrafts] = useState({});
  const [msg, setMsg] = useState({ type: 'info', text: '' });
  const [savingKey, setSavingKey] = useState('');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all');

  const applyCatalog = useCallback((data) => {
    const next = data || { default: null, categories: [] };
    setCatalog(next);
    const def = next.default || {};
    setDefaultDraft({
      mode: def.mode || 'FLAT',
      flat: moneyInput(def.flat ?? '0'),
      percent: moneyInput(def.percent ?? '0'),
    });
    const mapped = {};
    (next.categories || []).forEach((row) => {
      mapped[row.category_code] = emptyDraft(row);
    });
    setDrafts(mapped);
  }, []);

  const load = useCallback(async () => {
    const res = await billAvenueAdminAPI.getWalletCharges();
    if (!res.success) {
      setMsg({ type: 'error', text: res.message || 'Could not load wallet service charges' });
      return;
    }
    applyCatalog(res.data);
  }, [applyCatalog]);

  useEffect(() => {
    load();
  }, [load]);

  const amountReady = (draft) => String(draft?.flat ?? '').trim() !== '' && String(draft?.percent ?? '').trim() !== '';

  const saveDefault = async () => {
    if (!amountReady(defaultDraft)) {
      setMsg({ type: 'error', text: 'Enter the flat amount and the percent. Use 0 if that part of the charge should be zero.' });
      return;
    }
    setSavingKey('default');
    setMsg({ type: 'info', text: '' });
    const res = await billAvenueAdminAPI.saveWalletChargeDefault(defaultDraft);
    setSavingKey('');
    if (!res.success) {
      setMsg({ type: 'error', text: res.message || 'Could not save the default charge' });
      return;
    }
    applyCatalog(res.data);
    setMsg({ type: 'success', text: 'Default charge saved. Categories left on Default use this rate.' });
  };

  const saveCategory = async (code) => {
    const draft = drafts[code];
    if (!draft) return;
    if (!amountReady(draft)) {
      setMsg({ type: 'error', text: 'Enter the flat amount and the percent. Use 0 if that part of the charge should be zero.' });
      return;
    }
    setSavingKey(code);
    setMsg({ type: 'info', text: '' });
    const res = await billAvenueAdminAPI.saveWalletChargeCategory({
      category_code: code,
      mode: draft.mode,
      flat: draft.flat,
      percent: draft.percent,
      is_active: !draft.useDefault,
    });
    setSavingKey('');
    if (!res.success) {
      setMsg({ type: 'error', text: res.message || 'Could not save this category' });
      return;
    }
    const saved = res.data?.category;
    if (saved?.category_code) {
      setCatalog((prev) => ({
        ...(prev || {}),
        categories: (prev?.categories || []).map((row) => (
          row.category_code === saved.category_code ? saved : row
        )),
      }));
      setDrafts((prev) => ({ ...prev, [saved.category_code]: emptyDraft(saved) }));
    } else {
      await load();
    }
    setMsg({ type: 'success', text: 'Category charge saved. New payments use it. Past payments stay unchanged.' });
  };

  const patchDraft = (code, patch) => {
    setDrafts((prev) => ({ ...prev, [code]: { ...prev[code], ...patch } }));
  };

  const categories = catalog?.categories || [];
  const customCount = categories.filter((row) => row.has_override).length;
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return categories.filter((row) => {
      if (filter === 'custom' && !row.has_override) return false;
      if (filter === 'default' && row.has_override) return false;
      if (!q) return true;
      return (
        String(row.display_name || '').toLowerCase().includes(q)
        || String(row.category_code || '').toLowerCase().includes(q)
      );
    });
  }, [categories, filter, query]);

  const defaultDirty = catalog?.default
    && (
      String(defaultDraft.mode).toUpperCase() !== String(catalog.default.mode || 'FLAT').toUpperCase()
      || Number(defaultDraft.flat) !== Number(catalog.default.flat)
      || Number(defaultDraft.percent) !== Number(catalog.default.percent)
    );
  const defaultPreview = previewOnHundred(defaultDraft.mode, defaultDraft.flat, defaultDraft.percent);
  const liveLabel = catalog?.default?.config_mode
    ? `Live ${String(catalog.default.config_mode).toUpperCase()}`
    : 'Live default';

  const bannerClass = msg.type === 'error'
    ? 'bg-red-50 text-red-800 ring-red-200 dark:bg-red-950/40 dark:text-red-200 dark:ring-red-900'
    : msg.type === 'success'
      ? 'bg-emerald-50 text-emerald-800 ring-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-200 dark:ring-emerald-900'
      : '';

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h2 className="text-xl font-semibold text-slate-900 dark:text-slate-100">Wallet service charge</h2>
        <p className="mt-1 max-w-3xl text-sm text-slate-600 dark:text-slate-400">
          Company commission on a successful bill payment. Set one default, then give a category its own rate only when it should differ.
        </p>
      </div>

      {msg.text ? (
        <div className={`rounded-lg px-4 py-3 text-sm ring-1 ${bannerClass}`} role="status">{msg.text}</div>
      ) : null}

      <section className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm dark:border-slate-700 dark:bg-slate-900 sm:p-4">
        <h3 className="text-sm font-semibold text-slate-900 dark:text-slate-100">Default charge</h3>
        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
          {liveLabel}. A ₹100 bill charges {formatCurrency(defaultPreview)} when a category is left on Default.
        </p>
        <div className="mt-3 grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
          <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
            Type
            <select
              className={`${fieldClass} mt-1`}
              value={String(defaultDraft.mode).toUpperCase() === 'PERCENT' ? 'PERCENT' : 'FLAT'}
              onChange={(e) => setDefaultDraft((prev) => ({ ...prev, mode: e.target.value }))}
            >
              <option value="FLAT">Flat (₹)</option>
              <option value="PERCENT">Percent (%)</option>
            </select>
          </label>
          <AmountField
            labeled
            mode={defaultDraft.mode}
            flat={defaultDraft.flat}
            percent={defaultDraft.percent}
            onChange={(patch) => setDefaultDraft((prev) => ({ ...prev, ...patch }))}
          />
          <button
            type="button"
            onClick={saveDefault}
            disabled={savingKey === 'default' || !defaultDirty}
            className="h-10 w-full rounded-lg bg-blue-700 px-4 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
          >
            {savingKey === 'default' ? 'Saving…' : 'Save default'}
          </button>
        </div>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-900">
        <div className="space-y-3 border-b border-slate-200 p-3 dark:border-slate-700 sm:p-4">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <div className="relative min-w-0 flex-1">
              <FaMagnifyingGlass className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={13} />
              <input
                type="search"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search category, for example electricity or mobile"
                aria-label="Search categories"
                className={`${fieldClass} pl-9 pr-9`}
              />
              {query ? (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-slate-800 dark:hover:text-slate-200"
                  aria-label="Clear search"
                >
                  <FaXmark size={12} />
                </button>
              ) : null}
            </div>
            <div className="flex h-10 shrink-0 items-center gap-1 rounded-lg bg-slate-100 p-1 dark:bg-slate-800" role="tablist" aria-label="Filter categories">
              {[
                ['all', `All ${categories.length}`],
                ['custom', `Custom ${customCount}`],
                ['default', `Default ${Math.max(categories.length - customCount, 0)}`],
              ].map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  role="tab"
                  aria-selected={filter === id}
                  onClick={() => setFilter(id)}
                  className={`rounded-md px-3 py-1.5 text-xs font-semibold sm:text-sm ${
                    filter === id
                      ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-950 dark:text-slate-100'
                      : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <p className="text-xs text-slate-500 dark:text-slate-400">
            Showing {filtered.length} of {categories.length}. The list below scrolls. ₹100 is only a preview; the quote uses the real bill amount.
          </p>
        </div>

        <div className="max-h-[min(68vh,640px)] min-h-[240px] overflow-auto">
          {catalog == null ? (
            <p className="px-4 py-16 text-center text-sm text-slate-500">Loading categories…</p>
          ) : filtered.length === 0 ? (
            <p className="px-4 py-16 text-center text-sm text-slate-500 dark:text-slate-400">
              No category matches this search.
            </p>
          ) : (
            <>
              <div className="hidden md:block">
                <table className="w-full min-w-[820px] table-fixed border-separate border-spacing-0 text-sm">
                  <colgroup>
                    <col className="w-[26%]" />
                    <col className="w-[15%]" />
                    <col className="w-[15%]" />
                    <col className="w-[16%]" />
                    <col className="w-[14%]" />
                    <col className="w-[14%]" />
                  </colgroup>
                  <thead>
                    <tr className="text-left text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      <th className="sticky left-0 top-0 z-30 h-11 border-b border-slate-200 bg-slate-50 px-3 text-left align-middle dark:border-slate-700 dark:bg-slate-800">Category</th>
                      <th className="sticky top-0 z-20 h-11 border-b border-slate-200 bg-slate-50 px-3 text-left align-middle dark:border-slate-700 dark:bg-slate-800">Applies</th>
                      <th className="sticky top-0 z-20 h-11 border-b border-slate-200 bg-slate-50 px-3 text-left align-middle dark:border-slate-700 dark:bg-slate-800">Type</th>
                      <th className="sticky top-0 z-20 h-11 border-b border-slate-200 bg-slate-50 px-3 text-left align-middle dark:border-slate-700 dark:bg-slate-800">Amount</th>
                      <th className="sticky top-0 z-20 h-11 border-b border-slate-200 bg-slate-50 px-3 text-right align-middle dark:border-slate-700 dark:bg-slate-800">On ₹100</th>
                      <th className="sticky top-0 z-20 h-11 border-b border-slate-200 bg-slate-50 px-3 text-right align-middle dark:border-slate-700 dark:bg-slate-800">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((row) => {
                      const draft = drafts[row.category_code] || emptyDraft(row);
                      const dirty = rowIsDirty(row, draft);
                      const custom = !draft.useDefault;
                      const preview = custom
                        ? previewOnHundred(draft.mode, draft.flat, draft.percent)
                        : Number(row.preview_charge || 0);
                      const cell = 'border-b border-slate-100 px-3 py-2 align-middle dark:border-slate-800';
                      return (
                        <tr key={row.category_code} className="text-slate-800 dark:text-slate-100">
                          <td className={`sticky left-0 z-10 bg-white dark:bg-slate-900 ${cell}`}>
                            <p className="truncate font-semibold leading-5">{row.display_name}</p>
                            <p className="truncate text-xs leading-4 text-slate-500 dark:text-slate-400">{row.category_code}</p>
                          </td>
                          <td className={cell}>
                            <AppliesSelect
                              useDefault={draft.useDefault}
                              onChange={(useDefault) => patchDraft(row.category_code, { useDefault })}
                            />
                          </td>
                          <td className={cell}>
                            <TypeSelect
                              mode={draft.mode}
                              disabled={!custom}
                              onChange={(mode) => patchDraft(row.category_code, { mode })}
                            />
                          </td>
                          <td className={cell}>
                            <AmountField
                              mode={draft.mode}
                              flat={draft.flat}
                              percent={draft.percent}
                              disabled={!custom}
                              onChange={(patch) => patchDraft(row.category_code, patch)}
                            />
                          </td>
                          <td className={`${cell} text-right font-medium tabular-nums`}>
                            {formatCurrency(preview)}
                          </td>
                          <td className={cell}>
                            <div className="flex justify-end">
                              <SaveButton
                                dirty={dirty}
                                saving={savingKey === row.category_code}
                                onClick={() => saveCategory(row.category_code)}
                              />
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <ul className="divide-y divide-slate-100 dark:divide-slate-800 md:hidden">
                {filtered.map((row) => {
                  const draft = drafts[row.category_code] || emptyDraft(row);
                  const dirty = rowIsDirty(row, draft);
                  const custom = !draft.useDefault;
                  const preview = custom
                    ? previewOnHundred(draft.mode, draft.flat, draft.percent)
                    : Number(row.preview_charge || 0);
                  return (
                    <li key={row.category_code} className="space-y-3 px-3 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate font-semibold text-slate-900 dark:text-slate-100">{row.display_name}</p>
                          <p className="truncate text-xs text-slate-500 dark:text-slate-400">{row.category_code}</p>
                        </div>
                        <p className="shrink-0 text-sm font-semibold text-slate-800 dark:text-slate-100">
                          {formatCurrency(preview)}
                          <span className="block text-right text-[11px] font-normal text-slate-500">on ₹100</span>
                        </p>
                      </div>
                      <div className="grid grid-cols-1 gap-2 min-[420px]:grid-cols-3">
                        <AppliesSelect
                          useDefault={draft.useDefault}
                          onChange={(useDefault) => patchDraft(row.category_code, { useDefault })}
                        />
                        <TypeSelect
                          mode={draft.mode}
                          disabled={!custom}
                          onChange={(mode) => patchDraft(row.category_code, { mode })}
                        />
                        <AmountField
                          mode={draft.mode}
                          flat={draft.flat}
                          percent={draft.percent}
                          disabled={!custom}
                          onChange={(patch) => patchDraft(row.category_code, patch)}
                        />
                      </div>
                      <SaveButton
                        dirty={dirty}
                        saving={savingKey === row.category_code}
                        wide
                        onClick={() => saveCategory(row.category_code)}
                      />
                    </li>
                  );
                })}
              </ul>
            </>
          )}
        </div>
      </section>
    </div>
  );
};

function AppliesSelect({ useDefault, onChange }) {
  return (
    <select
      aria-label="Charge source"
      className={fieldClass}
      value={useDefault ? 'default' : 'custom'}
      onChange={(e) => onChange(e.target.value === 'default')}
    >
      <option value="default">Default</option>
      <option value="custom">Custom</option>
    </select>
  );
}

function TypeSelect({ mode, disabled, onChange }) {
  return (
    <select
      aria-label="Charge type"
      className={fieldClass}
      disabled={disabled}
      value={String(mode || 'FLAT').toUpperCase() === 'PERCENT' ? 'PERCENT' : 'FLAT'}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="FLAT">Flat (₹)</option>
      <option value="PERCENT">Percent (%)</option>
    </select>
  );
}

function AmountField({ mode, flat, percent, disabled = false, labeled = false, onChange }) {
  const percentMode = String(mode || 'FLAT').toUpperCase() === 'PERCENT';
  const input = (
    <div className="relative">
      <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-xs font-medium text-slate-400">
        {percentMode ? '%' : '₹'}
      </span>
      <input
        type="number"
        inputMode="decimal"
        min={0}
        max={percentMode ? 100 : undefined}
        step="0.01"
        disabled={disabled}
        aria-label={percentMode ? 'Percent of bill' : 'Flat amount in rupees'}
        className={`${fieldClass} pl-7 tabular-nums`}
        value={percentMode ? (percent ?? '') : (flat ?? '')}
        onChange={(e) => onChange(percentMode ? { percent: e.target.value } : { flat: e.target.value })}
      />
    </div>
  );
  if (!labeled) return input;
  return (
    <label className="block text-xs font-medium text-slate-500 dark:text-slate-400">
      Amount
      <span className="mt-1 block">{input}</span>
    </label>
  );
}

function SaveButton({ dirty, saving, onClick, wide = false }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={!dirty || saving}
      className={`h-10 rounded-lg px-3 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-40 ${
        wide ? 'w-full' : 'min-w-[4.5rem]'
      } ${
        dirty
          ? 'bg-blue-700 text-white hover:bg-blue-800'
          : 'border border-slate-200 text-slate-500 dark:border-slate-700 dark:text-slate-400'
      }`}
    >
      {saving ? 'Saving…' : 'Save'}
    </button>
  );
}

export default BbpsWalletCharges;
