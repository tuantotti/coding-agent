import {
  ClipboardList,
  Code2,
  FileSearch2,
  FlaskConical,
  Lightbulb,
  ScanSearch,
} from "lucide-react";

interface Props {
  onChipClick: (text: string) => void;
}

const CHIPS = [
  { icon: <FlaskConical size={13} />, label: "Write Tests" },
  { icon: <Lightbulb size={13} />, label: "Brainstorm" },
  { icon: <ClipboardList size={13} />, label: "Make a plan" },
];

const AGENT_CARDS = [
  {
    icon: <FileSearch2 size={16} />,
    iconBg: "rgba(139,92,246,0.15)",
    iconColor: "#a78bfa",
    action: "Analyze Requirement",
    title: "Requirement Analyst",
    desc: "Analyze requests, inspect repository context, identify ambiguity, and produce testable requirements.",
    prompt:
      "Analyze the requirements for this task only. Do not implement or modify source code: ",
  },
  {
    icon: <Code2 size={16} />,
    iconBg: "rgba(37,99,235,0.15)",
    iconColor: "#60a5fa",
    action: "Generate Code",
    title: "Programmer",
    desc: "Write focused, compatible code changes and communicate their effects clearly.",
    prompt: "Write a Python function that ",
  },
  {
    icon: <FlaskConical size={16} />,
    iconBg: "rgba(22,163,74,0.15)",
    iconColor: "#4ade80",
    action: "Run Tests",
    title: "Tester",
    desc: "Run approved checks, evaluate test-suite quality, and report mutations.",
    prompt: "Run tests and check coverage for ",
  },
  {
    icon: <ScanSearch size={16} />,
    iconBg: "rgba(217,119,6,0.15)",
    iconColor: "#fbbf24",
    action: "Review Code",
    title: "Reviewer",
    desc: "Produce evidence-based, actionable reviews. Prioritise correctness and security.",
    prompt: "Review the code in ",
  },
];

export function EmptyState({ onChipClick }: Props) {
  return (
    <>
      <div className="quick-chips">
        {CHIPS.map((c) => (
          <button
            key={c.label}
            className="quick-chip"
            onClick={() => onChipClick(c.label)}
          >
            {c.icon}
            {c.label}
          </button>
        ))}
      </div>

      <div className="agent-cards">
        {AGENT_CARDS.map((card) => (
          <div
            key={card.title}
            className="agent-card"
            onClick={() => onChipClick(card.prompt)}
          >
            <div className="agent-card-header">
              <div
                className="agent-card-icon"
                style={{
                  background: card.iconBg,
                  color: card.iconColor,
                }}
              >
                {card.icon}
              </div>

              <span className="agent-card-action">
                {card.action}
              </span>
            </div>

            <div className="agent-card-title">
              {card.title}
            </div>

            <div className="agent-card-desc">
              {card.desc}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}