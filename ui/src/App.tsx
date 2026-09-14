import { useState } from "react";
import { ApprovalCard } from "./components/ApprovalCard";
import { ChatArea } from "./components/ChatArea";
import { RunStatusBadge } from "./components/RunStatusBadge";
import { Sidebar, type RunSummary } from "./components/Sidebar";
import { TaskBar } from "./components/TaskBar";
import { useRunStream } from "./hooks/useRunStream";
import { api } from "./services/api";
import type { ResumeRunRequest } from "./services/api";

interface RunRecord {
  run_id: string;
  task: string;
  sourceFolder: string;
  startedAt: Date;
}

function relativeTime(d: Date): string {
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

export function App() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const activeRun = runs.find((r) => r.run_id === activeRunId) ?? null;
  const stream = useRunStream(activeRunId);

  const isRunning =
    submitting ||
    (stream.status !== "idle" &&
      stream.status !== "completed" &&
      stream.status !== "failed");

  const handleStart = async (task: string, sourceFolder: string) => {
    setSubmitting(true);
    setApiError(null);
    try {
      const run = await api.startRun({ task, source_folder: sourceFolder });
      const record: RunRecord = {
        run_id: run.run_id,
        task,
        sourceFolder,
        startedAt: new Date(),
      };
      setRuns((prev) => [record, ...prev]);
      setActiveRunId(run.run_id);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Failed to start run");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResume = async (req: ResumeRunRequest) => {
    if (!activeRunId) return;
    setApiError(null);
    try {
      await api.resumeRun(activeRunId, req);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Failed to submit decisions");
    }
  };

  const handleNewRun = () => {
    setActiveRunId(null);
    setApiError(null);
    stream.close();
  };

  const sidebarRuns: RunSummary[] = runs.map((r) => ({
    run_id: r.run_id,
    label: r.task.length > 36 ? r.task.slice(0, 36) + "…" : r.task,
    status: r.run_id === activeRunId ? stream.status : "idle",
    time: relativeTime(r.startedAt),
  }));

  const topbarTitle = activeRun
    ? activeRun.task.length > 60
      ? activeRun.task.slice(0, 60) + "…"
      : activeRun.task
    : null;

  return (
    <div className="app-shell">
      <Sidebar
        runs={sidebarRuns}
        activeRunId={activeRunId}
        onSelect={setActiveRunId}
        onNewRun={handleNewRun}
      />

      <div className="main-area">
        {/* Top bar */}
        <div className="topbar">
          {topbarTitle ? (
            <>
              <span className="topbar-title">{topbarTitle}</span>
              <RunStatusBadge status={stream.status} />
            </>
          ) : (
            <span className="topbar-title topbar-empty">New run</span>
          )}
        </div>

        {/* Error */}
        {apiError && (
          <div className="error-toast">
            <span>⚠️</span>
            {apiError}
          </div>
        )}

        {/* Chat area */}
        <ChatArea
          task={activeRun?.task ?? null}
          sourceFolder={activeRun?.sourceFolder ?? null}
          events={stream.events}
        />

        {/* Inline approval card — injected above task bar */}
        {stream.approvals.length > 0 && (
          <div style={{ padding: "0 24px 12px" }}>
            <ApprovalCard
              approvals={stream.approvals}
              onSubmit={handleResume}
              disabled={stream.status !== "awaiting_approval"}
            />
          </div>
        )}

        {/* Output */}
        {stream.output && (
          <div style={{ padding: "0 24px 12px" }}>
            <div
              style={{
                background: "#f0fdf4",
                border: "1px solid #86efac",
                borderLeft: "4px solid #16a34a",
                borderRadius: "var(--radius-md)",
                padding: "12px 16px",
              }}
            >
              <div style={{ fontSize: 12, fontWeight: 700, color: "#166534", marginBottom: 6 }}>
                ✅ Final output
              </div>
              <pre style={{ margin: 0, fontSize: 13, whiteSpace: "pre-wrap", color: "#15803d" }}>
                {stream.output}
              </pre>
            </div>
          </div>
        )}

        {/* Task bar */}
        <TaskBar
          onSubmit={handleStart}
          disabled={isRunning}
          defaultFolder={activeRun?.sourceFolder}
        />
      </div>
    </div>
  );
}
