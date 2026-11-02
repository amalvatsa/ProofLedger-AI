# ProofLedger AI — Interview Test Cases

| PDF | Scenario and invoice | Amounts | Expected result | Interview point |
|---|---|---|---|---|
| `01_valid_invoice.pdf` | Acme Office Systems · `PL-10001` · `PO-1001` | Net INR 25,000 · Tax INR 4,500 · Gross INR 29,500 | `READY_FOR_POSTING` · all seven controls pass | The approved supplier, exact PO, reconciled totals, unique invoice ID, sufficient capacity, and source evidence all agree. This is a recommendation, not payment approval. |
| `02_valid_partial_invoice.pdf` | Nova Industrial Supplies · `NOV-3490` · `PO-2002` | Net INR 25,000 · Tax INR 4,500 · Gross INR 29,500 | `READY_FOR_POSTING` · `B001_PO_REMAINING` passes | PO-2002 has INR 30,000 remaining after INR 70,000 of confirmed invoices. A distinct invoice number and INR 25,000 claim are valid partial invoicing. |
| `03_duplicate_invoice.pdf` | Acme Office Systems · `inv 2048` · `PO-1001` | Net INR 12,000 · Tax INR 2,160 · Gross INR 14,160 | `BLOCKED` · `D001_DUPLICATE` fails | Normalization matches confirmed `INV-2048` for the same supplier; punctuation and capitalization cannot bypass duplicate protection. |
| `04_po_budget_exceeded.pdf` | Nova Industrial Supplies · `NOV-3500` · `PO-2002` | Net INR 35,000 · Tax INR 6,300 · Gross INR 41,300 | `BLOCKED` · `B001_PO_REMAINING` fails | The PO authorizes INR 100,000, INR 70,000 is confirmed, and only INR 30,000 remains. The new net claim is exactly INR 5,000 over budget. |
| `05_ambiguous_po.pdf` | Orchid Events India · `ORCH-500` · no PO reference | Net INR 8,000 · Tax INR 1,440 · Gross INR 9,440 | `NEEDS_REVIEW` · `P001_PO_MATCH` reviews | Two open candidate POs exist (`PO-4001`, `PO-4002`). ProofLedger does not guess; the buyer must confirm the correct PO. |
