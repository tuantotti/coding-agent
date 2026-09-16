import { useState } from "react";
import type { Decision, PendingApproval, ResumeRunRequest } from "../services/api";

interface Props {
  approvals: PendingApproval[];
  onSubmit: (req: ResumeRunRequest) => void;
  disabled: boolean;
}

export function ApprovalCard({ approvals, onSubmit, disabled }: Props) {
  const [decisions, setDecisions] = useState<Record<string, Decision[]>>(() =>
    Object.fromEntries(
      approvals.map((a) => [
        a.interrupt_id,
        a.action_requests.map(() => ({ type: "approve" as const })),
      ])
    )
  );

  if (approvals.length === 0) return null;

  const setDecision = (interruptId: string, idx: number, type: Decision["type"]) => {
    setDecisions((prev) => {
      const copy = [...(prev[interruptId] ?? [])];
      copy[idx] = { type };
      return { ...prev, [interruptId]: copy };
    });
  };

  const handleSubmit = () => {
    const built: Record<string, Decision[]> = {};
    for (const approval of approvals) {
      built[approval.interrupt_id] =
        decisions[approval.interrupt_id] ??
        approval.action_requests.map(() => ({ type: "approve" }));
    }
    onSubmit({ decisions: built });
  };

  return (
    <div className="approval-card">
      <div className="approval-header">
        <span>⚠️</span>
        <span>Action requires your approval</span>
      </div>

      {approvals.map((approval) =>
        approval.action_requests.map((action, idx) => {
          const current = decisions[approval.interrupt_id]?.[idx]?.type ?? "approve";
          return (
            <div className="approval-action" key={`${approval.interrupt_id}-${idx}`}>
              <div className="approval-action-name">
                <span>🔧</span>
                <code>{action.name}</code>
              </div>
              <pre className="approval-action-args">
                {JSON.stringify(action.args, null, 2)}
              </pre>
              <div className="approval-btns">
                <button
                  className={`approval-btn approve`}
                  style={{ opacity: current === "approve" ? 1 : 0.45 }}
                  onClick={() => setDecision(approval.interrupt_id, idx, "approve")}
                  disabled={disabled}
                >
                  ✅ Approve
                </button>
                <button
                  className={`approval-btn deny`}
                  style={{ opacity: current === "reject" ? 1 : 0.45 }}
                  onClick={() => setDecision(approval.interrupt_id, idx, "reject")}
                  disabled={disabled}
                >
                  ❌ Reject
                </button>
              </div>
            </div>
          );
        })
      )}

      <button className="approval-submit" onClick={handleSubmit} disabled={disabled}>
        Submit decisions →
      </button>
    </div>
  );
}
