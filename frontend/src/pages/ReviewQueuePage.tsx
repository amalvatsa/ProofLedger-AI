import { ArrowRight, Inbox, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, formatDate, formatMoney } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import type { Decision, RunRecord } from "../types";

type Filter = "ALL" | "NEEDS_REVIEW" | "BLOCKED";

export function ReviewQueuePage() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requestedFilter = searchParams.get("filter");
  const filter: Filter = requestedFilter === "NEEDS_REVIEW" || requestedFilter === "BLOCKED" ? requestedFilter : "ALL";

  function changeFilter(nextFilter: Filter) {
    setSearchParams(nextFilter === "ALL" ? {} : { filter: nextFilter });
  }

  useEffect(() => {
    api.getRuns("decision=NEEDS_REVIEW,BLOCKED&limit=100")
      .then(setRuns)
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load the review queue."))
      .finally(() => setLoading(false));
  }, []);

  const visible = useMemo(() => runs.filter((run) => {
    const fields = run.extracted.fields;
    const matchesFilter = filter === "ALL" || run.decision === filter;
    const haystack = `${fields?.vendor_name} ${fields?.invoice_number} ${run.original_filename}`.toLowerCase();
    return matchesFilter && haystack.includes(query.trim().toLowerCase());
  }), [runs, filter, query]);

  function reason(run: RunRecord): { code: string; title: string } {
    const control = run.checks.find((item) => item.outcome !== "PASS");
    return {
      code: control?.rule_id || "SAFE_FAILURE",
      title: control?.title || "Processing requires attention",
    };
  }

  return (
    <div className="page-wrap">
      <div className="page-heading">
        <div><span className="eyebrow">Exception workspace</span><h1>Review queue</h1><p>Understand why an invoice needs attention, inspect its evidence, and record the next review step.</p></div>
        <div className="queue-count"><strong>{runs.length}</strong><span>open exceptions</span></div>
      </div>

      <div className="toolbar-card">
        <div className="segmented-control" aria-label="Filter review queue">
          {(["ALL", "NEEDS_REVIEW", "BLOCKED"] as Filter[]).map((item) => (
            <button key={item} className={filter === item ? "active" : ""} onClick={() => changeFilter(item)}>
              {item === "ALL" ? "All" : item === "NEEDS_REVIEW" ? "Needs review" : "Blocked"}
            </button>
          ))}
        </div>
        <label className="search-field"><Search size={17} /><span className="sr-only">Search review queue</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search supplier or invoice" /></label>
      </div>

      {error && <div className="inline-error" role="alert">{error}</div>}
      <section className="table-card">
        <div className="table-header queue-table-grid"><span>Supplier / invoice</span><span>Amount</span><span>Reason</span><span>Received</span><span>Status</span><span /></div>
        {loading ? <div className="loading-row">Loading persisted exceptions…</div> : visible.length === 0 ? (
          <div className="empty-state"><div className="empty-icon"><Inbox /></div><h2>No exceptions match</h2><p>Try another filter, or process an exception sample to populate the queue.</p><Link className="secondary-button" to="/process">Process a sample</Link></div>
        ) : visible.map((run) => {
          const fields = run.extracted.fields;
          return (
            <Link to={`/runs/${run.id}`} className="table-row queue-table-grid" key={run.id}>
              <div className="cell-primary"><div className="vendor-avatar">{(fields?.vendor_name || "?")[0]}</div><span><strong>{fields?.vendor_name || "Unmatched supplier"}</strong><small>{fields?.invoice_number || "Invoice number missing"}</small></span></div>
              <strong>{formatMoney(run.money.gross, run.money.currency || "INR")}</strong>
              <span className="reason-cell"><strong>{reason(run).title}</strong><small>{reason(run).code}</small></span>
              <span>{formatDate(run.created_at, false)}</span>
              <StatusBadge decision={run.decision as Decision} status={run.status} compact />
              <span className="inspect-link">Inspect <ArrowRight size={14} /></span>
            </Link>
          );
        })}
      </section>
    </div>
  );
}
