import { useEffect, useRef } from "react";
import type { StreamEvent } from "../hooks/useRunStream";

interface Props {
  events: StreamEvent[];
}

function formatEvent(ev: StreamEvent): string {
  if (ev.event === "text" || ev.event === "activity") {
    const content = ev.content ?? ev.message ?? ev.text ?? "";
    return String(content);
  }
  if (ev.event === "status") return `[status] ${String(ev.status ?? "")}`;
  if (ev.event === "approval_required") return "[approval required]";
  if (ev.event === "completed") return "[completed]";
  if (ev.event === "failed") return `[failed] ${String(ev.error ?? "")}`;
  return `[${ev.event}]`;
}

export function EventStream({ events }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <div
      style={{
        background: "#0f172a",
        color: "#e2e8f0",
        fontFamily: "monospace",
        fontSize: 13,
        lineHeight: 1.6,
        padding: "12px 16px",
        borderRadius: 8,
        minHeight: 200,
        maxHeight: 480,
        overflowY: "auto",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {events.length === 0 ? (
        <span style={{ color: "#64748b" }}>Waiting for events…</span>
      ) : (
        events.map((ev, i) => {
          const text = formatEvent(ev);
          if (!text) return null;
          const isError = ev.event === "failed";
          return (
            <div key={i} style={{ color: isError ? "#f87171" : "inherit" }}>
              {text}
            </div>
          );
        })
      )}
      <div ref={bottomRef} />
    </div>
  );
}
