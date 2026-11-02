export type Decision = "READY_FOR_POSTING" | "NEEDS_REVIEW" | "BLOCKED";
export type RunStatus = "PROCESSING" | "COMPLETED" | "FAILED";

export interface RunEvent {
  id: number;
  stage: string;
  outcome: string;
  explanation: string;
  duration_ms: number;
  created_at: string;
}

export interface PolicyCheck {
  rule_id: string;
  title: string;
  outcome: "PASS" | "REVIEW" | "FAIL";
  detail: string;
  evidence: Record<string, unknown>;
}

export interface ExtractedFields {
  invoice_number: string | null;
  issue_date: string | null;
  vendor_name: string | null;
  vendor_id: string | null;
  po_reference: string | null;
  currency: string | null;
  net_amount: string | null;
  tax_amount: string | null;
  gross_total: string | null;
  tax_treatment: string | null;
  line_descriptions: string[];
}

export interface RunRecord {
  id: string;
  status: RunStatus;
  decision: Decision | null;
  original_filename: string;
  file_size: number;
  document_hash: string;
  extraction_method: string | null;
  extracted: {
    fields?: ExtractedFields;
    sources?: Record<string, { page: number; snippet: string; method?: string } | Array<{ page: number; snippet: string; method?: string }>>;
    page_count?: number;
    validation?: {
      required_fields_present: boolean;
      source_evidence_complete: boolean;
      totals_reconciled: boolean;
      sourced_field_count: number;
      fallback_attempted: boolean;
      fallback_accepted_fields: number;
    };
    vendor_id?: string;
    candidate_pos?: string[];
  };
  diagnostics: string[];
  checks: PolicyCheck[];
  explanation: string | null;
  next_action: string | null;
  money: Record<string, string | null>;
  matched_po_number: string | null;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
  events: RunEvent[];
  notes: Array<{ id: number; note: string; created_at: string }>;
  document_url: string | null;
}

export interface Summary {
  processed: number;
  ready: number;
  needs_review: number;
  blocked: number;
}

export interface LedgerRow {
  po_number: string;
  vendor_id: string;
  vendor_name: string;
  currency: string;
  authorized_net: string;
  confirmed_net: string;
  remaining_net: string;
  status: string;
  description: string;
}

export interface DemoSample {
  filename: string;
  label: string;
  expected: string;
  description: string;
}

export interface AssistantStatus {
  configured: boolean;
  provider_id: "openai" | "gemini" | null;
  provider: string | null;
  model: string;
  thinking_level: "minimal" | "low" | "medium" | "high" | null;
  configuration_error: string | null;
  scope: "selected_invoice_only";
  guardrails: string[];
}

export interface AssistantEvidence {
  label: string;
  detail: string;
}

export interface AssistantReply {
  answer: string;
  evidence: AssistantEvidence[];
  provider_id: "openai" | "gemini";
  provider: string;
  model: string;
  latency_ms: number;
  scope: "selected_invoice_only";
  decision_snapshot: Decision;
}

export interface AssistantHistoryMessage {
  role: "user" | "assistant";
  content: string;
}
