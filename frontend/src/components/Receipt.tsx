import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronDown,
  CircleSlash2,
  FileText,
  Landmark,
  MessageSquareText,
  ScanLine,
  ShieldCheck,
  X,
} from "lucide-react";
import { motion } from "motion/react";
import { type FormEvent, useMemo, useState } from "react";
import { api, apiUrl, formatDate, formatMoney } from "../api";
import type { PolicyCheck, RunRecord } from "../types";
import { StatusBadge } from "./StatusBadge";

function CheckIcon({ check }: { check: PolicyCheck }) {
  if (check.outcome === "PASS") return <Check size={15} />;
  if (check.outcome === "FAIL") return <CircleSlash2 size={15} />;
  return <AlertTriangle size={15} />;
}

export function Receipt({ run, onRefresh }: { run: RunRecord; onRefresh: () => Promise<void> | void }) {
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [note, setNote] = useState("");
  const [savingNote, setSavingNote] = useState(false);
  const [actionError, setActionError] = useState("");
  const fields = run.extracted.fields;

  const balancePercent = useMemo(() => {
    const authorized = Number(run.money.authorized || 0);
    const committed = Number(run.money.committed || 0);
    if (!authorized) return 0;
    return Math.min((committed / authorized) * 100, 100);
  }, [run.money.authorized, run.money.committed]);

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
          <span className="eyebrow">Decision receipt · {run.id.slice(0, 8)}</span>
          <h2>{fields?.vendor_name || fields?.vendor_id || "Unmatched supplier"}</h2>
          <p>{fields?.invoice_number || "Invoice number missing"} · Processed {formatDate(run.updated_at)}</p>
        </div>
        <StatusBadge decision={run.decision} status={run.status} />
      </div>

      <div className="receipt-decision-grid">
        <div className={`decision-hero decision-${run.decision?.toLowerCase()}`}>
          <div className="decision-icon">
            {run.decision === "READY_FOR_POSTING" ? <CheckCircle2 /> : run.decision === "BLOCKED" ? <CircleSlash2 /> : <AlertTriangle />}
          </div>
          <div>
            <span className="eyebrow">Recommendation—not a payment</span>
            <h3>{run.explanation}</h3>
            <div className="next-action"><ArrowRight size={17} /><span><strong>Next action</strong>{run.next_action}</span></div>
          </div>
        </div>
        <div className="amount-card">
          <span>Invoice claims</span>
          <strong>{formatMoney(run.money.gross, run.money.currency || "INR")}</strong>
          <small>Gross · Net {formatMoney(run.money.net, run.money.currency || "INR")}</small>
        </div>
      </div>

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
          {run.document_url ? (
            <iframe title={`Source invoice ${fields?.invoice_number || run.id}`} src={apiUrl(run.document_url)} />
          ) : (
            <div className="document-placeholder"><FileText /><span>Open the full receipt to preview the source PDF.</span></div>
          )}
          <div className="extraction-chip"><ScanLine size={14} /> Extracted via {run.extraction_method === "ocr" ? "local Tesseract OCR" : "embedded PDF text"}</div>
        </div>

        <div className="evidence-panel">
          <div className="panel-heading"><span><ShieldCheck size={17} /> Evidence checks</span><span>{run.checks.filter((item) => item.outcome === "PASS").length}/{run.checks.length} passed</span></div>
          <div className="check-list">
            {run.checks.map((item) => (
              <details className={`check-row check-${item.outcome.toLowerCase()}`} key={item.rule_id}>
                <summary>
                  <span className="check-icon"><CheckIcon check={item} /></span>
                  <span className="check-copy"><strong>{item.title}</strong><small>{item.rule_id}</small></span>
                  <span className="check-outcome">{item.outcome === "PASS" ? "Passed" : item.outcome === "FAIL" ? "Failed" : "Review"}</span>
                  <ChevronDown size={15} />
                </summary>
                <p>{item.detail}</p>
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
