# ProofLedger Invoice AI — Chatbot Test Report

Tested: 2026-11-01 (Asia/Kolkata)

## Outcome

The invoice-scoped chatbot is verified across local prompt validation, receipt isolation, request construction, provider error handling, output guardrails, browser behavior, and production build quality. The real OpenAI request reached the provider, but OpenAI returned HTTP 429 rate limiting. A successful live model answer therefore remains unverified until the account limit clears or its usage/billing allowance is increased.

## Automated results

- Assistant-specific backend tests: **46 passed**.
- Complete backend suite: **57 passed**.
- Frontend TypeScript check: **passed**.
- Frontend production build: **passed** with Vite 6.4.5 and 1,946 modules.
- Browser console after the final flow: **0 errors and 0 warnings**.

## Prompt and guardrail matrix

| Area | Examples tested | Result |
| --- | --- | --- |
| Natural selected-receipt prompts | `what is this?`, `Explain it`, `Why?`, `What happened?`, `What next?` | Accepted after a receipt is selected |
| Invoice questions | decision, supplier, PO match, tax/total, duplicate, remaining balance, OCR/source, next action | Accepted and mapped to deterministic evidence labels |
| Unrelated topics | weather, Bitcoin, sky color, poem/creative request | Rejected locally with HTTP 422 |
| Cross-invoice access | another invoice, all invoices, entire database | Rejected locally with HTTP 422 |
| Prompt injection | ignore instructions, reveal system prompt, unrestricted roleplay | Rejected locally with HTTP 422 |
| Rejected-history replay | injection, cross-invoice, and unrelated user messages retained in UI history | Removed before provider request |
| Input boundaries | blank input, 500/501-character boundary, nine history messages, oversized history message | Enforced by the API |
| Receipt isolation | request context inspected during a mocked provider call | Only the selected receipt ID, fields, money, checks, extraction evidence, and next action were present |
| Provider privacy | request payload inspected | `store: false`; bounded history; 500 output-token cap |
| Provider failures | rejected key, rate limit, exhausted quota, HTTP 500, network failure, malformed JSON, empty output | Converted to safe, user-facing errors without provider internals |
| Financial-action output | approve, authorize, pay, post, send payment, “go ahead and pay it” | Replaced by a deterministic refusal preserving the stored decision |
| External links and length | model-returned URL and oversized answer | URL removed; answer length capped |
| Missing receipt | nonexistent run ID | HTTP 404 |

## Live browser verification

1. Opened Invoice AI from the global left navigation.
2. Verified the composer did not exist before manual receipt selection.
3. Selected the synthetic `KITE-118` receipt only.
4. Sent `what is this?`; the corrected local validator accepted it and the request reached the OpenAI Responses API.
5. OpenAI returned a real rate-limit response for both `what is this?` and a later spaced retry using `Why did this invoice receive this decision?`. The application displayed `The AI provider rate limit was reached. Try again shortly.` and changed the header badge to `Provider rate-limited`.
6. Prompt injection, unrelated, and cross-invoice prompts were rejected locally with their expected messages.
7. Closing and reopening Invoice AI cleared the selected scope and conversation; the composer count returned to zero.
8. The status badge now says `configured` when a key exists and uses `verified` only after a successful live answer.

## Defects fixed during testing

- Natural contextual prompts were incorrectly rejected unless they contained an invoice keyword.
- A creative request such as `Write a poem about this` could reach the provider.
- Rejected injection text could remain in history and be included in a later request.
- The post-model action guard missed variants such as `Go ahead and pay it`.
- A malformed HTTP 200 provider response could escape as an unhandled error.
- The green model badge implied live availability when it only proved that a key was configured.

## Remaining external blocker

The configured OpenAI credential is present and accepted far enough for the Responses API to return HTTP 429. A successful evidence-grounded answer cannot be claimed until the provider rate limit clears or the OpenAI project has sufficient usage/billing allowance. No change to deterministic invoice processing is required.
