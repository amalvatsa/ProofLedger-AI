import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  CircleSlash2,
  Copy,
  FileText,
  Landmark,
  MessageSquareText,
  Printer,
  ScanLine,
  ShieldCheck,
  X,
} from "lucide-react";
import { motion } from "motion/react";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, apiUrl, formatDate, formatMoney } from "../api";
import type { PolicyCheck, RunRecord } from "../types";
import { StatusBadge } from "./StatusBadge";

function CheckIcon({ check }: { check: PolicyCheck }) {
  if (check.outcome === "PASS") return <Check size={15} />;
  if (check.outcome === "FAIL") return <CircleSlash2 size={15} />;
  return <AlertTriangle size={15} />;
}

function comparisonMoney(value: string | null | undefined, currency = "INR"): string {
  return value === null || value === undefined || value === "" ? "Not available" : formatMoney(value, currency);
}

const exceptionPriority = [
  "D001_DUPLICATE",
  "B001_PO_REMAINING",
  "T001_TOTAL_RECONCILIATION",
  "V001_APPROVED_VENDOR",
  "P001_PO_MATCH",
  "I001_REQUIRED_FIELDS",
  "X001_EXTRACTION_QUALITY",
];

const decisionReasonLabels: Record<string, string> = {
  D001_DUPLICATE: "Confirmed Duplicate",
  B001_PO_REMAINING: "PO Budget Exceeded",
  T001_TOTAL_RECONCILIATION: "Invoice Amounts Do Not Reconcile",
  V001_APPROVED_VENDOR: "Supplier Policy Violation",
  P001_PO_MATCH: "Purchase Order Conflict",
  I001_REQUIRED_FIELDS: "Required Information Missing",
  X001_EXTRACTION_QUALITY: "Document Evidence Is Uncertain",
};

function evidenceText(value: unknown, currency: string): string | null {
  return typeof value === "string" && value ? formatMoney(value, currency) : null;
}

function financialEvidence(check: PolicyCheck, currency: string): Array<[string, string]> {
  if (check.rule_id === "B001_PO_REMAINING") {
    return [
      ["Approved PO", evidenceText(check.evidence.authorized_net, currency)],
      ["Previously confirmed", evidenceText(check.evidence.confirmed_net, currency)],
      ["Remaining", evidenceText(check.evidence.remaining_net, currency)],
      ["Current invoice", evidenceText(check.evidence.requested_net, currency)],
      ["Excess", evidenceText(check.evidence.exceeded_by, currency)],
    ].filter((item): item is [string, string] => Boolean(item[1]));
  }
  if (check.rule_id === "T001_TOTAL_RECONCILIATION") {
    return [
      ["Net", evidenceText(check.evidence.net, currency)],
      ["Tax", evidenceText(check.evidence.tax, currency)],
      ["Gross", evidenceText(check.evidence.gross, currency)],
      ["Difference", evidenceText(check.evidence.difference, currency)],
    ].filter((item): item is [string, string] => Boolean(item[1]));
  }
  return [];
}

