import { useEffect, useRef } from "react";
import type { StreamEvent } from "../hooks/useRunStream";
import type { Message } from "./MessageBubble";
import { MessageBubble } from "./MessageBubble";

export interface ChatTurn {
  task: string;
  events: StreamEvent[];
}

interface Props {
  sourceFolder: string | null;
  turns: ChatTurn[];
}

const AGENT_META: Record<string, { emoji: string; color: string; label: string }> = {
  requirement_analyst:   { emoji: "📋", color: "#8b5cf6", label: "Requirement Analyst" },
  programmer:            { emoji: "💻", color: "#2563eb", label: "Programmer" },
  tester:                { emoji: "🧪", color: "#16a34a", label: "Tester" },
  reviewer:              { emoji: "🔍", color: "#d97706", label: "Reviewer" },
  information_retriever: { emoji: "🔎", color: "#0891b2", label: "Retriever" },
  coordinator:           { emoji: "🤖", color: "#7c6af5", label: "Coordinator" },
  coding_coordinator:    { emoji: "🤖", color: "#7c6af5", label: "Coordinator" },
  default:               { emoji: "🤖", color: "#7c6af5", label: "Agent" },
};

function turnToMessages(
  turnIndex: number,
  task: string,
  folder: string | null,
  events: StreamEvent[]
): Message[] {
  const msgs: Message[] = [];
  let idCounter = 0;

  msgs.push({
    id: `t${turnIndex}-task-${idCounter++}`,
    kind: "user",
    sender: "You",
    avatarEmoji: "👤",
    avatarColor: "var(--accent)",
    text: turnIndex === 0 && folder ? `${task}\n\n📁 ${folder}` : task,
  });

  let pendingAgentText = "";
  let pendingAgent = "coordinator";

  const flush = () => {
    if (!pendingAgentText.trim()) return;
    const meta = AGENT_META[pendingAgent] ?? AGENT_META.default;
    msgs.push({
      id: `t${turnIndex}-agent-${idCounter++}`,
      kind: "agent",
      sender: meta.label,
      avatarEmoji: meta.emoji,
      avatarColor: meta.color,
      text: pendingAgentText.trim(),
    });
    pendingAgentText = "";
  };

  const markFinalOutput = () => {
    for (let i = msgs.length - 1; i >= 0; i--) {
      if (msgs[i].kind === "agent") {
        msgs[i] = { ...msgs[i], variant: "final" };
        return;
      }
    }
  };

  for (const ev of events) {
    if (ev.event === "text_delta" || ev.event === "agent_activity") {
      const agent = (ev.agent as string | undefined) ?? "coordinator";
      if (agent !== pendingAgent) { flush(); pendingAgent = agent; }
      const chunk = String(ev.content ?? ev.delta ?? ev.message ?? ev.text ?? "");
      pendingAgentText += chunk;
    } else if (ev.event === "status") {
      flush();
      const s = String(ev.status ?? "");
      if (s === "running") {
        const meta = AGENT_META.coordinator;
        msgs.push({
          id: `t${turnIndex}-status-${idCounter++}`,
          kind: "muted",
          sender: meta.label,
          avatarEmoji: meta.emoji,
          avatarColor: meta.color,
          text: "Starting agents…",
        });
      }
    }
  }
  flush();
  if (events.some((ev) => ev.event === "completed")) markFinalOutput();
  return msgs;
}

export function ChatArea({ sourceFolder, turns }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const messages = turns.flatMap((turn, i) =>
    turnToMessages(i, turn.task, sourceFolder, turn.events)
  );

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length]);

  if (turns.length === 0) {
    return (
      <div className="chat-area">
        <div className="chat-empty">
          <div className="chat-empty-icon">🤖</div>
          <div className="chat-empty-title">Coding Agent</div>
          <div className="chat-empty-sub">
            Describe a software engineering task below.<br />
            The agent team will plan, implement, review and test it.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-area">
      {messages.map((m) => (
        <MessageBubble key={m.id} message={m} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
