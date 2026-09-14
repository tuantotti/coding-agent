/**
 * useRunStream — subscribe to a run's SSE event stream.
 *
 * Reconnects automatically on connection loss using the Last-Event-ID header
 * (native EventSource behaviour). Stops when the run reaches a terminal state.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import type { PendingApproval } from "../services/api";

export type RunStatus =
  | "idle"
  | "queued"
  | "running"
  | "awaiting_approval"
  | "completed"
  | "failed";

export interface StreamEvent {
  event: string;
  run_id: string;
  timestamp: string;
  [key: string]: unknown;
}

export interface RunStreamState {
  status: RunStatus;
  events: StreamEvent[];
  approvals: PendingApproval[];
  output: string | null;
  error: string | null;
}

const TERMINAL: ReadonlySet<string> = new Set(["completed", "failed"]);

export function useRunStream(runId: string | null) {
  const [state, setState] = useState<RunStreamState>({
    status: "idle",
    events: [],
    approvals: [],
    output: null,
    error: null,
  });

  const esRef = useRef<EventSource | null>(null);

  const close = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  useEffect(() => {
    if (!runId) return;

    setState({ status: "queued", events: [], approvals: [], output: null, error: null });

    const base = import.meta.env.VITE_API_URL ?? "";
    const url = `${base}/v1/runs/${runId}/events`;
    const es = new EventSource(url);
    esRef.current = es;

    const handle = (raw: MessageEvent, eventName: string) => {
      let data: Record<string, unknown>;
      try {
        data = JSON.parse(raw.data as string) as Record<string, unknown>;
      } catch {
        return;
      }
      const ev: StreamEvent = { event: eventName, ...data } as StreamEvent;

      setState((prev) => {
        const next: RunStreamState = { ...prev, events: [...prev.events, ev] };

        if (eventName === "status" || TERMINAL.has(eventName)) {
          next.status = (data.status as RunStatus | undefined) ?? (eventName as RunStatus);
        }
        if (eventName === "approval_required") {
          next.approvals = (data.approvals as PendingApproval[]) ?? [];
        }
        if (eventName === "completed") {
          next.output = (data.output as string | null) ?? null;
          next.approvals = [];
        }
        if (eventName === "failed") {
          next.error = (data.error as string | null) ?? "Unknown error";
          next.approvals = [];
        }
        return next;
      });

      if (TERMINAL.has(eventName)) close();
    };

    for (const evt of ["status", "text", "activity", "approval_required", "completed", "failed"]) {
      es.addEventListener(evt, (e) => handle(e as MessageEvent, evt));
    }

    es.onerror = () => {
      setState((prev) =>
        TERMINAL.has(prev.status) ? prev : { ...prev, status: "failed", error: "Stream disconnected" }
      );
    };

    return close;
  }, [runId, close]);

  return { ...state, close };
}
