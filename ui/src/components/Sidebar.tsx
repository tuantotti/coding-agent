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
  idle: "○",
  queued: "◔",
  running: "◑",
  awaiting_approval: "◐",
  completed: "✓",
  failed: "✕",
};

const STATUS_COLOR: Record<RunStatus, string> = {
  idle: "var(--sidebar-muted)",
  queued: "#d97706",
  running: "#3b82f6",
  awaiting_approval: "#a78bfa",
  completed: "#4ade80",
  failed: "#f87171",
};

export function Sidebar({ runs, activeRunId, onSelect, onNewRun }: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <div className="sidebar-logo">🤖</div>
        <span className="sidebar-title">Coding Agent</span>
      </div>

      <button className="sidebar-new-btn" onClick={onNewRun}>
        <span style={{ fontSize: 16 }}>＋</span>
        New run
      </button>

      {runs.length > 0 && (
        <>
          <div className="sidebar-section-label">Recents</div>
          <div className="sidebar-runs">
            {runs.map((run) => (
              <div
                key={run.run_id}
                className={`sidebar-run-item${activeRunId === run.run_id ? " active" : ""}`}
                onClick={() => onSelect(run.run_id)}
              >
                <span
                  className="sidebar-run-icon"
                  style={{ color: STATUS_COLOR[run.status] }}
                >
                  {STATUS_ICON[run.status]}
                </span>
                <span className="sidebar-run-label">{run.label}</span>
                <span className="sidebar-run-time">{run.time}</span>
              </div>
            ))}
          </div>
        </>
      )}
    </aside>
  );
}
