/**
 * Post-login routing for hierarchy onboarding (KYC + MPIN deferred to end user).
 */
export function getPostLoginPath(user) {
  const ob = user?.onboarding;
  // Older cached sessions without `onboarding`: keep previous behaviour (MPIN gate only).
  if (ob == null) return '/mpin-verification';
  if (!ob.account_ready) {
    if (!ob.kyc_complete) return '/onboarding/kyc';
    if (!ob.mpin_set) return '/onboarding/mpin-setup';
  }
  return '/mpin-verification';
}
