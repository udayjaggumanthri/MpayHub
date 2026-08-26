import React from 'react';
import OnboardingFormStep from '../setup/OnboardingFormStep';

/** Merchant onboarding form — sections 1–5 only. eKYC lives at /aeps/ekyc. */
const AepsSetup = (props) => <OnboardingFormStep {...props} />;

export default AepsSetup;
