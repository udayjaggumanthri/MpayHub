import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { FiChevronDown, FiAlertCircle } from 'react-icons/fi';

const defaultGetLabel = (opt) => (typeof opt === 'object' ? opt.label ?? opt.name ?? String(opt.value ?? '') : String(opt));
const defaultGetValue = (opt) => (typeof opt === 'object' ? opt.value ?? opt.id ?? opt : opt);

/**
 * Searchable dropdown for long option lists. Use SelectField wrapper for auto threshold.
 */
const SearchableSelect = ({
  options = [],
  value,
  onChange,
  getOptionLabel = defaultGetLabel,
  getOptionValue = defaultGetValue,
  placeholder = 'Select…',
  disabled = false,
  loading = false,
  searchable = true,
  label,
  required = false,
  error,
  helperText,
  className = '',
  emptyMessage = 'No options found',
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlightIndex, setHighlightIndex] = useState(0);
  const wrapRef = useRef(null);
  const inputRef = useRef(null);
  const listRef = useRef(null);

  const normalized = useMemo(
    () =>
      (options || []).map((opt) => ({
        opt,
        label: String(getOptionLabel(opt) ?? ''),
        value: String(getOptionValue(opt) ?? ''),
      })),
    [options, getOptionLabel, getOptionValue]
  );

  const filtered = useMemo(() => {
    if (!searchable || !query.trim()) return normalized;
    const q = query.trim().toLowerCase();
    return normalized.filter(
      (item) => item.label.toLowerCase().includes(q) || item.value.toLowerCase().includes(q)
    );
  }, [normalized, query, searchable]);

  const selected = normalized.find((item) => item.value === String(value ?? ''));

  const close = useCallback(() => {
    setOpen(false);
    setQuery('');
    setHighlightIndex(0);
  }, []);

  useEffect(() => {
    const onDocClick = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) close();
    };
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, [close]);

  useEffect(() => {
    if (open && searchable) inputRef.current?.focus();
  }, [open, searchable]);

  useEffect(() => {
    if (!open) return;
    const el = listRef.current?.children[highlightIndex];
    el?.scrollIntoView({ block: 'nearest' });
  }, [highlightIndex, open]);

  const pick = (item) => {
    onChange?.(item.value, item.opt);
    close();
  };

  const onKeyDown = (e) => {
    if (!open) {
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ArrowDown') {
        e.preventDefault();
        setOpen(true);
      }
      return;
    }
    if (e.key === 'Escape') {
      e.preventDefault();
      close();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setHighlightIndex((i) => Math.min(i + 1, Math.max(0, filtered.length - 1)));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setHighlightIndex((i) => Math.max(i - 1, 0));
      return;
    }
    if (e.key === 'Enter' && filtered[highlightIndex]) {
      e.preventDefault();
      pick(filtered[highlightIndex]);
    }
  };

  const borderClass = error ? 'border-red-400 focus:ring-red-200' : 'border-gray-300 dark:border-slate-600 focus:ring-blue-500 focus:border-blue-500';

  return (
    <div className={`w-full ${className}`} ref={wrapRef}>
      {label ? (
        <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
          {label}
          {required ? <span className="text-red-500 ml-1">*</span> : null}
        </label>
      ) : null}
      <div className="relative">
        <button
          type="button"
          disabled={disabled || loading}
          onClick={() => !disabled && !loading && setOpen((v) => !v)}
          onKeyDown={onKeyDown}
          className={`w-full px-4 py-3 border rounded-lg text-left flex items-center justify-between gap-2 bg-white dark:bg-slate-900 transition-all focus:outline-none focus:ring-2 ${borderClass} disabled:bg-gray-50 dark:disabled:bg-slate-800/50 disabled:text-gray-500 dark:disabled:text-slate-500 disabled:cursor-not-allowed`}
          aria-haspopup="listbox"
          aria-expanded={open}
        >
          <span className={selected ? 'text-gray-900 dark:text-slate-100 truncate' : 'text-gray-500 dark:text-slate-400 truncate'}>
            {loading ? 'Loading…' : selected?.label || placeholder}
          </span>
          <FiChevronDown className={`shrink-0 text-gray-400 dark:text-slate-500 transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
        {error && !open ? (
          <div className="absolute inset-y-0 right-8 flex items-center pointer-events-none">
            <FiAlertCircle className="text-red-500" size={18} />
          </div>
        ) : null}

        {open ? (
          <div className="absolute z-50 mt-1 w-full rounded-lg border border-gray-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-lg">
            {searchable ? (
              <div className="p-2 border-b border-gray-100 dark:border-slate-800">
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    setHighlightIndex(0);
                  }}
                  onKeyDown={onKeyDown}
                  placeholder="Search…"
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-slate-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
            ) : null}
            <ul ref={listRef} role="listbox" className="max-h-60 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <li className="px-4 py-3 text-sm text-gray-500 dark:text-slate-400">{emptyMessage}</li>
              ) : (
                filtered.map((item, idx) => (
                  <li
                    key={`${item.value}-${idx}`}
                    role="option"
                    aria-selected={item.value === String(value ?? '')}
                    onMouseEnter={() => setHighlightIndex(idx)}
                    onClick={() => pick(item)}
                    className={`px-4 py-2.5 text-sm cursor-pointer truncate ${
                      idx === highlightIndex ? 'bg-blue-50 dark:bg-blue-950/40 text-blue-900 dark:text-blue-300' : 'text-gray-900 dark:text-slate-100 hover:bg-gray-50 dark:hover:bg-slate-800'
                    } ${item.value === String(value ?? '') ? 'font-medium' : ''}`}
                  >
                    {item.label}
                  </li>
                ))
              )}
            </ul>
          </div>
        ) : null}
      </div>
      {error ? (
        <p className="mt-1.5 text-sm text-red-600 dark:text-red-400 flex items-center">
          <FiAlertCircle className="mr-1" size={14} />
          {error}
        </p>
      ) : null}
      {helperText && !error ? <p className="mt-1.5 text-sm text-gray-500 dark:text-slate-400">{helperText}</p> : null}
    </div>
  );
};

export default SearchableSelect;
