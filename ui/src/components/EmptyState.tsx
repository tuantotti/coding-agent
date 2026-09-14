interface Props {
  onChipClick: (text: string) => void;
}

const CHIPS = [
  { icon: "🧪", label: "Write Tests" },
  { icon: "💡", label: "Brainstorm" },
  { icon: "📋", label: "Make a plan" },
];

const AGENT_CARDS = [
  {
    icon: "💻", color: "#2563eb", action: "Generate Code",
    title: "Programmer",
    desc: "Write focused, compatible code changes and communicate their effects clearly.",
    prompt: "Write a Python function that ",
  },
  {
    icon: "🧪", color: "#16a34a", action: "Run Tests",
    title: "Tester",
    desc: "Run approved checks, evaluate test-suite quality, and report mutations.",
    prompt: "Run tests and check coverage for ",
  },
  {
    icon: "🔍", color: "#d97706", action: "Review Code",
    title: "Reviewer",
    desc: "Produce evidence-based, actionable reviews. Prioritise correctness and security.",
    prompt: "Review the code in ",
  },
];

/** Quick chips + agent cards — rendered inside empty state below the input */
export function EmptyState({ onChipClick }: Props) {
  return (
    <>
      <div className="quick-chips">
        {CHIPS.map((c) => (
          <button key={c.label} className="quick-chip" onClick={() => onChipClick(c.label)}>
            <span>{c.icon}</span>
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
              <div className="agent-card-icon" style={{ background: `${card.color}22`, color: card.color }}>
                {card.icon}
              </div>
              <span className="agent-card-action">{card.action}</span>
            </div>
            <div className="agent-card-title">{card.title}</div>
            <div className="agent-card-desc">{card.desc}</div>
          </div>
        ))}
      </div>
    </>
  );
}
