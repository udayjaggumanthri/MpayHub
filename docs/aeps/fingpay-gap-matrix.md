# AEPS / Fingpay — Gap Matrix & Credentials Checklist

Generated from the Enterprise Completion Plan against `AEPS UPDATED DOCS/` and the Partner codebase.
RSA public cert in updated docs is **byte-identical** to `backend/apps/integrations/fingpay/assets/fingpay_public_production.cer`.

## Completeness

~80% of Fingpay product surface is implemented. Live money is blocked by Tapits enablement + three code gaps (CW/AP OTP > ₹5000, outbound 3-way recon, first-class Bank eKYC) and provider-config RBAC.

## Gap matrix

| Doc requirement | Code status | Owner |
|-----------------|-------------|-------|
| Onboarding → eKYC → 2FA → products → status/ack → recon order | Gates in `services/gates.py` | Code (keep) |
| Onboarding v2 Java / PHP / Simple | Paths + payload mapping | Super Admin: GSTIN/PAN |
| eKYC send/validate/resend/biometric | Implemented | Code (keep) |
| Bank eKYC (`BeKYC` / FP097) | Soft hint only; no persisted state | **Code Phase 2** |
| Daily 2FA AUO (omit empty wadh) | Implemented | Code (keep) |
| CW / BE / MS / AP / CD bio + CD OTP | Implemented | Code (keep) |
| CW/AP Aadhaar OTP when amount > ₹5000 | **Missing** | **Code Phase 3** + Tapits (Simple path?) |
| Success = bankRRN + `00` (91/52/08 rules) | `_is_success` | Code (keep; add tests) |
| Status check + Ack | Implemented | Code (keep) |
| Bank IIN daily refresh | API + command; no cron | **Code Phase 6** |
| Callbacks (mobile I/S/F) | AllowAny, no token/IP | **Code Phase 4** |
| 3-way recon outbound POST | Inbound webhook only | **Code Phase 4** + Tapits prod URL |
| Micro ATM | Out of scope unless contracted | Tapits |
| Provider config Super Admin ownership | Any Admin can edit | **Code Phase 1** |
| Admin tables pagination / CSV | Hard caps, plain tables | **Code Phase 5** |
| AEPS wallet | Isolated ledger (Option A) | Product (Option B deferred) |

## Credentials — Super Admin pastes

Per environment row (Simple / UAT / Prod) in Admin → AEPS → Provider:

- Super Merchant ID (SMID)
- Super Merchant Login ID
- Password (plain or MD5 mode)
- `secret_key` (Simple hashes + 3-way recon)
- RSA public cert (encrypted UAT/Prod only; bundled cert OK)
- GSTIN + companyOrShopPan defaults
- Egress IP override only if NAT

## Credentials / ops — Tapits must email

- `secret_key` for this SMID (if not issued)
- IP whitelist for this VPS public IP (+ SMID)
- AEPS product enablement (clears `10027`)
- Production 3-way recon URL (after UAT logs)
- Whether `send/otp` (> ₹5000) has a Simple-API path
- Whether MATM is contracted

## Open questions for Tapits

1. Simple path for CW/AP OTP > ₹5000?
2. Does Fingpay also push recon to us, or only expect outbound?
3. Exact OTP threshold / per-bank variance?
4. Confirm `subMerchantId` not required for this SMID.
