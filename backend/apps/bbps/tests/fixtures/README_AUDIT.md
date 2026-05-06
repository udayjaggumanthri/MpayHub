# MDM billerInfo audit (reference)

`mdm_biller_profiles.json` holds three synthetic shapes used in tests:

1. **simple_dth** — single required `CustomerId` (typical dummy DTH).
2. **utility_with_lov** — `listOfValues` + `paramHelpText` (LOV + help coverage in sync).
3. **plan_mandatory_prepaid** — `planMdmRequirement: MANDATORY` + mobile input (plan picker + pay `plan_id`).

Sync persistence mapping lives in `apps/bbps/service_flow/biller_sync.py` (`billerInputParams` → `BbpsBillerInputParam`). LOV/help extraction is centralized in `apps/bbps/mdm_param_utils.py`.
