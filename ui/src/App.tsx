import { useState } from "react";
import { ApprovalPanel } from "./components/ApprovalPanel";
import { EventStream } from "./components/EventStream";
import { RunStatus } from "./components/RunStatus";
import { TaskInput } from "./components/TaskInput";
import { useRunStream } from "./hooks/useRunStream";
import { api } from "./services/api";
import type { ResumeRunRequest } from "./services/api";

export function App() {
  const [runId, setRunId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const stream = useRunStream(runId);

  const isActive =
    submitting ||
    (stream.status !== "idle" && stream.status !== "completed" && stream.status !== "failed");

  const handleStart = async (task: string, sourceFolder: string) => {
    setSubmitting(true);
    setApiError(null);
    try {
      const run = await api.startRun({ task, source_folder: sourceFolder });
      setRunId(run.run_id);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Failed to start run");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResume = async (req: ResumeRunRequest) => {
    if (!runId) return;
    setApiError(null);
    try {
      await api.resumeRun(runId, req);
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Failed to submit decisions");
    }
  };

  const handleReset = () => {
    setRunId(null);
    setApiError(null);
    stream.close();
  };

  return (
    <div style={{ maxWidth: 800, margin: "0 auto", padding: "32px 20px", fontFamily: "system-ui, sans-serif" }}>
      <header style={{ marginBottom: 28 }}>
        <h1 style={{ margin: 0, fontSize: 22, fontWeight: 700, color: "#1e293b" }}>
          🤖 Coding Agent
        </h1>
        <p style={{ margin: "4px 0 0", fontSize: 14, color: "#64748b" }}>
          LLM-based multi-agent system for software engineering tasks
        </p>
      </header>

      <section style={{ marginBottom: 24 }}>
        <TaskInput onSubmit={handleStart} disabled={isActive} />
      </section>

      {apiError && (
        <div style={{ background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 6, padding: "10px 14px", marginBottom: 16, color: "#991b1b", fontSize: 13 }}>
          {apiError}
        </div>
      )}

      {runId && (
        <>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
            <RunStatus status={stream.status} />
            <span style={{ fontSize: 12, color: "#94a3b8", fontFamily: "monospace" }}>
              {runId}
            </span>
            {!isActive && (
              <button
                onClick={handleReset}
                style={{ marginLeft: "auto", fontSize: 12, padding: "3px 10px", borderRadius: 4, border: "1px solid #d1d5db", background: "#f9fafb", cursor: "pointer" }}
              >
                New run
              </button>
            )}
          </div>

          {stream.approvals.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <ApprovalPanel
                approvals={stream.approvals}
                onSubmit={handleResume}
                disabled={stream.status !== "awaiting_approval"}
              />
            </div>
          )}

          <EventStream events={stream.events} />

          {stream.output && (
            <div style={{ marginTop: 16, background: "#f0fdf4", border: "1px solid #86efac", borderRadius: 8, padding: "12px 16px" }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: "#166534", marginBottom: 6 }}>Output</div>
              <pre style={{ margin: 0, fontSize: 13, whiteSpace: "pre-wrap", color: "#15803d" }}>{stream.output}</pre>
            </div>
          )}
        </>
      )}
    </div>
  );
}
