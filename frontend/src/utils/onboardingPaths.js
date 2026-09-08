/**
 * Post-login routing for hierarchy onboarding (KYC + Admin approval + MPIN).
 * Platform operators (Admin / Super Admin): KYC and MPIN are optional — go to dashboard.
 */
export function getPostLoginPath(user) {
  const ob = user?.onboarding;
  // Older cached sessions without `onboarding`: keep previous behaviour (MPIN gate only).
  if (ob == null) return '/mpin-verification';
  if (ob.must_change_password) return '/onboarding/set-password';

  // Admin / Super Admin: never force KYC or session MPIN
  if (ob.kyc_optional || ob.mpin_optional) {
    return '/dashboard';
  }

  if (!ob.account_ready) {
    // Stay on KYC route while awaiting Admin approval or after rejection.
    if (!ob.kyc_complete) return '/onboarding/kyc';
    if (!ob.mpin_set) return '/onboarding/mpin-setup';
  }
  return '/mpin-verification';
}
