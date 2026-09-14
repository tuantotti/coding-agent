import type { RunStatus } from "../hooks/useRunStream";

export interface RunSummary {
  run_id: string;
  label: string;
  status: RunStatus;
  time: string;
}

interface Props {
  runs: RunSummary[];
  activeRunId: string | null;
  onSelect: (runId: string) => void;
  onNewRun: () => void;
}

const STATUS_ICON: Record<RunStatus, string> = {
  idle: "○", queued: "◔", running: "◑",
  awaiting_approval: "◐", completed: "✓", failed: "✕",
};
const STATUS_COLOR: Record<RunStatus, string> = {
  idle: "var(--text-faint)", queued: "#fbbf24", running: "#60a5fa",
  awaiting_approval: "#c4b5fd", completed: "#4ade80", failed: "#f87171",
};

const NAV_ITEMS = [
  { icon: "💬", label: "Chat" },
  { icon: "📦", label: "Archived" },
  { icon: "📚", label: "Library" },
];

export function Sidebar({ runs, activeRunId, onSelect, onNewRun }: Props) {
  return (
    <aside className="sidebar">
      {/* Header */}
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <div className="sidebar-logo">🤖</div>
          <span className="sidebar-name">Seminar2</span>
        </div>
        <button className="sidebar-collapse-btn" title="Collapse">⊟</button>
      </div>

      {/* New run */}
      <button className="sidebar-new-btn" onClick={onNewRun}>
        <span style={{ fontSize: 16, lineHeight: 1 }}>⊕</span>
        New Run
      </button>

      {/* Features nav */}
      <div className="sidebar-section">
        <div className="sidebar-section-label">Features</div>
        {NAV_ITEMS.map((item) => (
          <div key={item.label} className="sidebar-item">
            <span className="sidebar-item-icon">{item.icon}</span>
            <span className="sidebar-item-label">{item.label}</span>
          </div>
        ))}
      </div>

      {/* Workspaces / recent runs */}
      {runs.length > 0 && (
        <div className="sidebar-section" style={{ flex: 1, overflow: "hidden", display: "flex", flexDirection: "column" }}>
          <div className="sidebar-section-label">Workspaces</div>
          <div className="sidebar-runs">
            {runs.map((run) => (
              <div
                key={run.run_id}
                className={`sidebar-item${activeRunId === run.run_id ? " active" : ""}`}
                onClick={() => onSelect(run.run_id)}
              >
                <span className="sidebar-item-icon" style={{ color: STATUS_COLOR[run.status] }}>
                  {STATUS_ICON[run.status]}
                </span>
                <span className="sidebar-item-label">{run.label}</span>
                <span className="sidebar-item-time">{run.time}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Bottom info card */}
      <div className="sidebar-bottom">
        <div className="sidebar-bottom-icon">✨</div>
        <div className="sidebar-bottom-title">MAS for SE</div>
        <div className="sidebar-bottom-desc">
          Multi-agent system for code generation, testing & review.
        </div>
        <button className="sidebar-bottom-btn">View Architecture</button>
      </div>
    </aside>
  );
}
