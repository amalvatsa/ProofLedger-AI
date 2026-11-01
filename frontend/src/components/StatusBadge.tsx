import { AlertTriangle, CheckCircle2, CircleSlash2, LoaderCircle } from "lucide-react";
import type { Decision, RunStatus } from "../types";

const labels: Record<Decision, string> = {
  READY_FOR_POSTING: "Ready for posting",
  NEEDS_REVIEW: "Needs review",
  BLOCKED: "Blocked",
};

export function StatusBadge({ decision, status, compact = false }: { decision: Decision | null; status?: RunStatus; compact?: boolean }) {
  if (!decision) {
    const failed = status === "FAILED";
    return (
      <span className={`status-badge ${failed ? "status-failed" : "status-processing"} ${compact ? "compact" : ""}`}>
        {failed ? <CircleSlash2 size={14} /> : <LoaderCircle className="spin" size={14} />}
        {failed ? "Failed safely" : "Processing"}
      </span>
    );
  }
  const Icon = decision === "READY_FOR_POSTING" ? CheckCircle2 : decision === "NEEDS_REVIEW" ? AlertTriangle : CircleSlash2;
  return (
    <span className={`status-badge status-${decision.toLowerCase().replaceAll("_", "-")} ${compact ? "compact" : ""}`}>
      <Icon size={compact ? 13 : 15} />
      {labels[decision]}
    </span>
  );
}
