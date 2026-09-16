import { useState } from "react";

interface Props {
  onSubmit: (task: string, sourceFolder: string) => void;
  disabled: boolean;
}

export function TaskInput({ onSubmit, disabled }: Props) {
  const [task, setTask] = useState("");
  const [folder, setFolder] = useState(".");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!task.trim()) return;
    onSubmit(task.trim(), folder.trim() || ".");
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <label style={labelStyle}>Task</label>
        <textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          disabled={disabled}
          rows={4}
          placeholder="Describe the coding task…"
          style={{ ...inputStyle, resize: "vertical" }}
        />
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        <label style={labelStyle}>Source folder</label>
        <input
          type="text"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
          disabled={disabled}
          placeholder="."
          style={inputStyle}
        />
      </div>

      <button
        type="submit"
        disabled={disabled || !task.trim()}
        style={{
          padding: "8px 20px",
          borderRadius: 6,
          background: disabled ? "#94a3b8" : "#2563eb",
          color: "#fff",
          fontWeight: 600,
          fontSize: 14,
          border: "none",
          cursor: disabled ? "not-allowed" : "pointer",
          alignSelf: "flex-end",
        }}
      >
        {disabled ? "Running…" : "Start"}
      </button>
    </form>
  );
}

const labelStyle: React.CSSProperties = {
  fontSize: 13,
  fontWeight: 600,
  color: "#374151",
};

const inputStyle: React.CSSProperties = {
  padding: "8px 10px",
  borderRadius: 6,
  border: "1px solid #d1d5db",
  fontSize: 14,
  fontFamily: "inherit",
  outline: "none",
};
