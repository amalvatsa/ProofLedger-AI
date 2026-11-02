import { AlertCircle, Check, Circle, FileCheck2, FileSearch, Landmark, ListChecks, LoaderCircle, Save, ScanText, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import type { RunRecord } from "../types";

const stages = [
  { key: "RECEIVED", label: "Invoice received", icon: FileSearch },
  { key: "DOCUMENT_READING", label: "Document reading", icon: ScanText },
  { key: "INTERPRETED", label: "Details organized", icon: ListChecks },
  { key: "EVIDENCE_VALIDATED", label: "Evidence checked", icon: FileCheck2 },
  { key: "VENDOR_VALIDATED", label: "Vendor validated", icon: ShieldCheck },
  { key: "PO_MATCHED", label: "Purchase order matched", icon: Landmark },
  { key: "BUSINESS_RULES_CHECKED", label: "Business rules checked", icon: ListChecks },
  { key: "DECISION_SAVED", label: "Decision saved", icon: Save },
];

export function Timeline({ run }: { run: RunRecord }) {
  const eventsByStage = new Map(run.events.map((event) => [event.stage, event]));

  return (
    <section className="timeline-card" aria-live="polite">
      <div className="section-heading-row">
        <div>
          <span className="eyebrow">Verified live journey</span>
          <h2>Processing timeline</h2>
        </div>
        <span className="truth-label">Backend events only</span>
      </div>
      <ol className="timeline-list">
        {stages.map(({ key, label, icon: StageIcon }, index) => {
          const event = eventsByStage.get(key);
          const isActive = event?.outcome === "PROCESSING";
          const isFailed = event?.outcome === "FAILED";
          const attention = event?.outcome === "REVIEW" || event?.outcome === "ATTENTION" || event?.outcome === "FAIL";
          return (
            <motion.li
              key={key}
              initial={event ? { opacity: 0, y: 5 } : false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.2, delay: event ? Math.min(index * 0.025, 0.12) : 0 }}
              className={`timeline-item ${event && !isActive ? "complete" : "pending"} ${isActive ? "active" : ""} ${attention ? "attention" : ""} ${isFailed ? "failed" : ""}`}
            >
              <div className="timeline-node">
                {isActive ? <LoaderCircle className="spin" size={15} /> : event ? (isFailed || attention ? <AlertCircle size={15} /> : <Check size={15} />) : <Circle size={13} />}
              </div>
              <div className="timeline-copy">
                <div className="timeline-title-row">
                  <span className="timeline-title"><StageIcon size={15} /> {label}</span>
                  {event && <span className="timeline-duration">{event.duration_ms} ms</span>}
                </div>
                <p>{event?.explanation || "Waiting for the previous step."}</p>
              </div>
            </motion.li>
          );
        })}
      </ol>
    </section>
  );
}
