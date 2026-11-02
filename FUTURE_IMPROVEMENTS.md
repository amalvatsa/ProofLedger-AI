# ProofLedger AI — Future Improvements

This file distinguishes the current interview prototype from proposed production capabilities. None of the workflows below should be presented as implemented unless explicitly marked current.

## Current boundary

The current application has a seeded, read-only vendor master; seeded purchase orders and confirmed commitments; deterministic invoice controls; an explicit synthetic confirmation action; local OCR; an optional evidence-validated Gemini extraction fallback; and a receipt-grounded explanation assistant. It has no user authentication, role-based authorization, secure vendor onboarding, goods-receipt ledger, ERP connection, or production audit/security controls.

## 1. Secure vendor onboarding and administration

Do not add an unauthenticated or visually hidden vendor-admin screen. Vendor creation and activation change financial authority and require a real identity and access-control foundation.

### Proposed data model

- `vendors`: immutable internal vendor ID, legal name, trading names, lifecycle status (`PENDING_VERIFICATION`, `ACTIVE`, `INACTIVE`, `PROHIBITED`), risk status, country, created/updated timestamps, and record version.
- `vendor_tax_registrations`: jurisdiction, registration type, encrypted identifier, verification status, verification source, and verified timestamp.
- `vendor_contacts`: business contact purpose, name, verified email/phone, and validity dates.
- `vendor_bank_accounts`: encrypted/tokenized banking reference, verification state, effective dates, and change-risk flags. ProofLedger should not expose raw account data unnecessarily.
- `vendor_documents`: secure object reference, document type, malware-scan state, retention class, and integrity hash.
- `vendor_change_requests`: requested changes, requester, reason, status, and maker/checker approvals.
- `vendor_audit_events`: actor, action, before/after references, request ID, timestamp, IP/device context, and immutable correlation data.

Unique and duplicate controls should cover internal vendor ID, normalized legal identity, applicable tax registration, and verified banking identity. Potential duplicates should enter review; fuzzy similarity alone must not merge or activate suppliers.

### Permissions and separation of duties

- Requester: submit a new-vendor or vendor-change request, but cannot verify or activate it.
- Verifier: validate identity and supporting evidence, but cannot approve their own request.
- Vendor administrator: activate, deactivate, or prohibit only after required verification and approvals.
- AP analyst: read active vendor evidence needed for invoice decisions; no vendor-authority writes.
- Auditor: read history and evidence without mutation privileges.

High-risk changes such as bank details, tax identity, activation, and reactivation should require step-up authentication and maker/checker approval. Authorization must be enforced server-side for every action.

### Intended workflow

`New vendor request → Pending verification → Evidence validation → Independent approval → Active vendor`

Rejected, inactive, and prohibited are explicit states with reason codes and effective dates. Reactivation creates a new reviewed change request; it does not silently flip a status flag.

### API requirements

- Authenticated, versioned endpoints for create request, add evidence, submit, verify, approve/reject, activate/deactivate/prohibit, and read audit history.
- Per-action authorization, tenant scoping, idempotency keys, optimistic concurrency, request validation, rate limits, and CSRF protection where cookies are used.
- Append-only audit events, encrypted sensitive fields, malware-scanned uploads, retention/deletion policy, and secrets managed outside source control.
- No endpoint may allow a client-supplied `ACTIVE` state without the required server-side verification and approval transition.

## 2. Goods-receipt management

A production ledger should ingest authoritative goods receipts and service-entry records from the ERP or receiving system. Each receipt needs PO line, accepted quantity/value, rejected quantity, receipt/reversal status, warehouse or service owner, timestamps, and source-system identifiers. Reversals must be explicit and auditable.

## 3. Quantity-level three-way matching

True three-way matching requires PO lines, ordered quantities, unit prices, accepted goods/service receipts, previously invoiced quantities, current invoice quantities, and documented tolerances. The engine should compare PO ↔ receipt ↔ invoice at line level and hold claims beyond accepted quantities. The current financial capacity control must not be described as delivery verification.

## 4. LLM-assisted extraction for unfamiliar formats

Current: an explicitly opt-in Gemini fallback can propose fields only when deterministic extraction is incomplete or ambiguous. Every accepted field needs locally corroborated page text, schema/type validation, and total checks; the model cannot decide policy.

Future: evaluate a labeled, representative invoice set; measure field precision/recall and abstention quality by layout/language; calibrate field-level confidence; add asynchronous retries and observability; define data residency and retention controls; and require human review thresholds based on measured risk rather than model self-confidence.

## 5. ERP integration

Start with read-only vendor, PO, invoice, and goods-receipt synchronization using stable source IDs and reconciliation jobs. Any write-back should use idempotent commands, explicit approval, least-privilege service identities, retry/dead-letter handling, and a durable audit trail. A ProofLedger recommendation must never equal automatic payment authorization.

## 6. Role-based authorization

Add enterprise identity integration, short-lived sessions, tenant isolation, role and attribute policies, server-side authorization middleware, step-up authentication for high-risk actions, and access reviews. Roles should separate AP analysis, buyer resolution, vendor administration, confirmation/posting, security administration, and audit.

## 7. Production security and audit requirements

- Encrypted object storage, database encryption, managed keys, rotation, and secret management.
- Malware scanning, PDF sandboxing, MIME/content validation, upload quotas, and decompression/resource limits.
- Immutable decision and change audit events with actor, evidence version, policy version, and correlation IDs.
- Data classification, minimization, retention, legal hold, deletion, backup/restore testing, and disaster recovery.
- Centralized logs, traces, metrics, alerting, dependency/container scanning, SAST/DAST, penetration testing, and incident response.
- Queue-backed workers, retry policies, idempotency, Postgres concurrency controls, and production availability targets.
- Privacy and provider governance for any external AI processing, including contractual retention, regional routing, and opt-out requirements.

