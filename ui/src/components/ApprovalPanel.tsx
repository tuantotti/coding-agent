import { useState } from "react";
import type { Decision, PendingApproval, ResumeRunRequest } from "../services/api";

interface Props {
  approvals: PendingApproval[];
  onSubmit: (req: ResumeRunRequest) => void;
  disabled: boolean;
}

export function ApprovalPanel({ approvals, onSubmit, disabled }: Props) {
  const [decisions, setDecisions] = useState<Record<string, Decision[]>>(() =>
    Object.fromEntries(
      approvals.map((a) => [a.interrupt_id, a.action_requests.map(() => ({ type: "approve" as const }))])
    )
  );

  if (approvals.length === 0) return null;

  const setDecision = (interruptId: string, idx: number, type: Decision["type"]) => {
    setDecisions((prev) => {
      const copy = prev[interruptId] ? [...prev[interruptId]] : [];
      copy[idx] = { ...copy[idx], type };
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
    <div
      style={{
        border: "2px solid #7c3aed",
        borderRadius: 8,
        padding: 16,
        background: "#faf5ff",
      }}
    >
      <h3 style={{ margin: "0 0 12px", color: "#6d28d9", fontSize: 15 }}>
        👀 Approval required
      </h3>

      {approvals.map((approval) => (
        <div key={approval.interrupt_id} style={{ marginBottom: 16 }}>
          {approval.action_requests.map((action, idx) => (
            <div
              key={idx}
              style={{
                background: "#fff",
                border: "1px solid #e9d5ff",
                borderRadius: 6,
                padding: 12,
                marginBottom: 8,
              }}
            >
              <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 6 }}>
                🔧 {action.name}
              </div>
              <pre
                style={{
                  background: "#f1f5f9",
                  borderRadius: 4,
                  padding: "6px 10px",
                  fontSize: 12,
                  overflowX: "auto",
                  margin: "0 0 10px",
                }}
              >
                {JSON.stringify(action.args, null, 2)}
              </pre>

              <div style={{ display: "flex", gap: 8 }}>
                {(["approve", "deny"] as const).map((type) => {
                  const current = decisions[approval.interrupt_id]?.[idx]?.type;
                  const active = current === type;
                  return (
                    <button
                      key={type}
                      onClick={() => setDecision(approval.interrupt_id, idx, type)}
                      disabled={disabled}
                      style={{
                        padding: "4px 14px",
                        borderRadius: 4,
                        border: "none",
                        fontWeight: 600,
                        fontSize: 13,
                        cursor: disabled ? "not-allowed" : "pointer",
                        background: active
                          ? type === "approve"
                            ? "#16a34a"
                            : "#dc2626"
                          : "#e2e8f0",
                        color: active ? "#fff" : "#374151",
                      }}
                    >
                      {type === "approve" ? "✅ Approve" : "❌ Deny"}
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      ))}

      <button
        onClick={handleSubmit}
        disabled={disabled}
        style={{
          padding: "8px 20px",
          background: disabled ? "#94a3b8" : "#7c3aed",
          color: "#fff",
          border: "none",
          borderRadius: 6,
          fontWeight: 700,
          fontSize: 14,
          cursor: disabled ? "not-allowed" : "pointer",
        }}
      >
        Submit decisions
      </button>
    </div>
  );
}
