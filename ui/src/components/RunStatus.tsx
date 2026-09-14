import type { RunStatus as Status } from "../hooks/useRunStream";

interface Props {
  status: Status;
}

const LABEL: Record<Status, string> = {
  idle: "Idle",
  queued: "Queued",
  running: "Running…",
  awaiting_approval: "Awaiting approval",
  completed: "Completed",
  failed: "Failed",
};

const COLOR: Record<Status, string> = {
  idle: "#6b7280",
  queued: "#d97706",
  running: "#2563eb",
  awaiting_approval: "#7c3aed",
  completed: "#16a34a",
  failed: "#dc2626",
};

export function RunStatus({ status }: Props) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 10px",
        borderRadius: 12,
        fontSize: 13,
        fontWeight: 600,
        color: "#fff",
        background: COLOR[status],
      }}
    >
      {status === "running" && <span style={{ marginRight: 5 }}>⏳</span>}
      {status === "completed" && <span style={{ marginRight: 5 }}>✅</span>}
      {status === "failed" && <span style={{ marginRight: 5 }}>❌</span>}
      {status === "awaiting_approval" && <span style={{ marginRight: 5 }}>👀</span>}
      {LABEL[status]}
    </span>
  );
}
