# ProofLedger AI — Video Script and Interview Preparation

Use this as a conversational guide, not a speech to read word for word. It is aligned to the verified local build as of 2026-11-01. Show the real application and genuine PDFs; never claim a model answer unless the model is visibly connected and the answer has been tested.

## The story in one sentence

ProofLedger turns an invoice PDF into an auditable finance recommendation, then lets an analyst question the saved Decision Receipt through a tightly scoped AI assistant without giving the model authority to approve, post, or pay anything.

## Verified facts to keep consistent

- Working local URL: `http://127.0.0.1:8000`
- Invoice extraction uses embedded PDF text with a genuine local Tesseract OCR fallback.
- Financial controls are deterministic: approved vendor, required fields, exact PO match, total reconciliation, duplicate history, remaining PO capacity, and extraction quality.
- The receipt assistant uses the Google Gemini API with `gemini-3.6-flash` only when `GEMINI_API_KEY` is configured.
- The model receives a constrained snapshot of the selected Decision Receipt—not the whole database or another invoice.
- A `READY_FOR_POSTING` result is a recommendation only. Neither the policy engine nor the AI executes payment or ERP posting.
- Recommendations do not consume PO capacity. Only the explicit synthetic demo-ledger confirmation changes confirmed commitments.
- All vendors, POs, confirmed invoices, and sample documents are synthetic.
- The interface is intentionally desktop-web only.

## Before recording

1. Start the application and open `http://127.0.0.1:8000` at a desktop width of at least 1280 px.
2. Run `./.venv/bin/python -m pytest -q`, `cd frontend && npm run typecheck`, and `npm run build`.
3. Run `./.venv/bin/python scripts/verify_live_application.py` if the database or environment has changed.
4. Confirm the five interview PDFs and guide exist in `demo_samples/interview/`.
5. If demonstrating the AI, set `GEMINI_API_KEY`, restart the app, and verify `/api/assistant/status` reports `configured: true`.
6. Ask the assistant one known invoice question before recording. If it is not connected, do not simulate an answer; narrate the visible setup state instead.
7. Do not click **Confirm as processed (demo ledger)** during the main recording because it changes later PO balances.
8. Leave 15–20 seconds for upload or OCR variability and finish before five minutes.

## Ready-to-use spoken script — target 4:55

### 0:00–0:45 — What the project is and why we built it

**On screen:** Open **Overview**. Point to Process invoice, Review queue, and History.

> “ProofLedger AI is an evidence-to-decision workspace for accounts payable. We built it because invoice processing is not just PDF extraction. An analyst must identify the supplier, find the correct purchase order, reconcile tax, check duplicate history, and make sure earlier invoices have not exhausted the PO. When the evidence is incomplete, the safe answer is not a guess—it is a clearly explained review.”

### 0:45–1:15 — How it is different

**On screen:** Open **Process invoice**.

> “Most invoice demos stop after extracting fields. ProofLedger separates three responsibilities. Document extraction reads the supplier’s claims. Deterministic controls compare those claims with approved vendors, POs, and confirmed invoices. Then an invoice-scoped AI assistant explains the saved receipt in natural language. The model can help an analyst understand the evidence, but it cannot change the policy result or authorize payment.”

### 1:15–2:10 — Step 1: upload and happy-path decision

**On screen:** Select **Clean happy path** and click **Process this sample**. Let the genuine upload finish.

> “I am uploading a real PDF through the same API as a manually selected file. The backend validates the PDF bytes, stores a hash, extracts embedded text, and saves each workflow event. It identifies Acme Office Systems, invoice PL-10001, and PO-1001.”

When the Decision Receipt appears:

> “The invoice claims ₹25,000 net plus ₹4,500 tax, for ₹29,500 gross. PO-1001 authorizes ₹120,000. Earlier confirmed invoices use ₹45,000, so ₹75,000 remains. All seven controls pass and the recommendation is Ready for posting. That is a recommendation—not a payment or ERP action.”

**Point to:** the backend event timeline, source-PDF preview, amounts, PO capacity, seven rule rows, and next action.

### 2:10–2:45 — Step 2: ask the invoice AI

**On screen:** Click **Invoice AI** in the fixed left navigation. Show that chat is locked, search for `PL-10001`, and manually select the Acme receipt. Only continue if the status badge shows the configured model.

Ask: **“Why did this invoice receive this decision?”**

> “The assistant is available from every page, but it cannot chat until I manually choose one saved receipt. The selection binds the conversation to that receipt ID. Its server-side context includes this invoice’s fields, calculations, rule outcomes, extraction evidence, and next action—not the full database. Changing or closing the assistant clears the scope and locks chat again.”

