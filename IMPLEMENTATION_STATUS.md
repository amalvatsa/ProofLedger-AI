# ProofLedger AI — Implementation Status

Last updated: 2026-11-02 (Asia/Kolkata)

## Current milestone

Phases 1–5 complete for the local/Docker case-study prototype. The verified production build is running locally at `http://127.0.0.1:8000`.

## Completed

- Read the official Zamp case study, final master implementation brief, and priority checklist.
- Created the project structure and source-controlled synthetic vendor, PO, and confirmed-invoice seed data.
- Implemented the FastAPI upload API, SQLite persistence, backend-derived run events, history, review notes, summary, PO ledger, health diagnostics, and idempotent synthetic confirmation.
- Implemented exact-decimal policy controls `V001`, `I001`, `P001`, `T001`, `D001`, `B001`, and `X001` with safe decision precedence.
- Generated six genuine PDF fixtures across three visual layouts, including a raster-only scan with zero embedded text.
- Implemented embedded-text extraction plus a real local Tesseract OCR fallback.
- Built the responsive React + TypeScript interface with Overview, Process Invoice, Review Queue, History, saved receipt routes, and read-only PO ledger.
- Connected every visible control to real behavior: independent upload, genuine sample upload, filters, search, receipt inspection, evidence expansion, reviewer notes, and explicit idempotent demo-ledger confirmation.
- Added a backend-derived animated timeline, actual PDF preview, exact PO-capacity visualization, extraction method disclosure, responsive navigation, focus states, and reduced-motion support.
- Added combined local production serving, Docker packaging, startup instructions, tradeoffs, and a five-minute demo guide.
- Final desktop-web UI pass: removed all mobile navigation and responsive layout branches, fixed the sidebar in place, and enforced a 1280px desktop canvas.
- Made all four Overview summary cards keyboard-accessible links: Processed → History, Ready → filtered History, and Needs Review / Blocked → filtered Review Queue views.
- Added a branded pre-React loading screen with the ProofLedger document-check icon, accessible status text, reduced-motion support, and a real bundle-initialization progress treatment with no artificial delay.
- Changed stored invoice delivery to an inline PDF response so opening the evidence preview no longer triggers an automatic file download.
- Reworked `DEMO_SCRIPT.md` into a verified sub-five-minute recording walkthrough plus interview Q&A, using the application’s exact sample names, decisions, amounts, extraction modes, and honest limitations.
- Added a real receipt-grounded AI assistant backed by the OpenAI Responses API, with `gpt-6-luna` as the default model, `store: false`, selected-receipt-only context, deterministic evidence references, and no state-changing tools.
- Added server-side scope, cross-invoice, prompt-injection, payment, approval, and posting guardrails; unrelated questions are rejected before a provider call and the deterministic policy decision remains authoritative.
- Added a polished desktop assistant experience with visible boundaries, suggested questions, grounded evidence chips, honest configuration status, and no simulated model fallback.
- Promoted Invoice AI into the fixed left navigation so it is available on every page. The global drawer requires manual receipt selection, groups saved invoices by attention level, supports invoice/supplier search, hides the chat composer until selection, and resets scope when changing or closing the assistant.
- Added `.env.example`, startup configuration loading, AI health/status reporting, API documentation, and an updated recording/interview script that begins with the product, problem, differentiation, and step-by-step workflow.

## Verification results

- `./.venv/bin/python -m pytest -q` — **105 passed** on 2026-11-02, including **46 dedicated assistant and guardrail tests** plus guarded extraction-fallback coverage.
- `cd frontend && npm run typecheck` — **passed** on 2026-11-01.
- `cd frontend && npm run build` — **passed** on 2026-11-01 with Vite 6.4.5: 1,946 modules transformed; production assets emitted successfully in 1.65s.
- Local production health: `GET /api/health` returned **HTTP 200** with SQLite healthy and Tesseract available; `/` returned **HTTP 200** with the built frontend.
- Browser smoke test: the happy-path PDF was uploaded through the UI and returned `READY_FOR_POSTING` with 7/7 controls, source preview, real events, and INR 75,000 remaining.
- Browser exception test: cumulative split-PO invoice returned `NEEDS_REVIEW` with INR 30,000 remaining and an exact INR 5,000 overage under `B001_PO_REMAINING`.
- Browser persistence test: reviewer note saved, Review Queue populated, History survived refresh, the receipt reopened by run ID, and the PO ledger showed confirmed/remaining values.
- Browser console check after the end-to-end flow: **0 errors and 0 warnings**.
- Verified fixture outcomes: clean and within-balance split → Ready; normalized duplicate → Blocked; cumulative overspend and ambiguous PO → Needs Review; image-only inclusive-tax scan → Ready when local OCR succeeds.

### Latest extraction fallback verification — 2026-11-02

- Added an explicitly opt-in structured extraction fallback for unfamiliar invoice layouts. Embedded text and Tesseract OCR still run first, and complete deterministic results do not call an external model.
- The fallback can fill only missing or ambiguous fields, requires page-linked verbatim evidence for every accepted value, preserves nulls for unknowns, and cannot replace deterministic fields or alter policy outcomes.
- Field types, dates, currencies, bounded monetary values, source snippets, and `net + tax = gross` are validated before extraction can be marked verified. Provider errors, malformed JSON, uncertain evidence, and unreconciled totals fail closed to `NEEDS_REVIEW`.
- Added portrait single-page and landscape multi-page PDF tests, invalid-output/provider-failure tests, evidence and total-reconciliation tests, and regression coverage proving all six existing samples retain their extraction paths and decisions.
- Full backend suite: **105 passed**. Frontend TypeScript production build: **passed** with Vite 6.4.5 and 1,946 modules transformed.
- Isolated live verification passed for all existing samples and for a genuinely unfamiliar synthetic layout processed through the configured Gemini API. The unfamiliar invoice was accepted only after ten source-linked fields and its totals validated.
- Processing now exposes nine backend events: received, document reading, extracted, interpreted, evidence validated, vendor validated, PO matched, business rules checked, and decision saved. The UI presents these as friendly, provider-neutral progress stages.

