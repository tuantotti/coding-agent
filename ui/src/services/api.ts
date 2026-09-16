/** Typed fetch wrapper for the Coding Agent FastAPI backend (/v1/runs). */

const BASE = import.meta.env.VITE_API_URL ?? "";

export interface Run {
  run_id: string;
  status: "queued" | "running" | "awaiting_approval" | "completed" | "failed";
  source_folder: string;
  output: string | null;
  error: string | null;
  approvals: PendingApproval[];
  created_at: string;
  updated_at: string;
}

export interface StartRunRequest {
  task: string;
  source_folder: string;
}

export interface ActionRequest {
  name: string;
  args: Record<string, unknown>;
}

export interface ReviewConfig {
  action_name: string;
  allowed_decisions: string[];
  args_schema: Record<string, unknown> | null;
}

export interface PendingApproval {
  interrupt_id: string;
  action_requests: ActionRequest[];
  review_configs: ReviewConfig[];
}

export type DecisionType = "approve" | "reject" | "edit";

export interface Decision {
  type: DecisionType;
  edited_action?: ActionRequest;
  message?: string; // optional rejection reason (for type="reject")
}

export interface ResumeRunRequest {
  decisions: Record<string, Decision[]>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(detail.detail ?? res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  startRun: (body: StartRunRequest): Promise<Run> =>
    request("/v1/runs", { method: "POST", body: JSON.stringify(body) }),

  getRun: (runId: string): Promise<Run> =>
    request(`/v1/runs/${runId}`),

  resumeRun: (runId: string, body: ResumeRunRequest): Promise<Run> =>
    request(`/v1/runs/${runId}/resume`, { method: "POST", body: JSON.stringify(body) }),

  findDir: (name: string): Promise<{ paths: string[] }> =>
    request(`/v1/system/find-dir?name=${encodeURIComponent(name)}`),
};
