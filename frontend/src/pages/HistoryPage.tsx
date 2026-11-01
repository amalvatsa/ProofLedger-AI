import { ArrowRight, Database, History, Search, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, formatDate, formatMoney } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import type { LedgerRow, RunRecord } from "../types";

export function HistoryPage() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [ledger, setLedger] = useState<LedgerRow[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [ledgerOpen, setLedgerOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestedDecision = searchParams.get("decision");
  const decisionFilter = requestedDecision === "READY_FOR_POSTING" || requestedDecision === "NEEDS_REVIEW" || requestedDecision === "BLOCKED" ? requestedDecision : null;

  function changeDecisionFilter(decision: string | null) {
    setSearchParams(decision ? { decision } : {});
  }

  useEffect(() => {
    Promise.all([api.getRuns("limit=200"), api.getLedger()])
      .then(([runData, ledgerData]) => { setRuns(runData); setLedger(ledgerData); })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load history."))
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(() => {
    const token = query.trim().toLowerCase();
    return runs.filter((run) => {
      const matchesDecision = !decisionFilter || run.decision === decisionFilter;
      const matchesSearch = `${run.extracted.fields?.vendor_name} ${run.extracted.fields?.invoice_number} ${run.original_filename} ${run.decision}`.toLowerCase().includes(token);
      return matchesDecision && matchesSearch;
    });
  }, [runs, query, decisionFilter]);

  return (
    <div className="page-wrap">
      <div className="page-heading">
        <div><span className="eyebrow">Auditable recommendations</span><h1>Run history</h1><p>Every completed attempt, event, check, note, and evidence receipt remains available after refresh.</p></div>
        <button className="secondary-button" onClick={() => setLedgerOpen(true)}><Database size={17} /> View PO ledger</button>
      </div>

      <div className="toolbar-card history-toolbar">
        <label className="search-field wide"><Search size={17} /><span className="sr-only">Search history</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search supplier, invoice ID, filename, or status" /></label>
        <div className="segmented-control history-filters" aria-label="Filter run history">
          {[
            [null, "All"],
            ["READY_FOR_POSTING", "Ready"],
            ["NEEDS_REVIEW", "Needs review"],
            ["BLOCKED", "Blocked"],
          ].map(([value, label]) => (
            <button key={label} className={decisionFilter === value ? "active" : ""} onClick={() => changeDecisionFilter(value)}>{label}</button>
          ))}
        </div>
        <span className="result-count">{visible.length} run{visible.length === 1 ? "" : "s"}</span>
      </div>
      {error && <div className="inline-error" role="alert">{error}</div>}

      <section className="table-card">
        <div className="table-header history-table-grid"><span>Run</span><span>Supplier / invoice</span><span>Amount</span><span>Processed</span><span>Decision</span><span /></div>
        {loading ? <div className="loading-row">Loading persisted history…</div> : visible.length === 0 ? (
          <div className="empty-state"><div className="empty-icon"><History /></div><h2>No run history yet</h2><p>Process a real or sample PDF to create the first persistent decision receipt.</p><Link className="primary-button" to="/process">Process invoice</Link></div>
        ) : visible.map((run) => {
          const fields = run.extracted.fields;
          return (
            <Link to={`/runs/${run.id}`} className="table-row history-table-grid" key={run.id}>
              <span className="run-id">{run.id.slice(0, 8)}</span>
              <div className="cell-primary"><div className="vendor-avatar">{(fields?.vendor_name || "?")[0]}</div><span><strong>{fields?.vendor_name || run.original_filename}</strong><small>{fields?.invoice_number || "Unidentified invoice"}</small></span></div>
              <strong>{formatMoney(run.money.gross, run.money.currency || "INR")}</strong>
              <span>{formatDate(run.created_at)}</span>
              <StatusBadge decision={run.decision} status={run.status} compact />
              <span className="inspect-link">Receipt <ArrowRight size={14} /></span>
            </Link>
          );
        })}
      </section>

      <AnimatePresence>
        {ledgerOpen && (
          <>
            <motion.button className="drawer-scrim" aria-label="Close PO ledger" onClick={() => setLedgerOpen(false)} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
            <motion.aside className="ledger-drawer" initial={{ x: "100%" }} animate={{ x: 0 }} exit={{ x: "100%" }} transition={{ duration: 0.22 }} aria-label="Read-only purchase order ledger">
              <div className="drawer-heading"><div><span className="eyebrow">Authoritative source</span><h2>PO ledger</h2><p>Confirmed commitments only. Recommendations do not consume budget.</p></div><button className="icon-button" onClick={() => setLedgerOpen(false)} aria-label="Close PO ledger"><X size={19} /></button></div>
              <div className="ledger-list">
                {ledger.map((row) => {
                  const percent = Math.min((Number(row.confirmed_net) / Number(row.authorized_net)) * 100, 100);
                  return (
                    <article className="ledger-card" key={row.po_number}>
                      <div><span className="po-number">{row.po_number}</span><span className="open-chip">{row.status}</span></div>
                      <h3>{row.vendor_name}</h3><p>{row.description}</p>
                      <div className="balance-track"><div className="balance-fill" style={{ width: `${percent}%` }} /></div>
                      <div className="ledger-numbers"><span><small>Confirmed</small><strong>{formatMoney(row.confirmed_net)}</strong></span><span><small>Remaining</small><strong>{formatMoney(row.remaining_net)}</strong></span><span><small>Authorized</small><strong>{formatMoney(row.authorized_net)}</strong></span></div>
                    </article>
                  );
                })}
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </div>
  );
}
