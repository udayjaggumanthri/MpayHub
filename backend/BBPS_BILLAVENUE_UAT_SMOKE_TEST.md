# BillAvenue BBPS UAT smoke test (PI39) — SSH / Admin ready

This is a short, repeatable checklist to verify BillAvenue UAT connectivity after deployment.

## Preconditions

- **Whitelisted VPS IP** is approved by BillAvenue.
- **BillAvenueConfig** is saved and **Active + Enabled** in the Admin UI.
- **Secrets** saved in Admin UI:
  - Working key
  - IV
- **Agent profile** saved (AGT channel) with the BillAvenue Agent ID.

## Recommended UAT settings (based on confirmed working VPS reference)

- **Payload format**: `xml`
- **Key derivation**: `md5`
- **encRequest encoding**: `hex`
- **Allow safe provider fallbacks**: ON
- **Txn status 404 HTML path fallback**: ON

> Notes:
> - These are UAT-proven settings for the reference environment. Production may require different crypto/encoding per BillAvenue confirmation.
> - Complaint APIs use `ver=2.0` (handled in code paths).

## Smoke test sequence

### 1) Integration health (admin)

Open **Admin → BBPS Configuration → Biller Sync Dashboard** and verify:

- Active config present
- Credentials present (working key + IV stored)
- Agent profile present
- Entitlement probe (if enabled) is OK

### 2) MDM / Biller Info (critical)

Run a provider sync or a targeted MDM call for a known UAT biller:

- Example biller id: `OTME00005XXZ43`
- Expected: decrypted payload contains `responseCode` = `000` and a `<biller>` block.

### 3) Bill fetch (for a MANDATORY-fetch biller)

Use the biller schema / input params from MDM, then fetch:

- Expected: decrypted payload contains `responseCode` = `000`
- Output includes `billAmount`, `dueDate`, and optional amount options.

### 4) Transaction status sanity

Try a status query using a value that should return **no rows**:

- Expected: decrypted payload contains `responseCode` = `205` and error info like `E003 No transaction found`.

This confirms **status endpoint + decrypt** are working even without doing a payment.

## If something fails

- **`DE001 Invalid ENC request`**: crypto mismatch (key derivation / IV / encoding) or wrong payload format (xml/json). Confirm admin settings match the reference.
- **HTML 404** on txn-status: keep `Txn status 404 HTML path fallback` enabled; if still failing, confirm BillAvenue’s exact UAT path.
- **Unauthorized/Access denied**: entitlement issue; share requestId and audit log excerpt with BillAvenue support.

