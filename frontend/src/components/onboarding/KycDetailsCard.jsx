import React from 'react';
import KycVerificationPanel from './KycVerificationPanel';

/**
 * Compact verified KYC summary for onboarding flows.
 */
const KycDetailsCard = ({ details, title = 'Verified details', profileUpdated = false }) => {
  if (!details || (!details.pan && !details.aadhaar_masked && !details.name)) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
        Loading verified details…
      </div>
    );
  }

  const verification = {
    pan_verified: Boolean(details.pan),
    aadhaar_verified: Boolean(details.aadhaar_masked),
    pan: details.pan
      ? {
          pan: details.pan,
          name: details.name,
          date_of_birth: details.date_of_birth,
          pan_type: details.pan_type,
        }
      : null,
    aadhaar: details.aadhaar_masked
      ? { uid_masked: details.aadhaar_masked, name: details.name, date_of_birth: details.date_of_birth }
      : null,
    profile_synced_from_kyc: Boolean(profileUpdated || details.profile_updated),
  };

  return <KycVerificationPanel verification={verification} title={title} variant="summary" />;
};

export default KycDetailsCard;
