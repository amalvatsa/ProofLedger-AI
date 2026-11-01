import { BrainCircuit, FileCheck2, History, Inbox, LayoutDashboard, ShieldCheck, Sparkles, UploadCloud } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { InvoiceAssistant } from "./InvoiceAssistant";

const navItems = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/process", label: "Process invoice", icon: UploadCloud },
  { to: "/review", label: "Review queue", icon: Inbox },
  { to: "/history", label: "History", icon: History },
];

export function AppShell() {
  const [assistantOpen, setAssistantOpen] = useState(false);

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="Primary navigation">
        <div className="brand-block">
          <div className="brand-mark" aria-hidden="true">
            <FileCheck2 size={23} strokeWidth={2.4} />
          </div>
          <div>
            <div className="brand-name">ProofLedger</div>
            <div className="brand-subtitle">AI finance operations</div>
          </div>
        </div>

        <div className="demo-pill"><span className="demo-dot" /> Synthetic workspace</div>

        <span className="nav-section-label">Workspace</span>
        <nav className="nav-list">
          {navItems.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}
            >
              <Icon size={18} />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>

        <button
          type="button"
          className="assistant-launch"
          onClick={() => setAssistantOpen(true)}
          aria-expanded={assistantOpen}
          aria-controls="invoice-assistant-drawer"
        >
          <span className="assistant-launch-icon"><BrainCircuit size={19} /></span>
          <span><strong>Invoice AI</strong><small>Explain a saved decision</small></span>
          <Sparkles size={14} />
        </button>

        <div className="sidebar-trust">
          <ShieldCheck size={19} />
          <div>
            <strong>Policy stays authoritative</strong>
            <span>AI explains evidence. It never approves payment.</span>
          </div>
        </div>
      </aside>

      <main className="main-content">
        <Outlet />
      </main>

      <InvoiceAssistant open={assistantOpen} onClose={() => setAssistantOpen(false)} />
    </div>
  );
}
