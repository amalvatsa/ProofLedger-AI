# ProofLedger AI

**Every invoice gets a decision. Every decision has proof.**

ProofLedger AI is a working Zamp ASA PS-1 case-study prototype. It accepts genuine invoice PDF bytes, extracts supplier claims using embedded text or local OCR with an optional evidence-validated Gemini fallback for unfamiliar layouts, checks authoritative synthetic vendor/PO/confirmed-invoice records, and saves one explainable recommendation:

- `READY_FOR_POSTING` — every required control passed. This is a recommendation, not an ERP post or payment.
- `NEEDS_REVIEW` — missing, ambiguous, or unsupported evidence requires authorized human judgment.
- `BLOCKED` — reliable evidence confirms a policy violation such as a duplicate, PO overrun, supplier/PO conflict, inactive supplier, or invalid monetary claim.

All vendors, POs, invoices, and balances are fictional. Tax handling is an illustrative business assumption, not tax advice.

The interface is intentionally desktop-web only with a fixed sidebar and a 1280px minimum canvas; mobile navigation and mobile layout variants are not included.

### Optional unfamiliar-layout extraction

Deterministic extraction always runs first. To allow a Gemini structured-output attempt only when core fields are missing or ambiguous, explicitly opt in:

```bash
PROOFLEDGER_GEMINI_EXTRACTION_ENABLED=true
PROOFLEDGER_GEMINI_EXTRACTION_MODEL=gemini-3.6-flash
GEMINI_API_KEY=your-key
```

The fallback sends the PDF and locally extracted page text to Gemini. It cannot approve an invoice or change a policy result. Every proposed non-null value must include a page number and verbatim source snippet that matches local page text. The application then validates the field type, date, currency, bounded monetary values, source evidence, and `net + tax = gross` tolerance before setting extraction quality to verified. A reliably sourced negative value remains visible to the policy engine and is blocked; invalid JSON, API failures, unsupported values, or missing evidence remain unverified and route to review.

Actual limitations: this path is opt-in because PDFs leave the local machine; it is capped at 10 pages; values without locally corroborated text are rejected; an image-only PDF still needs local OCR text for field evidence; ambiguous numeric dates become null; line items are descriptions rather than a full quantity/rate table; a missing PO by itself does not trigger an external call; and no production accuracy benchmark has been established.

### Partial invoices and three-way matching boundary

ProofLedger supports legitimate partial invoicing financially. Multiple invoices may reference the same PO as long as each has a distinct same-supplier invoice identifier and every new net claim fits within `authorized PO net − previously confirmed invoice net`. Merely sharing a PO never makes two invoices duplicates, and evaluating a recommendation does not consume capacity.

The current prototype does **not** claim physical quantity or delivery verification. Quantity-level three-way matching requires authoritative PO line items, ordered quantities, unit prices, goods-receipt records, accepted quantities, previously invoiced quantities, and configured price/quantity tolerances. Until those records exist, ProofLedger reports only financial utilization and must not imply that goods were delivered or accepted.

## One-time setup

Requirements: Python 3.11+, Node.js 20+, npm, and optional Tesseract for the scanned-invoice success path. Without Tesseract, scanned PDFs fail safely to review.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_demo_data.py
cd frontend
npm install
npm run build
cd ..
```

Start the combined production build:

```bash
chmod +x start.sh
./start.sh
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Runtime uploads and SQLite data live under `data/runtime/` and are excluded from source control.

### Enable the invoice AI assistant

The application works without an LLM. The receipt-grounded assistant uses the Google Gemini API. Copy the example configuration, add your Gemini key, and restart the application:

```bash
cp .env.example .env
# Edit .env and set GEMINI_API_KEY, then:
./start.sh
```

The default model is `gemini-3.6-flash` with minimal thinking. Gemini thinking levels are `minimal`, `low`, `medium`, or `high`.

