import { AlertTriangle, ArrowRight, CheckCircle2, CircleSlash2, FileCheck2, Inbox, LoaderCircle, ShieldCheck, Sparkles } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, formatDate, formatMoney } from "../api";
import { StatusBadge } from "../components/StatusBadge";
import type { RunRecord, Summary } from "../types";

const defaultSummary: Summary = { processed: 0, ready: 0, needs_review: 0, blocked: 0 };

export function OverviewPage() {
  const [summary, setSummary] = useState(defaultSummary);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([api.getSummary(), api.getRuns("limit=6")])
      .then(([summaryData, runData]) => {
        setSummary(summaryData);
        setRuns(runData);
      })
      .catch((caught) => setError(caught instanceof Error ? caught.message : "Could not load the command center."))
      .finally(() => setLoading(false));
  }, []);

  const cards = [
    { label: "Processed", value: summary.processed, icon: FileCheck2, tone: "navy", detail: "Completed decisions", to: "/history" },
    { label: "Ready", value: summary.ready, icon: CheckCircle2, tone: "teal", detail: "All controls passed", to: "/history?decision=READY_FOR_POSTING" },
    { label: "Needs review", value: summary.needs_review, icon: AlertTriangle, tone: "amber", detail: "Evidence needs attention", to: "/review?filter=NEEDS_REVIEW" },
    { label: "Blocked", value: summary.blocked, icon: CircleSlash2, tone: "coral", detail: "Policy violations", to: "/review?filter=BLOCKED" },
  ];

  return (
    <div className="page-wrap">
      <section className="overview-hero">
        <div className="overview-hero-copy">
          <span className="eyebrow"><Sparkles size={14} /> Accounts payable control center</span>
          <h1>Every invoice gets a decision. Every decision has proof.</h1>
          <p>From invoice PDF to evidence-backed financial decision.</p>
          <Link to="/process" className="primary-button hero-cta">Process an Invoice <ArrowRight size={17} /></Link>
        </div>
        <div className="hero-proof-card">
          <div className="proof-orbit"><ShieldCheck size={25} /></div>
          <div>
            <span>Financial control model</span>
            <strong>Claims are checked against company records before a recommendation is saved.</strong>
          </div>
          <ul>
            <li><CheckCircle2 size={15} /> Vendor and PO authority</li>
            <li><CheckCircle2 size={15} /> Duplicate and balance controls</li>
            <li><CheckCircle2 size={15} /> Transparent evidence trail</li>
          </ul>
          <small>Recommendations only · No payment execution</small>
        </div>
      </section>

      {error && <div className="inline-error" role="alert">{error}</div>}

      <section className="stat-grid" aria-label="Run summary">
        {cards.map((card, index) => (
          <motion.div className="stat-card-motion" key={card.label} initial={{ opacity: 0, y: 7 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, delay: index * 0.035 }}>
            <Link className={`stat-card stat-card-link tone-${card.tone}`} to={card.to} aria-label={`View ${card.label.toLowerCase()} invoices`}>
              <div className="stat-icon"><card.icon size={19} /></div>
              <div className="stat-copy"><span>{card.label}</span><strong>{loading ? "—" : card.value}</strong><small>{card.detail}</small></div>
              <ArrowRight className="stat-arrow" size={16} />
            </Link>
          </motion.div>
        ))}
      </section>

      <section className="overview-grid">
        <div className="content-card recent-card">
          <div className="section-heading-row">
            <div><span className="eyebrow">Persistent run history</span><h2>Recent invoices</h2></div>
            <Link to="/history" className="text-link">View all <ArrowRight size={15} /></Link>
          </div>
          {loading ? (
            <div className="loading-row"><LoaderCircle className="spin" /> Loading genuine runs…</div>
          ) : runs.length === 0 ? (
            <div className="empty-inline"><Inbox size={25} /><div><strong>No invoices processed yet</strong><span>Your first evidence receipt will appear here.</span></div><Link to="/process">Process the first invoice</Link></div>
          ) : (
            <div className="run-list">
              {runs.map((run) => {
                const fields = run.extracted.fields;
                return (
                  <Link to={`/runs/${run.id}`} className="run-row" key={run.id}>
                    <div className="vendor-avatar">{(fields?.vendor_name || "?").slice(0, 1)}</div>
                    <div className="run-main"><strong>{fields?.vendor_name || run.original_filename}</strong><span>{fields?.invoice_number || "Invoice ID unavailable"} · {formatDate(run.created_at)}</span></div>
                    <div className="run-amount">{formatMoney(run.money.gross, run.money.currency || "INR")}</div>
                    <StatusBadge decision={run.decision} status={run.status} compact />
                    <ArrowRight size={15} className="row-arrow" />
                  </Link>
                );
              })}
            </div>
          )}
        </div>

      </section>
    </div>
  );
}
