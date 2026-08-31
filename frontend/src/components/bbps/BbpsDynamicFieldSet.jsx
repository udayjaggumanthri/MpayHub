import React from 'react';
import Input from '../common/Input';
import SelectField from '../common/SelectField';

/**
 * Renders biller input fields from GET /bbps/billers/:id/schema/ input_schema (MDM-driven).
 *
 * @param {Record<string, string>} [fieldErrors] - Per-param validation messages.
 */
const BbpsDynamicFieldSet = ({ fields, values, onChange, fieldErrors }) => {
  if (!Array.isArray(fields) || fields.length === 0) return null;

  const helpCallout = (f) =>
    f.help_text ? (
      <div
        className="mt-2 text-xs text-gray-800 dark:text-slate-200 bg-slate-50 dark:bg-slate-800/50 border-l-4 border-slate-400 pl-2 py-2 pr-2 rounded"
        key={`${f.param_name}-callout`}
      >
        {f.help_text}
      </div>
    ) : null;

  const errors = fieldErrors && typeof fieldErrors === 'object' ? fieldErrors : {};

  return (
    <div className="space-y-4">
      <div className="grid md:grid-cols-2 gap-4">
        {fields.map((f) => {
          const name = f.param_name;
          const val = values[name] ?? '';
          const labelText = String(f.display_label || f.label || f.param_name || '').trim() || name;
          const label = `${labelText}${f.is_optional ? '' : ' *'}`;
          const fieldError = errors[name] || '';

          if (f.input_kind === 'select' && Array.isArray(f.choices) && f.choices.length > 0) {
            return (
              <div key={name} className="md:col-span-1">
                <SelectField
                  label={label}
                  required={!f.is_optional}
                  value={val}
                  onChange={(next) => onChange(name, next)}
                  options={f.choices}
                  getOptionLabel={(c) => c.label || c.value}
                  getOptionValue={(c) => c.value}
                  placeholder="Select…"
                  error={fieldError || undefined}
                />
                {helpCallout(f)}
              </div>
            );
          }

          const inputType =
            f.input_kind === 'numeric'
              ? 'tel'
              : f.input_kind === 'date'
                ? 'date'
                : f.canonical_key === 'mobile' || f.canonical_key === 'card_last4'
                  ? 'tel'
                  : 'text';

          return (
            <div key={name}>
              <Input
                label={label}
                type={inputType}
                value={val}
                error={fieldError || undefined}
                onChange={(e) => {
                  const raw = e.target.value;
                  let next = raw;
                  if (f.canonical_key === 'mobile' || f.input_kind === 'numeric') {
                    next = raw.replace(/\D/g, '');
                    if (f.canonical_key === 'mobile') next = next.slice(0, 10);
                  }
                  if (f.canonical_key === 'card_last4') {
                    next = raw.replace(/\D/g, '').slice(0, 4);
                  }
                  onChange(name, next);
                }}
                placeholder={labelText}
                required={!f.is_optional}
              />
              {helpCallout(f)}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default BbpsDynamicFieldSet;
