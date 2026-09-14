import type { RunStatus } from "../hooks/useRunStream";

const LABEL: Record<RunStatus, string> = {
  idle: "Idle",
  queued: "Queued",
  running: "Running",
  awaiting_approval: "Needs approval",
  completed: "Done",
  failed: "Failed",
};

export function RunStatusBadge({ status }: { status: RunStatus }) {
  return (
    <span className={`status-badge ${status}`}>
      <span className="status-dot" />
      {LABEL[status]}
    </span>
  );
}
