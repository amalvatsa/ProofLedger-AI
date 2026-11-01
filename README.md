# ProofLedger AI

**Every invoice gets a decision. Every decision has proof.**

ProofLedger AI is a working Zamp ASA PS-1 case-study prototype. It accepts genuine invoice PDF bytes, extracts supplier claims using embedded text or local OCR, checks authoritative synthetic vendor/PO/confirmed-invoice records, and saves one explainable recommendation:

- `READY_FOR_POSTING` — every required control passed. This is a recommendation, not an ERP post or payment.
- `NEEDS_REVIEW` — evidence, authorization, arithmetic, extraction quality, or remaining PO capacity needs human attention.
- `BLOCKED` — a same-supplier normalized invoice number already exists in the confirmed ledger.

All vendors, POs, invoices, and balances are fictional. Tax handling is an illustrative business assumption, not tax advice.

The interface is intentionally desktop-web only with a fixed sidebar and a 1280px minimum canvas; mobile navigation and mobile layout variants are not included.

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

The application works without an LLM, but the receipt-grounded assistant requires a real OpenAI API credential. Copy the example configuration, add your key, and restart the application:

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY, then:
./start.sh
```

The assistant uses `gpt-6-luna` by default through the OpenAI Responses API. It receives only a constrained snapshot of the manually selected Decision Receipt, sends requests with API storage disabled, rejects unrelated and prompt-injection requests before the model call, and cannot change policy results or perform payment/posting actions. The UI distinguishes a key that is merely **configured** from a provider that has returned a **verified** live answer, and visibly reports rate limiting or provider failure. Set `PROOFLEDGER_LLM_MODEL` in `.env` to use another compatible model.

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
cd "/Users/vimalvatsa/Desktop/Amal Zamp"
./.venv/bin/python scripts/verify_live_application.py
```

This uploads the happy path and all four featured exceptions to the real localhost API, verifies uploaded-byte hashes and persisted documents, checks every financial value and rule outcome, confirms the seven-event sequence, reopens History, checks the Review Queue, and proves that recommendations do not consume PO capacity.

The backend suite uses an isolated temporary SQLite database. It covers real machine-readable PDFs, normalized duplicates, cumulative PO capacity, inclusive tax, actual OCR or truthful unavailability, ambiguous/missing fields, embedded prompt injection, invalid PDFs, idempotent demo confirmation, events, notes, and persistent history.

## Demo PDFs

The generated files are in `demo_samples/`:

- `happy_path.pdf`
- `duplicate_invoice.pdf`
- `split_po_overspend.pdf`
- `split_po_within_balance.pdf`
- `scanned_inclusive_tax.pdf` — raster-only; contains zero embedded text
- `ambiguous_po.pdf`

The sample picker selects one of these genuine PDFs and uploads it through the same `POST /api/runs` endpoint used by independent uploads. No decision branches on filename, sample choice, fixture ID, or invoice ID.

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
