# BBPS + BillAvenue Gap Matrix

## Before vs After (hardening pass)

| Requirement | Before | After | Code location | Risk | Fix action | Test case |
|---|---|---|---|---|---|---|
| MDM-first orchestration (no mock fallback) | Partial | Pass | `backend/apps/bbps/services.py`, `backend/apps/integrations/bbps_client.py` | payments on stale catalog | hard-stop on live config only + legacy path disabled | `BbpsGovernanceFlowTests.test_provider_discovery_from_mapping` |
| request/encryption/transport protocol rules | Partial | Pass | `backend/apps/integrations/billavenue/client.py` | 200 HTML unauthorized ambiguity | raw `encRequest` for MDM, POST params for others, auth error taxonomy | parser + client flow tests/manual Postman |
| Channel-wise mandatory device fields | Fail | Pass | `backend/apps/bbps/service_flow/compliance.py`, `fetch_service.py`, `payment_service.py` | NPCI/BillAvenue rejects request | enforce MOB/MOBB and INT/INTB mandatory fields | add unit validation path |
| Payment mode/channel restrictions from MDM | Fail | Pass | `backend/apps/bbps/service_flow/compliance.py`, `payment_service.py` | invalid pay mode at runtime | enforce biller mode/channel list + amount bands + restricted combinations | `test_mode_channel_matrix_validation` |
| Paise conversion correctness | Partial | Pass | `backend/apps/integrations/bbps_client.py`, `payment_service.py` | over/under charge | central paise conversion before API payload | existing + flow validation |
| Fetch→Pay linkage for mandatory-fetch billers | Fail | Pass | `backend/apps/bbps/service_flow/compliance.py`, `payment_service.py`, `fetch_service.py` | wrong account/payment mismatch | enforce latest fetch session and request id match | `test_fetch_pay_linkage_for_mandatory_fetch` |
| Awaited 15-minute status cooling | Fail | Pass | `backend/apps/bbps/service_flow/compliance.py`, `status_service.py`, `views.py` | premature finalization | block poll before cooling period expires | API behavior in `poll_status_view` |
| Complaint cooling by category (0h vs 24h) | Fail | Pass | `backend/apps/bbps/service_flow/compliance.py`, `complaint_service.py` | invalid CMS raise | enforce category-based cooling at registration | complaint service path |
| planMdmRequirement and ACTIVE-only plans | Partial | Partial | `backend/apps/bbps/service_flow/plan_service.py` | deactivated plans shown | keep ACTIVE/non-expired plans only in local store | plan pull run checks |
| CCF1 handling | Partial | Pass | `backend/apps/bbps/service_flow/compliance.py`, `payment_service.py` | settlement mismatch | compute floor(CCF1+GST) and inject payload amountInfo.CCF1 | `test_ccf1_computation_floor` |
| Transaction query UX/API | Fail | Pass | `backend/apps/bbps/views.py`, `serializers.py`, `urls.py`, `frontend/src/components/bbps/BbpsTransactionQuery.jsx` | no compliant query flow | add track by txn/mobile/request and response rendering | manual UI + API |
| Complaint register/track UX | Partial | Pass | `frontend/src/components/bbps/BbpsComplaintManager.jsx`, `api.js` | poor enterprise usability | add dedicated complaint screens and dispositions | manual UI flow |
| Bharat Connect branding stages | Fail | Partial | `frontend/src/components/bbps/BharatConnectBranding.jsx`, `BillPayment.jsx`, `CreditCardBill.jsx` | frontend approval delay | stage-1/2/3 placeholders + sonic cue hook | manual screen checks |
| Ops readiness diagnostics | Partial | Pass | `backend/apps/bbps/views.py`, `frontend/src/components/admin/BillerSyncDashboard.jsx` | unclear blockers | add UAT readiness endpoint + dashboard render | manual admin checks |

## Remaining external blocker

- BillAvenue UAT entitlement can still return `Unauthorized Access Detected` for MDM even with valid request shape and credentials. This is upstream and must be resolved by BillAvenue support for institute + agent entitlement mapping.