export function Receipt({ run, onRefresh }: { run: RunRecord; onRefresh: () => Promise<void> | void }) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [actionError, setActionError] = useState("");
  const [copied, setCopied] = useState(false);
  const [evidenceExpanded, setEvidenceExpanded] = useState(false);
  const [sourcePreviewState, setSourcePreviewState] = useState<"checking" | "available" | "missing">(run.document_url ? "checking" : "missing");
  const evidenceRef = useRef<HTMLDivElement>(null);
  const fields = run.extracted.fields;
  const vendorCheck = run.checks.find((item) => item.rule_id === "V001_APPROVED_VENDOR");
  const poCheck = run.checks.find((item) => item.rule_id === "P001_PO_MATCH");
  const totalCheck = run.checks.find((item) => item.rule_id === "T001_TOTAL_RECONCILIATION");
  const duplicateCheck = run.checks.find((item) => item.rule_id === "D001_DUPLICATE");
  const passedChecks = run.checks.filter((item) => item.outcome === "PASS").length;
  const attentionChecks = [...run.checks.filter((item) => item.outcome !== "PASS")].sort(
    (left, right) => exceptionPriority.indexOf(left.rule_id) - exceptionPriority.indexOf(right.rule_id),
  );
  const primaryCheck = attentionChecks[0];
  const decisionHeadline = run.decision === "READY_FOR_POSTING"
    ? "READY FOR POSTING"
    : `${run.decision === "BLOCKED" ? "BLOCKED" : "NEEDS REVIEW"} — ${decisionReasonLabels[primaryCheck?.rule_id] || primaryCheck?.title || "Action required"}`;
  const decisionExplanation = (run.explanation || "The saved evidence requires attention.").replace(/^BLOCKED:\s*/i, "");

  const balancePercent = useMemo(() => {
    const authorized = Number(run.money.authorized || 0);
    const committed = Number(run.money.committed || 0);
    if (!authorized) return 0;
    return Math.min((committed / authorized) * 100, 100);
  }, [run.money.authorized, run.money.committed]);

  useEffect(() => {
    if (!run.document_url) {
      setSourcePreviewState("missing");
      return;
    }

    const controller = new AbortController();
    setSourcePreviewState("checking");
    fetch(apiUrl(run.document_url), {
      headers: { Range: "bytes=0-0" },
      signal: controller.signal,
    })
      .then((response) => setSourcePreviewState(response.ok ? "available" : "missing"))
      .catch((error: unknown) => {
        if (!(error instanceof DOMException && error.name === "AbortError")) setSourcePreviewState("missing");
      });

    return () => controller.abort();
  }, [run.document_url]);

  async function confirmLedger() {
    setConfirming(true);
    setActionError("");
    try {
      await api.confirm(run.id);
      setConfirmOpen(false);
      await onRefresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Confirmation failed.");
    } finally {
      setConfirming(false);
    }
  }

  async function submitNote(event: FormEvent) {
    event.preventDefault();
    if (!note.trim()) return;
    setSavingNote(true);
    setActionError("");
    try {
      await api.addNote(run.id, note.trim());
      setNote("");
      await onRefresh();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Could not save note.");
    } finally {
      setSavingNote(false);
    }
  }

  async function copyDecisionSummary() {
    const summary = [
      "ProofLedger Decision Receipt",
      `Invoice: ${fields?.invoice_number || "Not available"}`,
      `Supplier: ${fields?.vendor_name || fields?.vendor_id || "Not available"}`,
      `Invoice date: ${fields?.issue_date || "Not available"}`,
      `Gross amount: ${formatMoney(run.money.gross, run.money.currency || "INR")}`,
      `Purchase order: ${run.matched_po_number || fields?.po_reference || "Not available"}`,
      `Recommendation: ${run.decision?.replaceAll("_", " ") || "Not available"}`,
      `Evidence checks: ${passedChecks}/${run.checks.length} passed`,
      `Reason: ${run.explanation || "Not available"}`,
      `Next action: ${run.next_action || "Not available"}`,
      `Receipt ID: ${run.id}`,
    ].join("\n");
    try {
      await navigator.clipboard.writeText(summary);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setActionError("The decision summary could not be copied in this browser.");
    }
  }

  function toggleEvidence() {
    const details = Array.from(evidenceRef.current?.querySelectorAll("details") || []);
    const expand = details.some((item) => !item.open);
    details.forEach((item) => { item.open = expand; });
    setEvidenceExpanded(expand);
  }

  if (run.status === "FAILED") {
    return (
      <section className="failure-card">
        <CircleSlash2 size={28} />
        <div>
          <span className="eyebrow">Stopped safely</span>
          <h2>We could not verify this PDF</h2>
          <p>{run.explanation}</p>
          <strong>{run.next_action}</strong>
        </div>
      </section>
    );
  }

  return (
    <motion.section className="receipt" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.24 }}>
      <div className="receipt-header">
        <div>
          <span className="eyebrow"><ClipboardCheck size={14} /> Decision receipt · {run.id.slice(0, 8)}</span>
          <h2>{fields?.vendor_name || fields?.vendor_id || "Unmatched supplier"}</h2>
          <p>{fields?.invoice_number || "Invoice number missing"} · Processed {formatDate(run.updated_at)}</p>
        </div>
        <div className="receipt-header-actions">
          <StatusBadge decision={run.decision} status={run.status} />
          <div className="receipt-utility-actions" aria-label="Decision receipt actions">
            <button type="button" className="utility-button" onClick={() => void copyDecisionSummary()}><Copy size={15} /> {copied ? "Copied" : "Copy summary"}</button>
            <button type="button" className="utility-button" onClick={() => window.print()}><Printer size={15} /> Print</button>
          </div>
        </div>
      </div>

      <div className="receipt-decision-grid">
        <div className={`decision-hero decision-${run.decision?.toLowerCase()}`}>
          <div className="decision-icon">
            {run.decision === "READY_FOR_POSTING" ? <CheckCircle2 /> : run.decision === "BLOCKED" ? <CircleSlash2 /> : <AlertTriangle />}
          </div>
          <div>
            <span className="eyebrow">Recommendation—not a payment</span>
            <h3>{decisionHeadline}</h3>
            <p className="decision-reason"><strong>Reason:</strong> {decisionExplanation}</p>
          </div>
        </div>
        <div className="amount-card">
          <span>Supplier invoice total</span>
          <strong>{formatMoney(run.money.gross, run.money.currency || "INR")}</strong>
          <small>Net {formatMoney(run.money.net, run.money.currency || "INR")} · Tax {formatMoney(run.money.tax, run.money.currency || "INR")}</small>
        </div>
      </div>

      <div className={`next-action next-action-${run.decision?.toLowerCase()}`}>
        <span className="next-action-icon"><ArrowRight size={18} /></span>
        <span><strong>Recommended next action</strong>{run.next_action || "Review the saved evidence before continuing."}</span>
      </div>

      {attentionChecks.length > 0 && (
        <section className="exception-summary" aria-labelledby={`exceptions-${run.id}`}>
          <div className="exception-summary-heading">
            <div><span className="eyebrow">Complete exception summary</span><h3 id={`exceptions-${run.id}`}>All issues requiring attention</h3></div>
            <strong>{attentionChecks.length} control{attentionChecks.length === 1 ? "" : "s"}</strong>
          </div>
          <div className="exception-summary-list">
            {attentionChecks.map((item, index) => {
              const figures = financialEvidence(item, run.money.currency || "INR");
              return (
                <article className={`exception-summary-item exception-${item.outcome.toLowerCase()}`} key={item.rule_id}>
                  <div className="exception-rank">{index === 0 ? "Primary" : "Also"}</div>
                  <div className="exception-summary-copy">
                    <div><strong>{item.title}</strong><span>{item.rule_id} · {item.outcome === "FAIL" ? "Confirmed violation" : "Human review"}</span></div>
                    <p>{item.detail}</p>
                    {figures.length > 0 && <dl>{figures.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
                    {item.resolution && <small><b>Next:</b> {item.resolution}</small>}
                  </div>
                </article>
              );
            })}
          </div>
        </section>
      )}

      <section className="reconciliation-section" aria-labelledby={`reconciliation-${run.id}`}>
        <div className="section-heading-row reconciliation-heading">
          <div><span className="eyebrow">Claim-to-record reconciliation</span><h3 id={`reconciliation-${run.id}`}>What the supplier submitted vs. what the company authorized</h3></div>
          <span className="reconciliation-summary"><ShieldCheck size={15} /> {passedChecks} of {run.checks.length} controls passed</span>
        </div>
        <div className="reconciliation-grid">
          <article className="comparison-card supplier-claim-card">
            <div className="comparison-card-heading"><span className="comparison-icon"><FileText size={19} /></span><div><span>Supplier evidence</span><strong>Invoice claim</strong></div></div>
            <dl className="comparison-list">
              <div><dt>Supplier</dt><dd>{fields?.vendor_name || fields?.vendor_id || "Not available"}</dd></div>
              <div><dt>Invoice number</dt><dd>{fields?.invoice_number || "Not available"}</dd></div>
              <div><dt>Invoice date</dt><dd>{fields?.issue_date || "Not available"}</dd></div>
              <div><dt>Gross amount</dt><dd>{comparisonMoney(fields?.gross_total, fields?.currency || "INR")}</dd></div>
              <div><dt>Tax amount</dt><dd>{comparisonMoney(fields?.tax_amount, fields?.currency || "INR")}</dd></div>
              <div><dt>Claimed PO</dt><dd>{fields?.po_reference || "Not available"}</dd></div>
            </dl>
          </article>

          <article className="comparison-card company-record-card">
            <div className="comparison-card-heading"><span className="comparison-icon"><Landmark size={19} /></span><div><span>Authoritative evidence</span><strong>Company records</strong></div></div>
            <dl className="comparison-list">
              <div><dt>Approved supplier</dt><dd className={vendorCheck?.outcome === "PASS" ? "verified-value" : "attention-value"}>{vendorCheck?.outcome === "PASS" ? fields?.vendor_name || fields?.vendor_id || "Not available" : "Not available"}</dd></div>
              <div><dt>Matched PO</dt><dd className={poCheck?.outcome === "PASS" ? "verified-value" : "attention-value"}>{run.matched_po_number || "Not available"}</dd></div>
              <div><dt>PO authorized net</dt><dd>{comparisonMoney(run.money.authorized, run.money.currency || "INR")}</dd></div>
              <div><dt>Previously committed</dt><dd>{comparisonMoney(run.money.committed, run.money.currency || "INR")}</dd></div>
              <div><dt>Remaining before invoice</dt><dd>{comparisonMoney(run.money.remaining, run.money.currency || "INR")}</dd></div>
              <div><dt>Validation</dt><dd className={duplicateCheck?.outcome === "FAIL" || totalCheck?.outcome !== "PASS" ? "attention-value" : "verified-value"}>{duplicateCheck?.outcome === "FAIL" ? "Confirmed duplicate found" : totalCheck?.outcome === "PASS" ? "Totals reconciled" : "Requires review"}</dd></div>
            </dl>
          </article>
        </div>
      </section>

      {run.matched_po_number && (
        <div className="po-balance-card">
          <div className="po-balance-heading">
            <span><Landmark size={17} /> {run.matched_po_number} capacity</span>
            <strong>{formatMoney(run.money.remaining)} remaining</strong>
          </div>
          <div className="balance-track" aria-label={`${balancePercent.toFixed(0)} percent already committed`}>
            <motion.div className="balance-fill" initial={{ width: 0 }} animate={{ width: `${balancePercent}%` }} transition={{ duration: 0.45 }} />
          </div>
          <div className="balance-labels">
            <span>Confirmed {formatMoney(run.money.committed)}</span>
            <span>Authorized {formatMoney(run.money.authorized)}</span>
          </div>
          {Number(run.money.exceeded || 0) > 0 && <div className="overage-callout">Requested net exceeds remaining capacity by {formatMoney(run.money.exceeded)}.</div>}
        </div>
      )}

      {run.extracted.candidate_pos && run.extracted.candidate_pos.length > 0 && (
        <div className="candidate-card">
          <Landmark size={18} />
          <div><strong>Possible purchase orders—not auto-selected</strong><p>{run.extracted.candidate_pos.join(" · ")}</p></div>
        </div>
      )}

      <div className="receipt-columns">
        <div className="document-panel">
          <div className="panel-heading"><span><FileText size={17} /> Source invoice</span><span>{run.extracted.page_count || 1} page</span></div>
          {run.document_url && sourcePreviewState === "available" ? (
            <iframe title={`Source invoice ${fields?.invoice_number || run.id}`} src={apiUrl(run.document_url)} />
          ) : (
            <div className="document-placeholder">
              <FileText />
              <strong>{sourcePreviewState === "checking" ? "Checking source PDF…" : "Source PDF unavailable on this machine"}</strong>
              <span>{sourcePreviewState === "checking" ? "The preview will appear when the file is ready." : "The saved receipt and extracted evidence remain available for review."}</span>
            </div>
          )}
          <div className="extraction-chip"><ScanLine size={14} /> Extracted via {run.extraction_method === "ocr" ? "local text recognition" : run.extraction_method === "hybrid" ? "layout-aware source verification" : "embedded PDF text"}</div>
        </div>

        <div className="evidence-panel">
          <div className="panel-heading"><span><ShieldCheck size={17} /> Evidence checks</span><button type="button" className="panel-action" onClick={toggleEvidence}>{evidenceExpanded ? "Collapse all" : "Expand all"}</button></div>
          <div className="check-list" ref={evidenceRef}>
            {run.checks.map((item) => (
              <details className={`check-row check-${item.outcome.toLowerCase()}`} key={item.rule_id}>
                <summary>
                  <span className="check-icon"><CheckIcon check={item} /></span>
                  <span className="check-copy"><strong>{item.title}</strong><small>{item.rule_id}</small></span>
                  <span className="check-outcome">{item.outcome === "PASS" ? "Passed" : item.outcome === "FAIL" ? "Failed" : "Review"}</span>
                  <ChevronDown size={15} />
                </summary>
                <p>{item.detail}{item.resolution && <><br /><strong>Suggested resolution:</strong> {item.resolution}</>}</p>
              </details>
            ))}
          </div>
        </div>
      </div>

      <div className="claims-card">
        <div className="panel-heading"><span>Claims read from the invoice</span><span>Source evidence, not authority</span></div>
        <div className="claims-grid">
          {[
            ["Invoice number", fields?.invoice_number],
            ["Issue date", fields?.issue_date],
            ["Vendor ID", fields?.vendor_id],
            ["PO reference", fields?.po_reference],
            ["Currency", fields?.currency],
            ["Tax treatment", fields?.tax_treatment],
            ["Net", formatMoney(fields?.net_amount, fields?.currency || "INR")],
            ["Tax", formatMoney(fields?.tax_amount, fields?.currency || "INR")],
            ["Gross", formatMoney(fields?.gross_total, fields?.currency || "INR")],
          ].map(([label, value]) => (
            <div key={label as string}><span>{label}</span><strong>{value || "Not found"}</strong></div>
          ))}
        </div>
      </div>

      {actionError && <div className="inline-error" role="alert">{actionError}</div>}

      <div className="receipt-actions">
        <Link className="secondary-button print-hidden" to="/history">Back to History</Link>
        {run.decision === "READY_FOR_POSTING" && (
          <button className="primary-button" onClick={() => setConfirmOpen(true)} disabled={Boolean(run.confirmed_at)}>
            <CheckCircle2 size={17} /> {run.confirmed_at ? "Confirmed in demo ledger" : "Confirm as processed (demo ledger)"}
          </button>
        )}
        {run.decision !== "READY_FOR_POSTING" && (
          <form className="note-form" onSubmit={submitNote}>
            <MessageSquareText size={17} />
            <label className="sr-only" htmlFor={`note-${run.id}`}>Reviewer note</label>
            <input id={`note-${run.id}`} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Add a reviewer note" maxLength={1200} />
            <button className="secondary-button" disabled={savingNote || !note.trim()}>{savingNote ? "Saving…" : "Save note"}</button>
          </form>
        )}
      </div>

      {run.notes.length > 0 && (
        <div className="notes-list">
          <strong>Reviewer notes</strong>
          {run.notes.map((item) => <div key={item.id}><span>{item.note}</span><small>{formatDate(item.created_at)}</small></div>)}
        </div>
      )}

      {confirmOpen && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => setConfirmOpen(false)}>
          <motion.div className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="confirm-title" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} onMouseDown={(event) => event.stopPropagation()}>
            <button className="icon-button modal-close" onClick={() => setConfirmOpen(false)} aria-label="Close confirmation"><X size={18} /></button>
            <div className="modal-icon"><CheckCircle2 /></div>
            <span className="eyebrow">Synthetic ledger action</span>
            <h3 id="confirm-title">Confirm this invoice as processed?</h3>
            <p>This will add one idempotent confirmation to the demo SQLite ledger and reduce the remaining PO balance. It does not post to an ERP or execute payment.</p>
            <div className="modal-summary"><span>{fields?.invoice_number}</span><strong>{formatMoney(run.money.net)} net</strong></div>
            <div className="modal-actions">
              <button className="ghost-button" onClick={() => setConfirmOpen(false)}>Cancel</button>
              <button className="primary-button" onClick={confirmLedger} disabled={confirming}>{confirming ? "Confirming…" : "Confirm demo ledger"}</button>
            </div>
          </motion.div>
        </div>
      )}
    </motion.section>
  );
}
