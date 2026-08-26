import React, { useState } from 'react';
import { FaCircleCheck, FaChevronDown, FaChevronUp } from 'react-icons/fa6';

const EM_DASH = '—';

const formatDob = (value) => {
  if (!value) return EM_DASH;
  const s = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    const [y, m, d] = s.slice(0, 10).split('-');
    return `${d}-${m}-${y}`;
  }
  return s;
};

const formatVerifiedAt = (value) => {
  if (!value) return EM_DASH;
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const displayValue = (value) => {
  if (value === null || value === undefined || String(value).trim() === '') {
    return EM_DASH;
  }
  return String(value);
};

const PRIMARY_PAN_FIELDS = [
  { key: 'pan', label: 'PAN', mono: true },
  { key: 'name', label: 'Name' },
  { key: 'date_of_birth', label: 'Date of birth', formatter: formatDob },
  { key: 'pan_type', label: 'Type' },
];

const formatSeeding = (value, data) => {
  const desc = data?.aadhaar_seeding_status_desc;
  if (desc) return desc;
  const code = String(value || '').trim().toUpperCase();
  if (code === 'Y') return 'Linked (Y)';
  if (code === 'R') return 'Not linked (R)';
  if (code === 'NA') return 'Not applicable (NA)';
  return displayValue(value);
};

const TECHNICAL_PAN_FIELDS = [
  { key: 'father_name', label: 'Father name' },
  { key: 'pan_status', label: 'PAN status' },
  { key: 'aadhaar_seeding_status', label: 'Aadhaar seeding', formatter: formatSeeding },
  { key: 'name_match_score', label: 'Name match score' },
  { key: 'name_match_result', label: 'Name match result' },
  { key: 'name_provided', label: 'Name submitted' },
  { key: 'last_updated_at', label: 'PAN last updated' },
  { key: 'message', label: 'Message' },
  { key: 'reference_id', label: 'Reference ID', mono: true },
  { key: 'provider_code', label: 'Provider' },
  { key: 'verified_at', label: 'Verified at', formatter: formatVerifiedAt },
];

const PRIMARY_AADHAAR_FIELDS = [
  { key: 'uid_masked', label: 'Aadhaar', mono: true },
  { key: 'name', label: 'Name' },
  { key: 'date_of_birth', label: 'Date of birth', formatter: formatDob },
  { key: 'gender', label: 'Gender' },
  { key: 'address', label: 'Address', fullWidth: true },
  { key: 'district', label: 'District' },
  { key: 'state', label: 'State' },
  { key: 'pincode', label: 'Pincode' },
];

const TECHNICAL_AADHAAR_FIELDS = [
  { key: 'care_of', label: 'Care of' },
  { key: 'year_of_birth', label: 'Year of birth' },
  { key: 'country', label: 'Country' },
  { key: 'message', label: 'Message' },
  { key: 'reference_id', label: 'Reference ID', mono: true },
  { key: 'provider_code', label: 'Provider' },
  { key: 'verified_at', label: 'Verified at', formatter: formatVerifiedAt },
];

const SUMMARY_FIELDS = [
  { key: 'pan', label: 'PAN', mono: true },
  { key: 'name', label: 'Name' },
  { key: 'date_of_birth', label: 'Date of birth', formatter: formatDob },
  { key: 'pan_type', label: 'Type' },
  { key: 'aadhaar_masked', label: 'Aadhaar', mono: true },
];

const SourceHint = ({ source }) => {
  if (source !== 'profile') return null;
  return <span className="ml-1 text-[10px] font-medium uppercase text-amber-700">(from profile)</span>;
};

const DetailGrid = ({ fields, data, variant = 'full', hideEmpty = false }) => (
  <dl className={`grid gap-x-4 gap-y-3 ${variant === 'summary' ? 'grid-cols-1' : 'grid-cols-1 sm:grid-cols-2'}`}>
    {fields.map(({ key, label, formatter, mono, fullWidth }) => {
      const raw = data?.[key];
      if (hideEmpty && (raw === null || raw === undefined || String(raw).trim() === '')) {
        return null;
      }
      const shown = formatter ? formatter(raw, data) : displayValue(raw);
      const sourceKey = key === 'name' ? 'name_source' : key === 'date_of_birth' ? 'date_of_birth_source' : null;
      return (
        <div key={key} className={fullWidth ? 'sm:col-span-2' : ''}>
          <dt className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</dt>
          <dd className={`mt-0.5 text-sm text-slate-900 break-words ${mono ? 'font-mono' : ''}`}>
            {shown}
            {sourceKey ? <SourceHint source={data?.[sourceKey]} /> : null}
          </dd>
        </div>
      );
    })}
  </dl>
);

const DocumentCard = ({ title, verified, children, technicalToggle }) => (
  <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
    <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-slate-100 bg-slate-50/80">
      <div className="flex items-center gap-2 min-w-0">
        <p className="text-sm font-semibold text-slate-900 truncate">{title}</p>
        {verified ? (
          <span className="inline-flex shrink-0 items-center gap-1 rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 ring-1 ring-emerald-200">
            <FaCircleCheck size={10} /> Verified
          </span>
        ) : null}
      </div>
      {technicalToggle}
    </div>
    <div className="p-4">{children}</div>
  </div>
);

const PanelSkeleton = () => (
  <div className="space-y-4 animate-pulse" aria-hidden="true">
    <div className="h-24 rounded-xl bg-slate-100" />
    <div className="h-32 rounded-xl bg-slate-100" />
  </div>
);

/**
 * PAN + Aadhaar verified identity (self profile, admin user detail, onboarding).
 */
const KycVerificationPanel = ({
  verification,
  title = 'Verified KYC details',
  variant = 'full',
  showTechnicalDetails = false,
  loading = false,
  emptyMessage = 'Verification details will appear after you complete KYC.',
}) => {
  const [showTechnical, setShowTechnical] = useState(showTechnicalDetails);

  if (loading) {
    return (
      <section aria-label="KYC verification details" className="space-y-3">
        <p className="text-sm font-semibold text-slate-900">{title}</p>
        <PanelSkeleton />
      </section>
    );
  }

  if (!verification) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        {emptyMessage}
      </div>
    );
  }

  const pan = verification.pan;
  const aadhaar = verification.aadhaar;
  const hasPan = Boolean(verification.pan_verified && pan);
  const hasAadhaar = Boolean(verification.aadhaar_verified && aadhaar);

  if (variant === 'summary') {
    const summaryData = {
      pan: pan?.pan || '',
      name: pan?.name || aadhaar?.name || '',
      date_of_birth: pan?.date_of_birth || aadhaar?.date_of_birth || '',
      pan_type: pan?.pan_type || '',
      aadhaar_masked: aadhaar?.uid_masked || '',
      name_source: pan?.name_source || aadhaar?.name_source || '',
      date_of_birth_source: pan?.date_of_birth_source || aadhaar?.date_of_birth_source || '',
    };
    if (!summaryData.pan && !summaryData.name && !summaryData.aadhaar_masked) {
      return (
        <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
          {emptyMessage}
        </div>
      );
    }
    return (
      <div className="rounded-xl border border-emerald-200 bg-emerald-50/40 p-4 space-y-3">
        <p className="text-sm font-semibold text-emerald-900">{title}</p>
        <DetailGrid fields={SUMMARY_FIELDS} data={summaryData} variant="summary" hideEmpty />
      </div>
    );
  }

  if (!hasPan && !hasAadhaar) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        {emptyMessage}
      </div>
    );
  }

  const technicalButton = (section) => (
    <button
      type="button"
      onClick={() => setShowTechnical((v) => !v)}
      className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-700 hover:text-indigo-900"
      aria-expanded={showTechnical}
    >
      {showTechnical ? <FaChevronUp size={10} /> : <FaChevronDown size={10} />}
      {showTechnical ? 'Hide' : 'Show'} {section} details
    </button>
  );

  return (
    <section aria-label="KYC verification details" className="space-y-4">
      <p className="text-sm font-semibold text-slate-900">{title}</p>

      {hasPan ? (
        <DocumentCard
          title="PAN — Cashfree"
          verified={verification.pan_verified}
          technicalToggle={showTechnicalDetails ? technicalButton('provider') : null}
        >
          <DetailGrid fields={PRIMARY_PAN_FIELDS} data={pan} />
          {showTechnical && showTechnicalDetails ? (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Provider record</p>
              <DetailGrid fields={TECHNICAL_PAN_FIELDS} data={pan} />
            </div>
          ) : null}
        </DocumentCard>
      ) : null}

      {hasAadhaar ? (
        <DocumentCard
          title="Aadhaar — DigiLocker"
          verified={verification.aadhaar_verified}
          technicalToggle={showTechnicalDetails ? technicalButton('provider') : null}
        >
          <DetailGrid fields={PRIMARY_AADHAAR_FIELDS} data={aadhaar} hideEmpty />
          {showTechnical && showTechnicalDetails ? (
            <div className="mt-4 pt-4 border-t border-slate-100">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 mb-3">Provider record</p>
              <DetailGrid fields={TECHNICAL_AADHAAR_FIELDS} data={aadhaar} />
            </div>
          ) : null}
        </DocumentCard>
      ) : null}

      {verification.profile_synced_from_kyc ? (
        <p className="text-xs text-emerald-700">
          Profile name and date of birth were synced from verified KYC records.
        </p>
      ) : null}
    </section>
  );
};

export default KycVerificationPanel;
