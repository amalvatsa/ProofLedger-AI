import { ArrowLeft, FileText, LoaderCircle, RefreshCw, UploadCloud, WandSparkles, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type DragEvent, useEffect, useRef, useState } from "react";
import { api, apiUrl } from "../api";
import { Receipt } from "../components/Receipt";
import { Timeline } from "../components/Timeline";
import type { DemoSample, RunRecord } from "../types";

export function ProcessInvoicePage() {
  const [samples, setSamples] = useState<DemoSample[]>([]);
  const [sampleName, setSampleName] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [run, setRun] = useState<RunRecord | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getSamples().then((data) => {
      setSamples(data);
      if (data.length) setSampleName(data[0].filename);
    }).catch(() => setSamples([]));
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

  async function processSample() {
    if (!sampleName) return;
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

  return (
    <div className="page-wrap process-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">PDF to defensible decision</span>
          <h1>{run ? "Your decision is ready" : "Process an invoice"}</h1>
          <p>{run ? "Follow every backend event, then inspect the claims, source records, arithmetic, and control outcomes." : "Drop in a supplier PDF. ProofLedger reads the actual document, checks confirmed records, and saves an explainable recommendation."}</p>
        </div>
        {run && <button className="secondary-button" onClick={reset}><ArrowLeft size={16} /> Process another</button>}
      </div>

      {error && <div className="inline-error" role="alert"><span>{error}</span><button onClick={() => setError("")} aria-label="Dismiss error"><X size={16} /></button></div>}

      <AnimatePresence mode="wait">
        {!run ? (
          <motion.div key="upload" className="upload-layout" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
            <section className="upload-card">
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
                    <strong>{selectedFile.name}</strong>
                    <span>{(selectedFile.size / 1024).toFixed(1)} KB · Ready to send through the real upload API</span>
                    <div className="drop-actions">
                      <button className="ghost-button" onClick={() => inputRef.current?.click()}>Choose another</button>
                      <button className="primary-button" onClick={() => upload(selectedFile, "manual-upload")} disabled={uploading}>{uploading ? <><LoaderCircle className="spin" size={17} /> Processing…</> : <>Process invoice <UploadCloud size={17} /></>}</button>
                    </div>
                  </>
                ) : (
                  <>
                    <strong>Drop your invoice here</strong>
                    <span>PDF only · Up to 10 MB · Your file is stored locally for this demo</span>
                    <button className="secondary-button" onClick={() => inputRef.current?.click()}>Browse PDF</button>
                  </>
                )}
              </div>

              <div className="privacy-line"><span className="demo-dot" /> Synthetic demo environment · Never upload real customer data</div>
            </section>

            <aside className="sample-card">
              <div className="sample-icon"><WandSparkles size={21} /></div>
              <span className="eyebrow">Prepared demo cases</span>
              <h2>Try a real sample PDF</h2>
              <p>The picker only selects a genuine file. Every sample travels through the exact same upload and processing API.</p>
              <label htmlFor="sample-select">Sample case</label>
              <select id="sample-select" value={sampleName} onChange={(event) => setSampleName(event.target.value)}>
                {samples.map((sample) => <option key={sample.filename} value={sample.filename}>{sample.label}</option>)}
              </select>
              {samples.find((sample) => sample.filename === sampleName) && (
                <div className="sample-description">
                  <strong>Expected safe outcome</strong>
                  <span>{samples.find((sample) => sample.filename === sampleName)?.expected}</span>
                  <p>{samples.find((sample) => sample.filename === sampleName)?.description}</p>
                </div>
              )}
              <button className="primary-button full-button" onClick={processSample} disabled={uploading || !sampleName}>
                {uploading ? <><LoaderCircle className="spin" size={17} /> Processing actual PDF…</> : <>Process this sample <RefreshCw size={16} /></>}
              </button>
            </aside>
          </motion.div>
        ) : (
          <motion.div key="result" className="result-stack" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Timeline run={run} />
            {run.status === "PROCESSING" ? (
              <div className="processing-wait"><LoaderCircle className="spin" /><div><strong>ProofLedger is evaluating persisted evidence</strong><span>The timeline advances only when the backend saves a real event.</span></div></div>
            ) : (
              <Receipt run={run} onRefresh={refreshRun} />
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
