import type { AssistantHistoryMessage, AssistantReply, AssistantStatus, DemoSample, LedgerRow, RunRecord, Summary } from "./types";

export const API_BASE =
  import.meta.env.VITE_API_URL ||
  (window.location.port === "8000" ? "" : "http://127.0.0.1:8000");

export function apiUrl(path: string): string {
  if (path.startsWith("http")) return path;
  return `${API_BASE}${path}`;
}

function errorDetail(payload: unknown, status: number): string {
  if (!payload || typeof payload !== "object" || !("detail" in payload)) {
    return `Request failed with ${status}.`;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item && typeof item === "object" && "msg" in item ? String(item.msg) : ""))
      .filter(Boolean);
    if (messages.length) return messages.join(" ");
  }
  return `Request failed with ${status}.`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: "Request failed." }));
    throw new Error(errorDetail(payload, response.status));
  }
  return response.json() as Promise<T>;
}

export const api = {
  getSummary: () => request<Summary>("/api/summary"),
  getRuns: (params = "") => request<RunRecord[]>(`/api/runs${params ? `?${params}` : ""}`),
  getRun: (id: string) => request<RunRecord>(`/api/runs/${id}`),
  getLedger: () => request<LedgerRow[]>("/api/ledger"),
  getSamples: () => request<DemoSample[]>("/api/demo-samples"),
  getHealth: () => request<{ status: string; ocr_available: boolean }>("/api/health"),
  getAssistantStatus: () => request<AssistantStatus>("/api/assistant/status"),
  askAssistant: (id: string, question: string, history: AssistantHistoryMessage[]) =>
    request<AssistantReply>(`/api/runs/${id}/assistant`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
    }),
  upload: async (file: File, source = "upload") => {
    const form = new FormData();
    form.append("file", file);
    form.append("source", source);
    return request<{ run_id: string; status: string }>("/api/runs", { method: "POST", body: form });
  },
  addNote: (id: string, note: string) =>
    request(`/api/runs/${id}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note }),
    }),
  confirm: (id: string) => request(`/api/runs/${id}/confirm`, { method: "POST" }),
};

export function formatDate(value: string, includeTime = true): string {
  const date = new Date(value);
  return new Intl.DateTimeFormat("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(includeTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(date);
}

export function formatMoney(value: string | null | undefined, currency = "INR"): string {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(value));
}
