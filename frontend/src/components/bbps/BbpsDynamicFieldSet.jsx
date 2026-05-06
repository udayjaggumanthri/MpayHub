import React from 'react';
import Input from '../common/Input';

/**
 * Renders biller input fields from GET /bbps/billers/:id/schema/ input_schema (MDM-driven).
 */
const BbpsDynamicFieldSet = ({ fields, values, onChange }) => {
  if (!Array.isArray(fields) || fields.length === 0) return null;

  return (
    <div className="grid md:grid-cols-2 gap-4">
      {fields.map((f) => {
        const name = f.param_name;
        const val = values[name] ?? '';
        const label = `${name}${f.is_optional ? '' : ' *'}`;
        const help = f.help_text ? (
          <p className="text-xs text-gray-500 mt-1" key={`${name}-help`}>
            {f.help_text}
          </p>
        ) : null;

        if (f.input_kind === 'select' && Array.isArray(f.choices) && f.choices.length > 0) {
          return (
            <div key={name} className="md:col-span-1">
              <label className="block text-sm font-medium text-gray-700 mb-2">{label}</label>
              <select
                className="w-full px-4 py-3 border border-gray-300 rounded-lg"
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
              {help}
            </div>
          );
        }

        const inputType =
          f.input_kind === 'numeric' ? 'tel' : f.input_kind === 'date' ? 'date' : f.canonical_key === 'mobile' ? 'tel' : 'text';

        return (
          <div key={name}>
            <Input
              label={label}
              type={inputType}
              value={val}
              onChange={(e) => {
                const raw = e.target.value;
                let next = raw;
                if (f.canonical_key === 'mobile' || f.input_kind === 'numeric') {
                  next = raw.replace(/\D/g, '');
                  if (f.canonical_key === 'mobile') next = next.slice(0, 10);
                }
                onChange(name, next);
              }}
              placeholder={name}
              required={!f.is_optional}
            />
            {help}
          </div>
        );
      })}
    </div>
  );
};

export default BbpsDynamicFieldSet;