Then mention the guardrail test:

> “Unrelated questions, requests for another invoice, and prompt-injection attempts are rejected before a model call. Model output also passes a financial-action guardrail. The saved deterministic decision remains the source of authority.”

**If the status says Model setup needed, say this instead:**

> “The UI is intentionally honest: without a real API credential it shows Model setup needed and produces no simulated answer. The deterministic invoice workflow remains fully available.”

### 2:45–3:35 — Step 3: cumulative PO overspend

**On screen:** Process **Cumulative PO overspend**.

> “This PO authorizes ₹100,000, but earlier confirmed invoices have already used ₹70,000. The new invoice requests ₹35,000 net. Comparing it only with the original PO would look safe. ProofLedger calculates the remaining ₹30,000 and identifies the exact ₹5,000 overage.”

When the receipt appears:

> “The result is Blocked under B001 because the reliable net claim exceeds the strict remaining PO budget by ₹5,000. The next action is to obtain a formally approved PO amendment or a corrected invoice. The AI can explain this arithmetic, but it cannot override it.”

### 3:35–4:05 — Step 4: normalized duplicate

**On screen:** Process **Normalized duplicate**.

> “The supplier writes the identifier as ‘inv 2048’, while the confirmed ledger contains ‘INV-2048’. ProofLedger normalizes the vendor and invoice identifier, finds the confirmed duplicate, and blocks the recommendation under D001. Formatting differences do not bypass the control.”

### 4:05–4:32 — Step 5: ambiguous PO, review, and persistence

**On screen:** Process `05_ambiguous_po.pdf`, then briefly show **Review queue** and **History**.

> “Orchid Events is approved, but the invoice has no PO reference and two open candidate orders. ProofLedger does not guess: it routes the invoice to review and asks the buyer to confirm the correct PO. Review Queue groups the exceptions, and History restores the source document, backend events, calculations, and notes.”

### 4:32–4:55 — Closing judgment and limitations

**On screen:** Return to the strongest Decision Receipt.

> “The main design choice is separating helpful AI from financial authority. AI explains one saved receipt; explicit rules decide whether the evidence supports posting or requires review. This is a one-day prototype with synthetic procurement data, not a production ERP integration. My next steps would be read-only ERP connectivity, role-based approval, and evaluation on anonymized customer invoices.”

Stop recording before 5:00.

## Step-by-step technical process

1. **Receive genuine bytes.** FastAPI accepts PDF uploads, validates the extension, content type, `%PDF-` signature, and 10 MB limit, stores the bytes locally, and calculates a SHA-256 hash.
2. **Create an auditable run.** A SQLite record is created before processing; every real stage writes a persisted backend event.
3. **Extract invoice evidence.** `pdfplumber` reads embedded text. If too little usable text exists, `pypdfium2` renders pages and local Tesseract performs OCR.
4. **Interpret constrained fields.** The backend maps supplier, invoice number, issue date, PO reference, currency, tax treatment, net, tax, and gross into a fixed schema with source snippets.
5. **Read authoritative synthetic records.** The claimed vendor and PO are compared with approved vendor, purchase-order, and previously confirmed invoice records.
6. **Calculate with Decimal.** Net plus tax is reconciled to gross; normalized duplicates are checked; confirmed net commitments are subtracted from the PO authorization.
7. **Apply seven controls.** `V001`, `I001`, `P001`, `T001`, `D001`, `B001`, and `X001` produce Ready for posting, Needs review, or Blocked. Missing evidence never becomes an approval.
8. **Save the Decision Receipt.** The recommendation, explanation, money breakdown, rule evidence, next action, source document, diagnostics, and events remain available in History.
9. **Render the analyst workspace.** React shows Overview, Process Invoice, Review Queue, History, source preview, backend timeline, PO ledger, Decision Receipt, and a global Invoice AI launcher.
10. **Require explicit scope selection.** The global assistant groups completed receipts by decision, supports search, and withholds the chat composer until the analyst manually chooses one invoice. Changing or closing it resets the conversation and selected context.
11. **Answer receipt questions with AI.** When configured, the server builds a context from only the selected receipt and calls `gemini-3.6-flash` through the Google Gemini API.
12. **Enforce guardrails twice.** Pre-model checks reject unrelated, cross-invoice, and prompt-injection requests. Post-model checks block payment, approval, and posting instructions. Visible evidence references are derived from the receipt.
13. **Keep authority deterministic.** The assistant route cannot edit the run, confirm the demo ledger, post to an ERP, or execute payment.

