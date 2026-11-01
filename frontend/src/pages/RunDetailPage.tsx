import { ArrowLeft, LoaderCircle } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Receipt } from "../components/Receipt";
import { Timeline } from "../components/Timeline";
import type { RunRecord } from "../types";

export function RunDetailPage() {
  const { runId } = useParams();
  const [run, setRun] = useState<RunRecord | null>(null);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    if (!runId) return;
    try {
      setRun(await api.getRun(runId));
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "This run could not be loaded.");
    }
  }, [runId]);

  useEffect(() => { void refresh(); }, [refresh]);

  return (
    <div className="page-wrap">
      <div className="detail-back-row"><Link to="/history" className="text-link"><ArrowLeft size={15} /> Back to history</Link></div>
      {error ? <div className="inline-error" role="alert">{error}</div> : !run ? <div className="loading-row page-loading"><LoaderCircle className="spin" /> Loading decision receipt…</div> : (
        <div className="result-stack"><Timeline run={run} />{run.status !== "PROCESSING" && <Receipt run={run} onRefresh={refresh} />}</div>
      )}
    </div>
  );
}
