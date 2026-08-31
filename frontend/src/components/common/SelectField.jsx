import React from 'react';
import SearchableSelect from './SearchableSelect';

const defaultGetLabel = (opt) => (typeof opt === 'object' ? opt.label ?? opt.name ?? String(opt.value ?? '') : String(opt));
const defaultGetValue = (opt) => (typeof opt === 'object' ? opt.value ?? opt.id ?? opt : opt);
const defaultIsDisabled = (opt) => Boolean(typeof opt === 'object' && opt.disabled);

const SEARCH_THRESHOLD = 8;

/**
 * Auto-selects native <select> for short lists (<8 options) or SearchableSelect for longer lists.
 */
const SelectField = ({
  options = [],
  value,
  onChange,
  getOptionLabel = defaultGetLabel,
  getOptionValue = defaultGetValue,
  isOptionDisabled = defaultIsDisabled,
  placeholder = 'Select…',
  disabled = false,
  loading = false,
  searchable,
  label,
  required = false,
  error,
  helperText,
  className = '',
  selectClassName = '',
  includeEmptyOption = true,
  emptyOptionLabel,
}) => {
  const useSearchable = searchable ?? options.length >= SEARCH_THRESHOLD;

  if (!useSearchable) {
    return (
      <div className={`w-full ${className}`}>
        {label ? (
          <label className="block text-sm font-medium text-gray-700 dark:text-slate-300 mb-2">
            {label}
            {required ? <span className="text-red-500 ml-1">*</span> : null}
          </label>
        ) : null}
        <select
          value={value ?? ''}
          onChange={(e) => {
            const val = e.target.value;
            const match = options.find((opt) => String(getOptionValue(opt)) === val);
            onChange?.(val, match);
          }}
          disabled={disabled || loading}
          required={required}
          className={`w-full px-4 py-3 border rounded-lg bg-white dark:bg-slate-900 text-gray-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 dark:disabled:bg-slate-800/50 disabled:text-gray-500 dark:disabled:text-slate-500 disabled:cursor-not-allowed ${
            error ? 'border-red-400' : 'border-gray-300 dark:border-slate-600'
          } ${selectClassName}`}
        >
          {includeEmptyOption ? (
            <option value="">{emptyOptionLabel || placeholder}</option>
          ) : null}
          {options.map((opt, idx) => {
            const val = getOptionValue(opt);
            const lab = getOptionLabel(opt);
            return (
              <option key={`${val}-${idx}`} value={val} disabled={isOptionDisabled(opt)}>
                {lab}
              </option>
            );
          })}
        </select>
        {error ? <p className="mt-1 text-xs text-red-600 dark:text-red-400">{error}</p> : null}
        {helperText && !error ? <p className="mt-1.5 text-sm text-gray-500 dark:text-slate-400">{helperText}</p> : null}
      </div>
    );
  }

  return (
    <SearchableSelect
      options={options}
      value={value}
      onChange={onChange}
      getOptionLabel={getOptionLabel}
      getOptionValue={getOptionValue}
      placeholder={placeholder}
      disabled={disabled}
      loading={loading}
      searchable
      label={label}
      required={required}
      error={error}
      helperText={helperText}
      className={className}
    />
  );
};

export default SelectField;
