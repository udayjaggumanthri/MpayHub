import React, { useState, useEffect, useRef } from 'react';
import { contactsAPI } from '../../services/api';
import { mapContactRow, contactRoleLabel } from '../../utils/contactsHelpers';
import Input from '../common/Input';
import { FaUser, FaSpinner } from 'react-icons/fa6';

const DEBOUNCE_MS = 280;
const MIN_QUERY = 2;

/**
 * Live contact lookup: debounced partial match on name or phone; pick from dropdown.
 */
const ContactSearchTypeahead = ({
  label = 'Contact name or phone number',
  placeholder = 'Start typing name or phone…',
  value,
  onChange,
  onPick,
  onClearSelection,
  icon: Icon = FaUser,
  size = 'lg',
  helperText,
  /** e.g. Search button — aligned with the input row (not helper text below). */
  trailingAction = null,
  /** Fires when the user presses Enter in the field (same as clicking Search). */
  onSubmitSearch = null,
  /** When true, Enter does not run `onSubmitSearch` (mirror Search button disabled). */
  submitSearchDisabled = false,
  className = '',
}) => {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const runIdRef = useRef(0);
  const onPickRef = useRef(onPick);
  const onChangeRef = useRef(onChange);
  const onSubmitSearchRef = useRef(onSubmitSearch);

  useEffect(() => {
    onPickRef.current = onPick;
    onChangeRef.current = onChange;
    onSubmitSearchRef.current = onSubmitSearch;
  });

  useEffect(() => {
    const q = (value || '').trim();
    if (q.length < MIN_QUERY) {
      runIdRef.current += 1;
      setSuggestions([]);
      setLoading(false);
      setOpen(false);
      return;
    }

    setLoading(true);
    const runId = ++runIdRef.current;
    const timer = setTimeout(async () => {
      try {
        const result = await contactsAPI.suggestContacts(q);
        if (runId !== runIdRef.current) return;

        const rows =
          result.success && Array.isArray(result.data?.contacts) ? result.data.contacts : [];
        setSuggestions(rows);
        setOpen(true);

        const digits = q.replace(/\D/g, '');
        if (rows.length === 1 && digits.length === 10 && rows[0].phone === digits) {
          const mapped = mapContactRow(rows[0]);
          if (mapped) {
            onChangeRef.current(`${mapped.name} · ${mapped.phone}`);
            onPickRef.current?.(mapped);
          }
          setOpen(false);
        }
      } catch {
        if (runId === runIdRef.current) {
          setSuggestions([]);
        }
      } finally {
        if (runId === runIdRef.current) {
          setLoading(false);
        }
      }
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
  }, [value]);

  useEffect(() => {
    const onDoc = (e) => {
      if (!wrapRef.current?.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const handleInputChange = (e) => {
    const next = e.target.value;
    onChange(next);
    onClearSelection?.();
  };

  const handleSelectRow = (row) => {
    const mapped = mapContactRow(row);
    if (mapped) {
      onChange(`${mapped.name} · ${mapped.phone}`);
      onPick(mapped);
    }
    setOpen(false);
    setSuggestions([]);
  };

  const handleInputKeyDown = (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    if (!onSubmitSearchRef.current || submitSearchDisabled) return;
    onSubmitSearchRef.current();
  };

  const qLen = (value || '').trim().length;
  const showList =
    open && (suggestions.length > 0 || (loading && qLen >= MIN_QUERY));

  return (
    <div ref={wrapRef} className={`relative ${className}`.trim()}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:gap-4">
        <div className="relative min-w-0 flex-1">
          <Input
            label={label}
            type="text"
            enterKeyHint="search"
            icon={loading ? FaSpinner : Icon}
            value={value}
            onChange={handleInputChange}
            onKeyDown={handleInputKeyDown}
            onFocus={() => {
              if (suggestions.length > 0) setOpen(true);
            }}
            placeholder={placeholder}
            size={size}
            className={loading ? '[&_svg]:animate-spin' : ''}
            autoComplete="off"
          />
          {showList && (
            <ul
              className="absolute left-0 right-0 top-full z-30 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
              role="listbox"
            >
              {loading && suggestions.length === 0 ? (
                <li className="px-4 py-3 text-sm text-gray-500">Searching…</li>
              ) : null}
              {!loading && suggestions.length === 0 && qLen >= MIN_QUERY ? (
                <li className="px-4 py-3 text-sm text-gray-500">No matching contacts</li>
              ) : null}
              {suggestions.map((row) => {
                const role = contactRoleLabel(row.contact_role);
                return (
                  <li key={row.id} role="option" aria-selected="false">
                    <button
                      type="button"
                      className="flex w-full flex-col items-start gap-0.5 px-4 py-2.5 text-left hover:bg-blue-50"
                      onMouseDown={(e) => e.preventDefault()}
                      onClick={() => handleSelectRow(row)}
                    >
                      <span className="font-medium text-gray-900">{row.name}</span>
                      <span className="text-sm text-gray-600 tabular-nums">{row.phone}</span>
                      {row.email ? (
                        <span className="text-xs text-gray-500 truncate max-w-full">{row.email}</span>
                      ) : null}
                      {role ? <span className="text-xs text-blue-600">{role}</span> : null}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
        {trailingAction ? (
          <div className="flex w-full shrink-0 sm:w-auto sm:items-end">{trailingAction}</div>
        ) : null}
      </div>
      {helperText ? <p className="mt-2 text-xs text-gray-500">{helperText}</p> : null}
    </div>
  );
};

export default ContactSearchTypeahead;