Gemini receives only a constrained snapshot of the manually selected Decision Receipt. Unrelated and prompt-injection requests are rejected before the model call, and the model cannot change policy results or perform payment/posting actions. The UI distinguishes a key that is merely **configured** from a provider that has returned a **verified** live answer, shows the model used for each answer, and visibly reports configuration, quota, rate-limit, safety-block, and provider failures.

### Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts\generate_demo_data.py
cd frontend
npm install
npm run build
cd ..
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

## Development mode

Terminal 1:

```bash
source .venv/bin/activate
python -m uvicorn backend.app.main:app --reload --port 8000
```

Terminal 2:

```bash
cd frontend
VITE_API_URL=http://127.0.0.1:8000 npm run dev
```

The Vite UI is then available at [http://127.0.0.1:5173](http://127.0.0.1:5173).

## Verification

```bash
./.venv/bin/python -m pytest -q
cd frontend
npm run typecheck
npm run build
```

With the application running, execute the reusable live-server verification:

```bash
cd "/path/to/ProofLedger-AI"
./.venv/bin/python scripts/verify_live_application.py
```

This uploads the five interview PDFs to the real localhost API, verifies uploaded-byte hashes and persisted documents, checks every financial value and rule outcome, confirms the nine-event sequence, reopens History, checks the Review Queue, and proves that recommendations do not consume PO capacity.

When a real provider key is configured, verify one grounded chatbot answer and its pre-provider prompt-injection guardrail:

```bash
PROOFLEDGER_EXPECTED_PROVIDER=gemini ./.venv/bin/python scripts/verify_live_assistant.py
```

The backend suite uses an isolated temporary SQLite database. It covers real machine-readable PDFs, normalized duplicates, cumulative PO capacity, inclusive tax, actual OCR or truthful unavailability, two unfamiliar-layout PDF formats, structured-output validation, invented or unsourced values, provider and JSON failures, unreconciled totals, ambiguous/missing fields, embedded prompt injection, invalid PDFs, idempotent demo confirmation, events, notes, and persistent history.

## Demo PDFs

The generated files are in `demo_samples/`:

- `happy_path.pdf`
- `duplicate_invoice.pdf`
- `split_po_overspend.pdf`
- `split_po_within_balance.pdf`
- `scanned_inclusive_tax.pdf` — raster-only; contains zero embedded text
- `ambiguous_po.pdf`

The sample picker selects one of these genuine PDFs and uploads it through the same `POST /api/runs` endpoint used by independent uploads. No decision branches on filename, sample choice, fixture ID, or invoice ID.

The final five-file interview pack is in `demo_samples/interview/`; see its `TEST_CASE_GUIDE.md` for exact amounts, decisions, rules, and talking points.

## Main routes

- `#/` — Overview with real decision counts and recent runs
- `#/process` — independent upload/sample picker, persisted event timeline, and Decision Receipt
- `#/review` — searchable Needs Review and Blocked queue with reviewer notes
- `#/history` — persistent run history and read-only PO ledger
- `#/runs/:id` — reopen the saved Decision Receipt

The fixed left navigation includes **Invoice AI** on every page. Opening it first presents a manually searchable, decision-grouped receipt selector; the chat composer remains unavailable until one completed invoice is chosen. Changing or closing the assistant clears that scope and relocks chat. Answers retain deterministic evidence references and server-side guardrails. `/api/assistant/status` reports whether a real model is configured; `/api/runs/{id}/assistant` accepts guarded questions for the selected receipt only.

API documentation is available at `/docs`. Important endpoints include `/api/runs`, `/api/summary`, `/api/ledger`, `/api/health`, `/api/runs/{id}/notes`, and `/api/runs/{id}/confirm`.

## Docker

```bash
docker build -t proofledger-ai .
docker run --rm -p 8000:8000 -v proofledger-data:/data proofledger-ai
```

## Honest scope

This is a synthetic-data prototype with real document processing and deterministic financial controls. It does not include authentication, production security review, real vendor data, email ingestion, payment execution, ERP write-back, approval chains, or a production deployment. See `TRADEOFFS.md` and `IMPLEMENTATION_STATUS.md` for details.
