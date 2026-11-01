import {
  ArrowLeft,
  Bot,
  BrainCircuit,
  CheckCircle2,
  CircleSlash2,
  FileText,
  Inbox,
  LockKeyhole,
  RotateCcw,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { api, formatDate, formatMoney } from "../api";
import type {
  AssistantEvidence,
  AssistantHistoryMessage,
  AssistantStatus,
  Decision,
  RunRecord,
} from "../types";
import { StatusBadge } from "./StatusBadge";

interface ChatEntry extends AssistantHistoryMessage {
  id: string;
  evidence?: AssistantEvidence[];
  intro?: boolean;
  provider?: string;
  model?: string;
  latencyMs?: number;
}

interface InvoiceAssistantProps {
  open: boolean;
  onClose: () => void;
}

type ProviderState = "checking" | "configured" | "verified" | "limited" | "unavailable";

function readableDecision(decision: RunRecord["decision"]): string {
  if (decision === "READY_FOR_POSTING") return "ready for posting";
  if (decision === "NEEDS_REVIEW") return "in review";
  if (decision === "BLOCKED") return "blocked";
  return "unavailable";
}

function decisionGroup(decision: Decision | null): "attention" | "ready" {
  return decision === "READY_FOR_POSTING" ? "ready" : "attention";
}

function invoiceLabel(run: RunRecord): string {
  return run.extracted.fields?.invoice_number || run.original_filename || run.id.slice(0, 8);
}

function InvoiceChoice({ run, onSelect }: { run: RunRecord; onSelect: (run: RunRecord) => void }) {
  const fields = run.extracted.fields;
  return (
    <button type="button" className="assistant-invoice-choice" onClick={() => onSelect(run)}>
      <span className="assistant-invoice-icon"><FileText size={17} /></span>
      <span className="assistant-invoice-copy">
        <strong>{invoiceLabel(run)}</strong>
        <small>{fields?.vendor_name || fields?.vendor_id || "Unmatched supplier"}</small>
      </span>
      <span className="assistant-invoice-meta">
        <strong>{formatMoney(run.money.gross, run.money.currency || "INR")}</strong>
        <small>{formatDate(run.updated_at, false)}</small>
      </span>
      <StatusBadge decision={run.decision} status={run.status} compact />
    </button>
  );
}

export function InvoiceAssistant({ open, onClose }: InvoiceAssistantProps) {
  const [status, setStatus] = useState<AssistantStatus | null>(null);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [selectedRun, setSelectedRun] = useState<RunRecord | null>(null);
  const [messages, setMessages] = useState<ChatEntry[]>([]);
  const [question, setQuestion] = useState("");
  const [search, setSearch] = useState("");
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingAnswer, setLoadingAnswer] = useState(false);
  const [error, setError] = useState("");
  const [failedQuestion, setFailedQuestion] = useState("");
  const [providerState, setProviderState] = useState<ProviderState>("checking");
  const logRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    let active = true;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    setLoadingRuns(true);
    setError("");
    Promise.all([api.getAssistantStatus(), api.getRuns("limit=200")])
      .then(([assistantStatus, records]) => {
        if (!active) return;
        setStatus(assistantStatus);
        setProviderState(assistantStatus.configured ? "configured" : "unavailable");
        setRuns(records.filter((run) => run.status === "COMPLETED" && Boolean(run.decision)));
      })
      .catch((caught) => {
        if (active) setError(caught instanceof Error ? caught.message : "Could not load invoice receipts.");
      })
      .finally(() => {
        if (active) setLoadingRuns(false);
      });
    window.requestAnimationFrame(() => closeRef.current?.focus());
    return () => {
      active = false;
      document.body.style.overflow = previousOverflow;
    };
  }, [open]);

  useEffect(() => {
    if (!open) {
      setSelectedRun(null);
      setMessages([]);
      setQuestion("");
      setSearch("");
      setError("");
      setFailedQuestion("");
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loadingAnswer]);

  const filteredRuns = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return runs;
    return runs.filter((run) => {
      const fields = run.extracted.fields;
      return `${fields?.invoice_number || ""} ${fields?.vendor_name || ""} ${fields?.vendor_id || ""} ${run.original_filename}`
        .toLowerCase()
        .includes(query);
    });
  }, [runs, search]);

  const groupedRuns = useMemo(() => ({
    attention: filteredRuns.filter((run) => decisionGroup(run.decision) === "attention"),
    ready: filteredRuns.filter((run) => decisionGroup(run.decision) === "ready"),
  }), [filteredRuns]);

  const quickQuestions = useMemo(() => {
    if (!selectedRun) return [];
    const attentionCheck = selectedRun.checks.find((check) => check.outcome !== "PASS");
    const evidenceQuestion = attentionCheck
      ? `Explain the ${attentionCheck.title.toLowerCase()} evidence.`
      : "Which controls passed and what evidence supports them?";
    return [
      "Why did this invoice receive this decision?",
      evidenceQuestion,
      selectedRun.matched_po_number ? "Explain the PO balance calculation." : "What PO evidence is missing?",
      "What should the AP analyst do next?",
    ];
  }, [selectedRun]);

  function chooseInvoice(run: RunRecord) {
    setSelectedRun(run);
    setSearch("");
    setQuestion("");
    setError("");
    setFailedQuestion("");
    setMessages([
      {
        id: `intro-${run.id}`,
        role: "assistant",
        intro: true,
        content: `This conversation is now locked to ${invoiceLabel(run)}. I can explain why it is ${readableDecision(run.decision)}, trace the evidence, and walk through its controls. I cannot change the decision or authorize payment.`,
      },
    ]);
  }

  function changeInvoice() {
    setSelectedRun(null);
    setMessages([]);
    setQuestion("");
    setError("");
    setFailedQuestion("");
  }

  async function ask(text: string, retry = false) {
    const trimmed = text.trim();
    if (!trimmed || !selectedRun || loadingAnswer || !status?.configured) return;
    const userEntry: ChatEntry = { id: `user-${Date.now()}`, role: "user", content: trimmed };
    const historySource = retry && messages.at(-1)?.role === "user" && messages.at(-1)?.content === trimmed
      ? messages.slice(0, -1)
      : messages;
    const history = historySource
      .filter((message) => !message.intro)
      .slice(-8)
      .map(({ role, content }) => ({ role, content: content.slice(0, 500) }));

    if (!retry) setMessages((current) => [...current, userEntry]);
    setQuestion("");
    setError("");
    setFailedQuestion("");
    setLoadingAnswer(true);
    try {
      const reply = await api.askAssistant(selectedRun.id, trimmed, history);
      setProviderState("verified");
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: reply.answer,
          evidence: reply.evidence,
          provider: reply.provider,
          model: reply.model,
          latencyMs: reply.latency_ms,
        },
      ]);
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "The invoice assistant could not answer.";
      setError(message);
      setFailedQuestion(trimmed);
      if (/rate limit|quota|credits/i.test(message)) setProviderState("limited");
      else if (/credential|provider|unavailable|configured/i.test(message)) setProviderState("unavailable");
    } finally {
      setLoadingAnswer(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    void ask(question);
  }

  const providerLabel = !status
    ? "Checking model"
    : !status.configured
      ? "Model setup needed"
      : providerState === "verified"
        ? `${status.provider_id === "gemini" ? "Gemini" : "OpenAI"} · ${status.model} · verified`
        : providerState === "limited"
          ? "Provider rate-limited"
          : providerState === "unavailable"
            ? "Provider unavailable"
            : `${status.provider_id === "gemini" ? "Gemini" : "OpenAI"} · ${status.model} · configured`;

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.button
            type="button"
            className="global-assistant-scrim"
            aria-label="Close invoice assistant"
            onClick={onClose}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />
          <motion.aside
            id="invoice-assistant-drawer"
            className="global-assistant-drawer"
            role="dialog"
            aria-modal="true"
            aria-labelledby="global-assistant-title"
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ type: "spring", stiffness: 320, damping: 34 }}
          >
            <header className="global-assistant-header">
              <div className="assistant-title-group">
                <div className="assistant-logo"><BrainCircuit size={22} /></div>
                <div>
                  <span className="assistant-kicker"><Sparkles size={12} /> Evidence-grounded AI</span>
                  <h2 id="global-assistant-title">Invoice AI</h2>
                </div>
              </div>
              <div className="global-assistant-header-actions">
                <div
                  className={`assistant-status ${providerState}`}
                  title="Configured means a key is present; verified means a live answer succeeded."
                >
                  <span />
                  {providerLabel}
                </div>
                <button ref={closeRef} type="button" className="global-assistant-close" onClick={onClose} aria-label="Close invoice assistant" title="Close invoice assistant">
                  <X size={19} />
                </button>
              </div>
            </header>

            {!selectedRun ? (
              <div className="assistant-selector-view">
                <div className="assistant-selector-intro">
                  <span className="eyebrow">Step 1 of 2 · Choose the evidence scope</span>
                  <h3>Select an invoice before chatting</h3>
                  <p>The conversation stays locked until you manually choose one saved Decision Receipt. The assistant never searches across invoices.</p>
                  <div className="assistant-locked-state"><LockKeyhole size={15} /><span>Chat is locked · No invoice context selected</span></div>
                </div>

                <label className="assistant-invoice-search">
                  <Search size={17} />
                  <span className="sr-only">Search invoices</span>
                  <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search invoice, supplier, or filename" />
                </label>

                {error && <div className="assistant-error" role="alert">{error}</div>}
                {loadingRuns ? (
                  <div className="assistant-selector-loading"><span /><span /><span /> Loading saved receipts</div>
                ) : filteredRuns.length === 0 ? (
                  <div className="assistant-selector-empty"><Inbox size={25} /><strong>No matching receipts</strong><span>Process an invoice or change your search.</span></div>
                ) : (
                  <div className="assistant-invoice-groups">
                    {groupedRuns.attention.length > 0 && (
                      <section>
                        <div className="assistant-group-heading">
                          <div><CircleSlash2 size={15} /><strong>Needs attention</strong></div>
                          <span>{groupedRuns.attention.length}</span>
                        </div>
                        <div className="assistant-invoice-list">
                          {groupedRuns.attention.map((run) => <InvoiceChoice key={run.id} run={run} onSelect={chooseInvoice} />)}
                        </div>
                      </section>
                    )}
                    {groupedRuns.ready.length > 0 && (
                      <section>
                        <div className="assistant-group-heading">
                          <div><CheckCircle2 size={15} /><strong>Ready for posting</strong></div>
                          <span>{groupedRuns.ready.length}</span>
                        </div>
                        <div className="assistant-invoice-list">
                          {groupedRuns.ready.map((run) => <InvoiceChoice key={run.id} run={run} onSelect={chooseInvoice} />)}
                        </div>
                      </section>
                    )}
                  </div>
                )}
                <p className="assistant-selector-footnote"><ShieldCheck size={13} /> Only completed receipts are selectable. Selection alone sends no data to the model.</p>
              </div>
            ) : (
              <div className="assistant-conversation-view">
                <div className="assistant-context-bar">
                  <button type="button" onClick={changeInvoice}><ArrowLeft size={15} /> Change invoice</button>
                  <div>
                    <span>Selected receipt</span>
                    <strong>{invoiceLabel(selectedRun)} · {selectedRun.extracted.fields?.vendor_name || "Unmatched supplier"}</strong>
                  </div>
                  <StatusBadge decision={selectedRun.decision} status={selectedRun.status} compact />
                </div>

                <div className="assistant-scope-summary">
                  <div><LockKeyhole size={15} /><span><strong>One receipt only</strong> Context · {selectedRun.id.slice(0, 8)}</span></div>
                  <div><ShieldCheck size={15} /><span><strong>No overrides</strong> Policy remains authoritative</span></div>
                </div>

                {status && !status.configured ? (
                  <div className="assistant-setup-state">
                    <div className="assistant-setup-icon"><BrainCircuit size={27} /></div>
                    <div>
                      <span className="eyebrow">Real model required</span>
                      <h4>Connect the invoice AI</h4>
                      <p>{status.configuration_error || <>Set <code>GEMINI_API_KEY</code> for Google Gemini or <code>OPENAI_API_KEY</code> for OpenAI, choose the provider if needed, and restart ProofLedger. No simulated answer is shown while the model is unavailable.</>}</p>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="assistant-message-log" ref={logRef} role="log" aria-live="polite" aria-label="Invoice assistant conversation">
                      {messages.map((message) => (
                        <motion.div
                          className={`assistant-message ${message.role}`}
                          key={message.id}
                          initial={{ opacity: 0, y: 5 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.18 }}
                        >
                          {message.role === "assistant" && <div className="message-avatar"><Bot size={15} /></div>}
                          <div className="message-content">
                            <p>{message.content}</p>
                            {message.provider && (
                              <span className="assistant-response-meta">
                                <Sparkles size={11} /> {message.provider} · {message.model} · {message.latencyMs} ms
                              </span>
                            )}
                            {message.evidence && message.evidence.length > 0 && (
                              <div className="assistant-evidence-list" aria-label="Evidence used">
                                {message.evidence.map((item) => (
                                  <details className="assistant-evidence-item" key={`${message.id}-${item.label}`}>
                                    <summary><ShieldCheck size={11} /> {item.label}</summary>
                                    <p>{item.detail}</p>
                                  </details>
                                ))}
                              </div>
                            )}
                          </div>
                        </motion.div>
                      ))}
                      {loadingAnswer && (
                        <div className="assistant-message assistant">
                          <div className="message-avatar"><Bot size={15} /></div>
                          <div className="assistant-thinking"><span /><span /><span /> Checking selected receipt evidence</div>
                        </div>
                      )}
                    </div>

                    <div className="assistant-quick-questions" aria-label="Suggested questions">
                      {quickQuestions.map((item) => (
                        <button type="button" onClick={() => void ask(item)} disabled={loadingAnswer || !status?.configured} key={item}>{item}</button>
                      ))}
                    </div>

                    {error && (
                      <div className="assistant-error" role="alert">
                        <span>{error}</span>
                        {failedQuestion && status?.configured && (
                          <button type="button" onClick={() => void ask(failedQuestion, true)} disabled={loadingAnswer}>
                            <RotateCcw size={13} /> Retry
                          </button>
                        )}
                      </div>
                    )}

                    <form className="assistant-composer" onSubmit={submit}>
                      <label className="sr-only" htmlFor="global-assistant-question">Ask about the selected invoice</label>
                      <textarea
                        id="global-assistant-question"
                        value={question}
                        onChange={(event) => setQuestion(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && !event.shiftKey) {
                            event.preventDefault();
                            void ask(question);
                          }
                        }}
                        placeholder="Ask why it was flagged, how the balance was calculated, or what happens next…"
                        maxLength={500}
                        rows={2}
                        disabled={!status?.configured || loadingAnswer}
                      />
                      <div className="assistant-compose-actions">
                        <span>{question.length}/500</span>
                        <button type="submit" aria-label="Send invoice question" disabled={!question.trim() || loadingAnswer || !status?.configured}>
                          <Send size={16} />
                        </button>
                      </div>
                    </form>
                    <p className="assistant-disclaimer">AI explains the selected receipt; it cannot approve, post, or pay an invoice.</p>
                  </>
                )}
              </div>
            )}
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
