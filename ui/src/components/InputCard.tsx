import { useRef, useState } from "react";

interface Props {
  onSubmit: (task: string, folder: string) => void;
  disabled: boolean;
  initialTask?: string;
  defaultFolder?: string;
  /** When true, renders inside the empty-state (centered), otherwise bottom bar */
  variant?: "center" | "bottom";
}

export function InputCard({
  onSubmit,
  disabled,
  initialTask = "",
  defaultFolder = ".",
  variant = "center",
}: Props) {
  const [task, setTask] = useState(initialTask);
  const [folder, setFolder] = useState(defaultFolder);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const autoResize = () => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  };

  const handleSubmit = () => {
    if (!task.trim() || disabled) return;
    onSubmit(task.trim(), folder.trim() || ".");
    setTask("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSubmit();
  };

  const handleBrowse = async () => {
    if ("showDirectoryPicker" in window) {
      try {
        const handle = await (
          window as unknown as { showDirectoryPicker: () => Promise<{ name: string }> }
        ).showDirectoryPicker();
        setFolder((prev) => {
          const base = prev.replace(/[^/\\]+$/, "").replace(/[/\\]$/, "");
          return base ? `${base}/${handle.name}` : handle.name;
        });
      } catch { /* cancelled */ }
    } else {
      fileInputRef.current?.click();
    }
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const parts = (file as File & { webkitRelativePath?: string }).webkitRelativePath?.split("/");
    if (parts?.[0]) setFolder(parts[0]);
    e.target.value = "";
  };

  const card = (
    <div className="input-card">
      {/* Folder row */}
      <div className="input-card-folder">
        <span className="input-card-folder-icon">📁</span>
        <input
          className="input-card-folder-path"
          type="text"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
          placeholder="/absolute/path/to/your/project"
          disabled={disabled}
        />
        <button
          className="input-card-browse"
          onClick={handleBrowse}
          disabled={disabled}
          type="button"
        >
          Browse…
        </button>
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: "none" }}
          // @ts-expect-error non-standard attr
          webkitdirectory=""
          onChange={handleFileInput}
        />
      </div>

      {/* Text row */}
      <div className="input-card-row">
        <span className="input-card-spark">✦</span>
        <textarea
          ref={textareaRef}
          className="input-card-textarea"
          value={task}
          onChange={(e) => { setTask(e.target.value); autoResize(); }}
          onKeyDown={handleKeyDown}
          placeholder="Ask Anything…"
          rows={1}
          disabled={disabled}
        />
      </div>

      {/* Toolbar */}
      <div className="input-card-toolbar">
        <div className="input-toolbar-left">
          <button className="toolbar-icon-btn" type="button">🔗 Attach</button>
          <button className="toolbar-icon-btn" type="button">⚙ Settings</button>
          <button className="toolbar-icon-btn" type="button">⊞ Options</button>
        </div>
        <div className="input-toolbar-right">
          <button
            className="send-btn"
            onClick={handleSubmit}
            disabled={disabled || !task.trim()}
            title="Send (⌘↵)"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );

  if (variant === "bottom") {
    return <div className="taskbar-wrap">{card}</div>;
  }

  return card;
}
