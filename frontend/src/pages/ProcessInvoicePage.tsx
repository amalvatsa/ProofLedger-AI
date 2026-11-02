import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, CopyCheck, FileSearch, FileText, LoaderCircle, ScanLine, UploadCloud, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type DragEvent, useEffect, useRef, useState } from "react";
import { api, apiUrl } from "../api";
import { Receipt } from "../components/Receipt";
import { Timeline } from "../components/Timeline";
import type { DemoSample, RunRecord } from "../types";

const processingStages: Record<string, { title: string; progress: number }> = {
  RECEIVED: { title: "Preparing the document", progress: 12 },
  DOCUMENT_READING: { title: "Reading and understanding the document", progress: 30 },
  EXTRACTED: { title: "Organizing the invoice details", progress: 44 },
  INTERPRETED: { title: "Checking values against their source", progress: 58 },
  EVIDENCE_VALIDATED: { title: "Checking supplier records", progress: 70 },
  VENDOR_VALIDATED: { title: "Matching the purchase order", progress: 80 },
  PO_MATCHED: { title: "Running financial controls", progress: 90 },
  BUSINESS_RULES_CHECKED: { title: "Preparing the decision receipt", progress: 96 },
};

function processingPresentation(run: RunRecord) {
  const active = [...run.events].reverse().find((event) => event.outcome === "PROCESSING");
  const latest = active || run.events.at(-1);
  const presentation = processingStages[latest?.stage || "RECEIVED"] || processingStages.RECEIVED;
  return {
    ...presentation,
    detail: latest?.explanation || "The document has been accepted and is waiting to be read.",
  };
}