## Why the AI factor is meaningful

The AI is not a decorative chatbot and it is not asked to make a high-stakes decision. It solves a specific analyst problem: turning a dense receipt into a fast, grounded explanation.

- It can explain why the invoice is ready, blocked, or in review.
- It can walk through PO remaining-balance and overage calculations.
- It can identify which evidence or rule created the exception.
- It can explain the next action already saved on the receipt.
- It cannot answer unrelated questions, inspect another invoice, reveal hidden prompts, or change financial state.
- It produces no fake fallback answer when the real model is unavailable.

This division of labor is the differentiator: generative AI improves comprehension, while deterministic controls preserve auditability and financial safety.

## Accurate interview answers

### What exactly is “AI” in this project?

> “There are two intelligence layers. Local OCR converts image-only invoices into text. The generative layer is a real, receipt-grounded assistant using Google Gemini when configured. It explains only the Decision Receipt an analyst manually selects. It is deliberately not the source of financial authority.”

### Why use an LLM if the decision is deterministic?

> “The rules answer what the system should recommend; the LLM helps a human understand why. That is valuable for exception handling, onboarding, and audit review without introducing model variance into monetary controls.”

### How do the guardrails work?

> “The backend rejects unrelated questions, cross-invoice requests, and common prompt-injection patterns before calling the provider. The model receives only a constrained receipt snapshot plus strict instructions. Its output is checked again for approval, payment, and posting language. The route has no tools that can change financial state.”

### Can prompt injection in an invoice control the assistant?

> “No instruction from invoice content is trusted. The system prompt explicitly treats the invoice context, document snippets, conversation, and question as untrusted data. The assistant has no execution tools and receives a structured snapshot rather than database access.”

### What happens when the API key is absent or rejected?

> “The status endpoint reports the real configuration state. The UI shows Model setup needed and disables chat; it does not substitute a hardcoded response. Rejected credentials and provider errors return safe, explicit errors.”

### Why is this different from an OCR demo?

> “Reading the document is only the first step. ProofLedger combines source evidence with cumulative PO accounting, duplicate prevention, explicit decision rules, a saved audit trail, and a guarded natural-language explanation.”

### What if the invoice has no PO number?

> “The system does not silently choose one. It can display plausible open POs for the supplier, but the result stays in review until an analyst confirms the correct authority.”

### What if a vendor splits one PO across several invoices?

> “The control uses authorized value minus prior confirmed net commitments. The new invoice is tested against remaining capacity, not the original PO amount.”

### Why use Decimal for money?

> “Binary floating-point can introduce rounding errors. Decimal keeps the calculations explicit and exact at financial precision.”

### What if OCR reads an 8 as a 3?

> “Extraction is evidence, not authority. Required fields, totals, vendor records, and POs are cross-checked. Missing or inconsistent evidence routes the case to review.”

### How are duplicates defined?

> “The implemented rule normalizes the invoice identifier within the same vendor and checks the confirmed ledger. Broader fuzzy matching would be added as a review signal with evaluated thresholds, not as an automatic block without evidence.”

### What prevents a hallucinated PO?

> “The PO must exist in the authoritative ledger and match supplier and currency. Neither extracted text nor the LLM can create authorization.”

### How would you measure ROI?

> “I would measure baseline handling time, exception rate, rework, and invoice-error rate, then compare those metrics in a controlled pilot. I would not invent savings before collecting evidence.”

### Is this production-ready?

> “No. It is a focused one-day prototype. Production work includes identity and role separation, encryption and retention policy, observability, rate and cost controls, ERP connectivity, incident handling, and evaluation on a representative labeled invoice set.”

### What would you improve first?

> “First I would add read-only ERP integration and build an evaluation set from anonymized real exceptions. That validates both extraction and decision rules before any write-back or automated approval is considered.”

## Backup route if time is short

Keep the business problem, happy path, cumulative overspend, one guarded AI question, and the closing judgment. Mention the duplicate and OCR case in one sentence each instead of processing them live.

## Recording reminders

- Lead with the finance problem, then explain the product, differentiation, and workflow.
- Use the ₹100,000 / ₹70,000 / ₹35,000 / ₹5,000 example as the memorable proof point.
- Say “recommendation,” not “approval,” “posting,” or “payment execution.”
- Describe the assistant as “receipt-grounded AI,” not an autonomous finance agent.
- If the model is not configured, show the honest setup state and do not improvise a model answer.
- Narrate the actual live result. If it differs from the script, stop and investigate rather than forcing the story.
