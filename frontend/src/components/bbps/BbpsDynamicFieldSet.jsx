import React from 'react';
import Input from '../common/Input';

/**
 * Renders biller input fields from GET /bbps/billers/:id/schema/ input_schema (MDM-driven).
 *
 * @param {string} [formGuidance] - Optional server hint (e.g. BillAvenue placeholder param names).
 * @param {Record<string, string>} [fieldErrors] - Per-param validation messages.
 */
const BbpsDynamicFieldSet = ({ fields, values, onChange, formGuidance, fieldErrors }) => {
  if (!Array.isArray(fields) || fields.length === 0) return null;

  const helperLine = (f) =>
    [
      f.is_placeholder_wire_name && f.billavenue_param_key ? `BillAvenue key: ${f.billavenue_param_key}` : null,
      f.constraints_hint || null,
    ]
      .filter(Boolean)
      .join(' · ');

  const helpCallout = (f) =>
    f.help_text ? (
      <div
        className="mt-2 text-xs text-gray-800 bg-slate-50 border-l-4 border-slate-400 pl-2 py-2 pr-2 rounded"
        key={`${f.param_name}-callout`}
      >
        {f.help_text}
      </div>
    ) : null;

  const errors = fieldErrors && typeof fieldErrors === 'object' ? fieldErrors : {};

  return (
    <div className="space-y-4">
      {formGuidance ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2.5 text-sm text-amber-950 leading-snug">
          {formGuidance}
        </div>
      ) : null}

      <div className="grid md:grid-cols-2 gap-4">
        {fields.map((f) => {
          const name = f.param_name;
          const val = values[name] ?? '';
          const labelText = String(f.display_label || f.label || f.param_name || '').trim() || name;
          const label = `${labelText}${f.is_optional ? '' : ' *'}`;
          const hLine = helperLine(f);
          const fieldError = errors[name] || '';

          if (f.input_kind === 'select' && Array.isArray(f.choices) && f.choices.length > 0) {
            return (
              <div key={name} className="md:col-span-1">
                <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
                {hLine ? <p className="text-xs text-gray-600 mb-2">{hLine}</p> : null}
                <select
                  className={`w-full px-4 py-3 border rounded-lg ${
                    fieldError ? 'border-red-400 focus:ring-red-200' : 'border-gray-300'
                  }`}
                  value={val}
                  required={!f.is_optional}
                  onChange={(e) => onChange(name, e.target.value)}
                >
                  <option value="">Select…</option>
                  {f.choices.map((c) => (
                    <option key={`${name}-${c.value}`} value={c.value}>
                      {c.label || c.value}
                    </option>
                  ))}
                </select>
                {fieldError ? <p className="mt-1 text-xs text-red-600">{fieldError}</p> : null}
                {helpCallout(f)}
              </div>
            );
          }

          const inputType =
            f.input_kind === 'numeric'
              ? 'tel'
              : f.input_kind === 'date'
                ? 'date'
                : f.canonical_key === 'mobile'
                  ? 'tel'
                  : 'text';

          return (
            <div key={name}>
              <Input
                label={label}
                helperText={hLine || undefined}
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
