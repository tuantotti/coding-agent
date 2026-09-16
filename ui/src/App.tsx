import { Settings, Upload, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { ApprovalCard } from "./components/ApprovalCard";
import { ChatArea, type ChatTurn } from "./components/ChatArea";
import { EmptyState } from "./components/EmptyState";
import { InputCard } from "./components/InputCard";
import { RunStatusBadge } from "./components/RunStatusBadge";
import { Sidebar, type RunSummary } from "./components/Sidebar";
import { useRunStream, type StreamEvent } from "./hooks/useRunStream";
import { api } from "./services/api";
import type { ResumeRunRequest } from "./services/api";

interface TurnRecord {
  run_id: string;
  task: string;
  startedAt: Date;
}

interface ConversationRecord {
  id: string;
  sourceFolder: string;
  turns: TurnRecord[];
}

function relativeTime(d: Date): string {
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  return `${Math.floor(s / 3600)}h ago`;
}

function normalizeFolder(f: string): string {
  return f.trim().replace(/\/+$/, "");
}

export function App() {
  const [conversations, setConversations] = useState<ConversationRecord[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [eventsCache, setEventsCache] = useState<Record<string, StreamEvent[]>>({});
  const [apiError, setApiError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [prefill, setPrefill] = useState("");

  const activeConversation = conversations.find((c) => c.id === activeConversationId) ?? null;
  const latestTurn = activeConversation
    ? activeConversation.turns[activeConversation.turns.length - 1]
    : null;
  const liveRunId = latestTurn?.run_id ?? null;
  const stream = useRunStream(liveRunId);

  // Cache each run's events as they stream in, so switching away and back
  // (or appending a new turn) doesn't lose earlier turns' transcripts.
  useEffect(() => {
    if (!liveRunId) return;
    setEventsCache((prev) => ({ ...prev, [liveRunId]: stream.events }));
  }, [liveRunId, stream.events]);

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
      const turn: TurnRecord = { run_id: run.run_id, task, startedAt: new Date() };
      const normalized = normalizeFolder(sourceFolder);
      const existing = conversations.find((c) => normalizeFolder(c.sourceFolder) === normalized);

      if (existing) {
        setConversations((prev) => [
          { ...existing, turns: [...existing.turns, turn] },
          ...prev.filter((c) => c.id !== existing.id),
        ]);
        setActiveConversationId(existing.id);
      } else {
        const conv: ConversationRecord = { id: run.run_id, sourceFolder, turns: [turn] };
        setConversations((prev) => [conv, ...prev]);
        setActiveConversationId(conv.id);
      }
      setPrefill("");
    } catch (e) {
      setApiError(e instanceof Error ? e.message : "Failed to start run");
    } finally {
      setSubmitting(false);
    }
  };

  const handleResume = async (req: ResumeRunRequest) => {
    if (!liveRunId) return;
    setApiError(null);
    try { await api.resumeRun(liveRunId, req); }
    catch (e) { setApiError(e instanceof Error ? e.message : "Failed to submit"); }
  };

  const handleNewRun = () => {
    setActiveConversationId(null);
    setApiError(null);
    setPrefill("");
    stream.close();
  };

  const handleChipClick = (text: string) => {
    setPrefill(text);
  };

  const sidebarRuns: RunSummary[] = conversations.map((c) => {
    const last = c.turns[c.turns.length - 1];
    return {
      run_id: c.id,
      label: last.task.length > 34 ? last.task.slice(0, 34) + "…" : last.task,
      status: c.id === activeConversationId ? stream.status : "idle",
      time: relativeTime(last.startedAt),
    };
  });

  const hasActiveRun = !!activeConversation;
  const chatTurns: ChatTurn[] = activeConversation
    ? activeConversation.turns.map((t) => ({
        task: t.task,
        events: t.run_id === liveRunId ? stream.events : (eventsCache[t.run_id] ?? []),
      }))
    : [];

  return (
    <div className="app-shell">
      <Sidebar
        runs={sidebarRuns}
        activeRunId={activeConversationId}
        onSelect={setActiveConversationId}
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
            <button className="topbar-btn"><Settings size={13} /> Configuration</button>
            <button className="topbar-btn"><Upload size={13} /> Export</button>
          </div>
        </div>

        {/* Error */}
        {apiError && (
          <div className="error-toast"><TriangleAlert size={14} />{apiError}</div>
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
              sourceFolder={activeConversation.sourceFolder}
              turns={chatTurns}
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

            <InputCard
              onSubmit={handleStart}
              disabled={isRunning}
              defaultFolder={activeConversation.sourceFolder}
              variant="bottom"
            />
          </>
        )}
      </div>
    </div>
  );
}
