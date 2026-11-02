# ProofLedger AI — Tradeoffs and Next Steps

## Deliberate choices

### Deterministic controls over autonomous approval

Document extraction can be imperfect. The PDF is treated as supplier-claim evidence; vendor approval, PO authorization, confirmed commitments, duplicates, and final decisions are deterministic. This makes the prototype explainable and safe at the cost of supporting fewer arbitrary layouts.

### Local OCR with a truthful failure mode

Image-only PDFs are rasterized and sent to local Tesseract. If the binary is missing or required fields cannot be verified, the outcome is `NEEDS_REVIEW` with diagnostics. The application never labels machine-text parsing as OCR or pretends OCR succeeded.

### Optional Gemini extraction, never Gemini policy

Unfamiliar layouts may use Gemini structured output only after deterministic parsing is incomplete or ambiguous and only when explicitly enabled. Proposed fields are accepted individually after local page/snippet corroboration, type validation, and amount checks; totals must still reconcile before extraction quality can pass. Gemini never receives vendor-master, PO-ledger, duplicate, or remaining-capacity authority and cannot override their controls.

The safety tradeoff is deliberate: image-only values without local OCR evidence, ambiguous dates, missing snippets, documents over 10 pages, provider failures, and invalid JSON all stay unverified. This produces more human review than an inference-first extractor, but avoids turning plausible model output into posting evidence.

### Polling instead of WebSockets

The frontend polls a small run resource while processing. This keeps a one-day prototype reliable and observable without adding a second real-time transport. A production system could use server-sent events or a queue-backed event stream.

### SQLite and local files

SQLite provides transactional, refresh-persistent demo state with exact-decimal columns and minimal setup. It is not intended for horizontally scaled concurrent workers. Production would use managed Postgres plus encrypted object storage and retention controls.

### Combined production server

Vite builds the static frontend and FastAPI serves it alongside the API. This gives a single local/Docker URL. Development can still use two processes. Hash routing avoids static-server fallback complexity.

## Explicitly omitted

- Authentication, roles, and production authorization
- Email/vendor portals
- Real ERP, payment, or bank integrations
- Payment execution or an “approve anyway” action
- Tax-law validation
- Multi-agent orchestration, RAG, vector databases, or policy builders
- Invented fraud scores, ROI, savings, or accuracy claims
- Public deployment without suitable backend hosting and credentials

## What I would improve next

1. Evaluate extraction on a labeled, representative document corpus and report measured field-level quality.
2. Add encrypted object storage, malware scanning, retention policies, audit access controls, and secrets management.
3. Integrate read-only ERP vendor/PO data, then add controlled write-back behind role separation and approval.
4. Add buyer ownership, assignment, service-level tracking, and structured exception resolution.
5. Evaluate the constrained unfamiliar-layout fallback on labeled documents and calibrate field-level acceptance thresholds.
6. Add queue-backed workers, retries, idempotency keys, observability, and Postgres for production concurrency.