export function ProcessInvoicePage() {
  const [samples, setSamples] = useState<DemoSample[]>([]);
  const [processingSample, setProcessingSample] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getSamples().then(setSamples).catch(() => setSamples([]));
  }, []);

  useEffect(() => {
    if (!run || run.status !== "PROCESSING") return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getRun(run.id);
        setRun(next);
        if (next.status !== "PROCESSING") window.clearInterval(timer);
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "Could not refresh the run.");
        window.clearInterval(timer);
      }
    }, 600);
    return () => window.clearInterval(timer);
  }, [run?.id, run?.status]);

  function acceptFile(file: File) {
    setError("");
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf")) {
      setError("Choose a PDF invoice. Other file types are not accepted.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("This PDF is larger than the 10 MB demo limit.");
      return;
    }
    setSelectedFile(file);
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) acceptFile(file);
  }

  async function upload(file: File, source: string) {
    setUploading(true);
    setError("");
    setRun(null);
    try {
      const created = await api.upload(file, source);
      const detail = await api.getRun(created.run_id);
      setRun(detail);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The invoice could not be uploaded.");
    } finally {
      setUploading(false);
    }
  }

  async function processSample(sampleName: string) {
    if (!sampleName || uploading) return;
    setProcessingSample(sampleName);
    setUploading(true);
    setError("");
    try {
      const response = await fetch(apiUrl(`/api/demo-samples/${sampleName}`));
      if (!response.ok) throw new Error("The selected sample could not be loaded.");
      const blob = await response.blob();
      const file = new File([blob], sampleName, { type: "application/pdf" });
      setSelectedFile(file);
      await upload(file, `demo-picker:${sampleName}`);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The sample could not be processed.");
      setUploading(false);
    } finally {
      setProcessingSample("");
    }
  }

  async function refreshRun() {
    if (run) setRun(await api.getRun(run.id));
  }

  function reset() {
    setRun(null);
    setSelectedFile(null);
    setError("");
    if (inputRef.current) inputRef.current.value = "";
  }

  const scenarioPresentation: Record<string, { title: string; lesson: string; icon: typeof FileText; tone: string }> = {
    "happy_path.pdf": { title: "Clean invoice", lesson: "See every control pass with enough PO capacity.", icon: CheckCircle2, tone: "success" },
    "duplicate_invoice.pdf": { title: "Duplicate invoice", lesson: "Catch a formatting variation of a confirmed invoice.", icon: CopyCheck, tone: "blocked" },
    "split_po_overspend.pdf": { title: "PO budget exceeded", lesson: "See cumulative commitments expose an exact overage.", icon: AlertTriangle, tone: "warning" },
    "scanned_inclusive_tax.pdf": { title: "Scanned invoice", lesson: "Watch local OCR read an image-only document.", icon: ScanLine, tone: "blue" },
    "ambiguous_po.pdf": { title: "Ambiguous PO", lesson: "See the system surface candidates without guessing.", icon: FileSearch, tone: "warning" },
    "split_po_within_balance.pdf": { title: "Split PO within balance", lesson: "Verify a partial claim against remaining capacity.", icon: CheckCircle2, tone: "success" },
  };
  const liveProgress = run?.status === "PROCESSING" ? processingPresentation(run) : null;

  return (
    <div className="page-wrap process-page">
      <div className="page-heading process-heading">
        <div>
          <span className="eyebrow">PDF to evidence-backed decision</span>
          <h1>{run ? "Decision receipt" : "Process an invoice"}</h1>
          <p>{run ? "Trace the recorded workflow, compare the supplier claim with company records, and understand the saved recommendation." : "Upload a supplier PDF or run a prepared scenario through the same real verification workflow."}</p>
        </div>
        {run && <button className="secondary-button" onClick={reset}><ArrowLeft size={16} /> Process another</button>}
      </div>

      {error && <div className="inline-error" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}

      <AnimatePresence mode="wait">
        {!run ? (
          <motion.div key="upload" className="upload-experience" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
            <section className="upload-card">
              <div className="upload-card-heading">
                <div><span className="step-number">1</span><div><strong>Upload an invoice PDF</strong><span>We store and process the actual document bytes.</span></div></div>
                <span className="secure-label">Local demo storage</span>
              </div>
              <div
                className={`drop-zone ${dragging ? "dragging" : ""} ${selectedFile ? "has-file" : ""}`}
                onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
                onDragOver={(event) => event.preventDefault()}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
              >
                <input ref={inputRef} type="file" accept="application/pdf,.pdf" onChange={(event) => event.target.files?.[0] && acceptFile(event.target.files[0])} />
                <div className="upload-icon">{selectedFile ? <FileText size={31} /> : <UploadCloud size={31} />}</div>
                {selectedFile ? (
                  <>
                    <span className="file-ready-label"><CheckCircle2 size={14} /> PDF ready</span>
                    <strong>{selectedFile.name}</strong>
                    <span>{(selectedFile.size / 1024).toFixed(1)} KB · Ready for evidence-backed verification</span>
                    <div className="drop-actions">
                      <button className="ghost-button" onClick={() => inputRef.current?.click()}>Choose another</button>
                      <button className="primary-button" onClick={() => upload(selectedFile, "manual-upload")} disabled={uploading}>{uploading ? <><LoaderCircle className="spin" size={17} /> Verifying invoice…</> : <>Process Invoice <ArrowRight size={17} /></>}</button>
                    </div>
                  </>
                ) : (
                  <>
                    <strong>Drop your invoice PDF here</strong>
                    <span>or choose a file from your computer</span>
                    <button className="secondary-button" onClick={() => inputRef.current?.click()}><UploadCloud size={17} /> Browse PDF</button>
                    <small>PDF only · Maximum 10 MB · Never upload real customer data</small>
                  </>
                )}
              </div>
            </section>

            <section className="scenario-section">
              <div className="scenario-heading">
                <div><span className="step-number">2</span><div><strong>Or explore a prepared scenario</strong><span>Each card uploads a genuine PDF through the same API.</span></div></div>
                <span>{samples.length} verified samples</span>
              </div>
              <div className="scenario-grid">
                {samples.map((sample) => {
                  const presentation = scenarioPresentation[sample.filename] || { title: sample.label, lesson: sample.description, icon: FileText, tone: "blue" };
                  const ScenarioIcon = presentation.icon;
                  const isProcessing = processingSample === sample.filename;
                  return (
                    <button
                      type="button"
                      className={`scenario-card scenario-${presentation.tone}`}
                      key={sample.filename}
                      onClick={() => void processSample(sample.filename)}
                      disabled={uploading}
                    >
                      <span className="scenario-icon">{isProcessing ? <LoaderCircle className="spin" size={20} /> : <ScenarioIcon size={20} />}</span>
                      <span className="scenario-copy"><strong>{presentation.title}</strong><small>{presentation.lesson}</small></span>
                      <ArrowRight className="scenario-arrow" size={16} />
                    </button>
                  );
                })}
              </div>
            </section>
          </motion.div>
        ) : (
          <motion.div key="result" className="result-stack" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Timeline run={run} />
            {run.status === "PROCESSING" ? (
              <div className="processing-wait" aria-live="polite">
                <LoaderCircle className="spin" />
                <div className="processing-copy">
                  <small>Current step</small>
                  <strong>{liveProgress?.title}</strong>
                  <span>{liveProgress?.detail}</span>
                  <div className="processing-progress" aria-label={`${liveProgress?.progress || 0}% complete`}>
                    <i style={{ width: `${liveProgress?.progress || 0}%` }} />
                  </div>
                </div>
              </div>
            ) : (
              <Receipt run={run} onRefresh={refreshRun} />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