### Latest thorough live verification — 2026-10-31

- `./.venv/bin/python scripts/verify_live_application.py` — **passed** against `http://127.0.0.1:8000`.
- Uploaded all five required genuine PDFs and verified source SHA-256 hashes against the persisted document endpoint.
- Every case saved the exact seven ordered backend events and seven policy checks.
- Expected live summary delta: **5 processed, 2 Ready, 2 Needs Review, 1 Blocked** — matched exactly.
- Happy path: net INR 25,000, tax INR 4,500, gross INR 29,500; PO authorized INR 120,000, confirmed INR 45,000, remaining INR 75,000.
- Duplicate: normalized `inv 2048` matched confirmed `INV-2048` and was `BLOCKED` under `D001_DUPLICATE`.
- Cumulative overspend: net INR 35,000 against INR 30,000 remaining; exact INR 5,000 overage and `NEEDS_REVIEW` under `B001_PO_REMAINING`.
- Scanned inclusive-tax case: zero embedded text, `OCR_EXECUTED`, net INR 10,000 + included tax INR 1,800 = gross INR 11,800, `READY_FOR_POSTING`.
- Ambiguous PO: no PO selected; candidates `PO-4001` and `PO-4002` surfaced; `NEEDS_REVIEW` under `P001_PO_MATCH`.
- Ledger before/after the five recommendations was identical; no recommendation consumed budget.
- The same five cases were then processed through the React sample-picker UI. Each displayed the expected status, invoice ID, seven-stage timeline, Decision Receipt, and PDF preview.
- Review Queue filters: Blocked returned only Blocked rows; Needs Review returned only Needs Review rows; supplier search narrowed correctly after React state update.
- History contained **12 persisted runs** after reload; OCR receipt reopened successfully; reviewer note persisted; PO ledger remained INR 75,000 / INR 30,000 / INR 50,000 remaining for `PO-1001` / `PO-2002` / `PO-3001`.
- Browser console after all UI flows: **0 errors and 0 warnings**. Server request log showed successful 200/201/202 responses and no tracebacks.
- Final desktop-only production build: TypeScript passed; Vite transformed 1,944 modules in **1.42s**. Summary-card navigation verified with 13 Processed, 5 Ready-only, 6 Needs Review-only, and 2 Blocked-only rows; browser console remained clean.
- Loading-screen build: TypeScript passed; Vite transformed 1,945 modules in **1.52s**. The served production HTML contains the loader before the module script, React replaces it successfully, and the browser console reports zero errors or warnings.
- Inline-preview regression check: the document endpoint returned **HTTP 200**, `Content-Type: application/pdf`, and `Content-Disposition: inline`; the automated test also verified genuine `%PDF-` bytes.
- Invoice AI automated verification: selected-receipt context isolation, deterministic evidence references, missing-credential behavior, unrelated-request rejection, prompt-injection rejection, output parsing, and financial-action post-guardrails all passed.
- Invoice AI live API verification: `/api/assistant/status` now truthfully returns `configured: true` with `gpt-6-luna`; unrelated, prompt-injection, and cross-invoice requests each returned **HTTP 422** before an external provider call.
- Global Invoice AI browser verification: the launcher appeared on the application shell, chat remained locked with no composer before selection, receipts loaded in Needs attention / Ready for posting groups, search narrowed the list, selecting `KITE-118` bound context `160d2190`, Change invoice and close/reopen both relocked chat, and the browser reported **0 console errors**.
- Latest frontend verification with the global assistant: TypeScript passed; Vite 6.4.5 transformed **1,946 modules** and emitted the production build in **1.65s** on 2026-11-01.
- Comprehensive Invoice AI prompt verification: **46 assistant tests passed** across natural contextual prompts, topic evidence, injection and cross-invoice rejection, history sanitization, request limits, receipt isolation, provider privacy, provider failure mapping, malformed responses, and post-model financial-action refusal.
- Live model boundary test: the corrected `what is this?` prompt passed local validation for synthetic receipt `KITE-118` and reached the OpenAI Responses API; OpenAI returned HTTP 429. The UI surfaced the rate-limit message and changed the badge from `gpt-6-luna · configured` to `Provider rate-limited`.
- Final browser regression: injection, weather, and another-invoice prompts were rejected locally; close/reopen restored the locked selector with no composer; browser console remained at **0 errors and 0 warnings**.
- Final live server smoke test: health and assistant status returned **HTTP 200**, the strengthened unrelated-question check returned **HTTP 422**, missing real-provider configuration returned **HTTP 503**, the HTML shell returned `Cache-Control: no-store`, and the request log contained no tracebacks.

## Genuine blockers

- No public deployment was attempted because no production hosting target or credentials were supplied. A static-only deployment would be misleading because the working FastAPI/SQLite/OCR backend is required.
- A valid `OPENAI_API_KEY` is loaded locally, but the live OpenAI Responses API returned HTTP 429 rate limiting for the synthetic `KITE-118` test. The key is configured; a successful model answer is not yet verified. Check the OpenAI project usage/billing limits or retry after the provider limit clears.
- The five-minute video must still be recorded and uploaded by the candidate; `DEMO_SCRIPT.md` provides the verified run order and talking points.
