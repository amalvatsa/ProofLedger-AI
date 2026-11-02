# Gemini Extraction Stress Test Report

Tested: 2026-11-02 (Asia/Kolkata)

## Outcome

ProofLedger's unfamiliar-layout extraction path is enabled locally and now maps Gemini structured output into the existing invoice schema with field-level page/snippet evidence. Deterministic policy controls remain authoritative and the model cannot repair or override a completed financial control.

## Defects found and fixed

1. The active `.env` had a Gemini key but did not enable `PROOFLEDGER_GEMINI_EXTRACTION_ENABLED`, so extraction never attempted the fallback.
2. The deterministic tax regex could cross a line boundary from `Tax treatment` to the first amount, incorrectly treating net as tax.
3. The gross-total regex could match `total` inside `subtotal`, locking the net value into `gross_total` before fallback.
4. OCR could join a label and amount (`value6000.00`), causing valid numeric source evidence to be rejected.
5. The structured extraction prompt did not define the exact meaning of every application field clearly enough.
6. The provider output budget was 2,048 tokens and extraction did not request minimal thinking, increasing the risk of truncated structured JSON.
7. Omitted null fields and JSON-fenced provider output were rejected even when all supplied fields used the correct evidence object structure.
8. Provider quota, credential, model, configuration, rate-limit, and availability failures all collapsed into one generic diagnostic.

## Verification

- Full backend suite: **127 passed**.
- PDF extraction suite: **28 passed**.
- Frontend TypeScript check: passed.
- Frontend production build: passed (1,946 modules).
- Source-grounded offline provider-contract run against all nine supplied PDFs: **9/9 expected decisions and field mappings passed**.
  - Ready: modern alternative labels, landscape two-page itemized, bundled inclusive tax, scanned unfamiliar layout.
  - Needs Review: implied/missing PO, missing invoice number, missing date and gross total, unregistered supplier.
  - Blocked: reliably evidenced inconsistent tax arithmetic.

The offline provider-contract run supplies the expected Gemini JSON envelope but still executes ProofLedger's real PDF/OCR text extraction, type normalization, source matching, amount matching, total reconciliation, vendor/PO lookup, duplicate control, PO capacity logic, and final decision engine.

## Live API limitation

The live Google API was reached successfully during testing. Google then returned HTTP 429 `RESOURCE_EXHAUSTED`: the configured project's free-tier limit of 20 `gemini-3.6-flash` generate-content requests per day had been exhausted. ProofLedger now records this specifically as `STRUCTURED_FALLBACK_QUOTA_EXHAUSTED` and safely routes the invoice to review.

A post-fix live-model pass across all nine PDFs has therefore **not** been claimed. After quota resets or billing/quota is increased, run:

```bash
cd /Users/amalvatsa/Downloads/ProofLedger_Gemini_Stress_Tests
/Users/amalvatsa/Desktop/Amal\ Zamp/.venv/bin/python -B run_local_tests.py --url http://127.0.0.1:8000 --all
```

The script does not confirm invoices or consume PO balances, but it does create History records. Clear those test runs before the interview demo.

## Remaining product limitations

- Gemini extraction remains explicit opt-in because invoice bytes leave the local machine.
- Evidence must be corroborated by local PDF/OCR text; visually readable content that OCR misses will remain unverified.
- The schema captures descriptions, not a complete quantity/rate/line-tax table.
- Missing or implied purchase orders are never auto-selected.
- A successful live model call is subject to Google model availability, request limits, and project quota.
- This synthetic pack validates representative layouts; it is not a production accuracy benchmark.
