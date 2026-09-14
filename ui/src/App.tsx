import { useState } from "react";
import { ApprovalCard } from "./components/ApprovalCard";
import { ChatArea } from "./components/ChatArea";
import { EmptyState } from "./components/EmptyState";
import { InputCard } from "./components/InputCard";
import { RunStatusBadge } from "./components/RunStatusBadge";
import { Sidebar, type RunSummary } from "./components/Sidebar";
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
  const [prefill, setPrefill] = useState("");

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
      const record: RunRecord = { run_id: run.run_id, task, sourceFolder, startedAt: new Date() };
      setRuns((prev) => [record, ...prev]);
      setActiveRunId(run.run_id);
      setPrefill("");
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Failed to start run");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResume = async (req: ResumeRunRequest) => {
    if (!activeRunId) return;
    setApiError(null);
    try { await api.resumeRun(activeRunId, req); }
    catch (e) { setApiError(e instanceof Error ? e.message : "Failed to submit"); }
  };

  const handleNewRun = () => {
    setActiveRunId(null);
    setApiError(null);
    setPrefill("");
    stream.close();
  };

  const handleChipClick = (text: string) => {
    setPrefill(text);
  };

  const sidebarRuns: RunSummary[] = runs.map((r) => ({
    run_id: r.run_id,
    label: r.task.length > 34 ? r.task.slice(0, 34) + "…" : r.task,
    status: r.run_id === activeRunId ? stream.status : "idle",
    time: relativeTime(r.startedAt),
  }));

  const hasActiveRun = !!activeRun;

  return (
    <div className="app-shell">
      <Sidebar
        runs={sidebarRuns}
        activeRunId={activeRunId}
        onSelect={setActiveRunId}
        onNewRun={handleNewRun}
      />

      <div className="main-area">
        {/* Topbar */}
        <div className="topbar">
          <div className="topbar-left">
            <div className="model-chip">
              <span className="model-chip-dot" />
              GPT-5.4 nano
              <span style={{ color: "var(--text-faint)", fontSize: 11 }}>▾</span>
            </div>
            {hasActiveRun && (
              <div className="topbar-status">
                <RunStatusBadge status={stream.status} />
              </div>
            )}
          </div>
          <div className="topbar-right">
            <button className="topbar-btn">⚙ Configuration</button>
            <button className="topbar-btn">↑ Export</button>
          </div>
        </div>

        {/* Error */}
        {apiError && (
          <div className="error-toast"><span>⚠</span>{apiError}</div>
        )}

        {/* Content */}
        {!hasActiveRun ? (
          /* ── Empty state: orb + chips + input + agent cards ── */
          <div className="empty-state">
            <div className="orb" />
            <div className="empty-heading">Ready to Code Something New?</div>

            <EmptyState onChipClick={handleChipClick} />

            <div style={{ width: "100%", maxWidth: 740 }}>
              <InputCard
                onSubmit={handleStart}
                disabled={isRunning}
                initialTask={prefill}
                variant="center"
              />
            </div>
          </div>
        ) : (
          /* ── Active run: chat + approval + input bar ── */
          <>
            <ChatArea
              task={activeRun.task}
              sourceFolder={activeRun.sourceFolder}
              events={stream.events}
            />

            {stream.approvals.length > 0 && (
              <div style={{ padding: "0 24px 10px" }}>
                <ApprovalCard
                  approvals={stream.approvals}
                  onSubmit={handleResume}
                  disabled={stream.status !== "awaiting_approval"}
                />
              </div>
            )}

            {stream.output && (
              <div className="output-card">
                <div className="output-card-title">✅ Final output</div>
                <pre>{stream.output}</pre>
              </div>
            )}

            <InputCard
              onSubmit={handleStart}
              disabled={isRunning}
              defaultFolder={activeRun.sourceFolder}
              variant="bottom"
            />
          </>
        )}
      </div>
    </div>
  );
}
