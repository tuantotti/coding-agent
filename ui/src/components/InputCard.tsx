import { ArrowUp, FolderOpen, Paperclip, Settings2, LayoutGrid, Sparkles, AlertCircle } from "lucide-react";
import { useRef, useState } from "react";

interface Props {
  onSubmit: (task: string, folder: string) => void;
  disabled: boolean;
  initialTask?: string;
  defaultFolder?: string;
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
  const [folderError, setFolderError] = useState("");
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
    const f = folder.trim();
    if (!f.startsWith("/")) {
      setFolderError("Must be an absolute path (e.g. /Users/you/project)");
      return;
    }
    setFolderError("");
    onSubmit(task.trim(), f);
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
        <span className="input-card-folder-icon"><FolderOpen size={13} /></span>
        <input
          className="input-card-folder-path"
          type="text"
          value={folder}
          onChange={(e) => { setFolder(e.target.value); setFolderError(""); }}
          placeholder="/absolute/path/to/your/project"
          disabled={disabled}
          style={folderError ? { color: "#f87171" } : {}}
        />
        <button className="input-card-browse" onClick={handleBrowse} disabled={disabled} type="button">
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

      {folderError && (
        <div style={{ fontSize: 11, color: "#f87171", padding: "2px 4px 4px", display: "flex", alignItems: "center", gap: 4 }}>
          <AlertCircle size={11} /> {folderError}
        </div>
      )}

      {/* Text row */}
      <div className="input-card-row">
        <span className="input-card-spark"><Sparkles size={15} /></span>
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
          <button className="toolbar-icon-btn" type="button"><Paperclip size={13} /> Attach</button>
          <button className="toolbar-icon-btn" type="button"><Settings2 size={13} /> Settings</button>
          <button className="toolbar-icon-btn" type="button"><LayoutGrid size={13} /> Options</button>
        </div>
        <div className="input-toolbar-right">
          <button
            className="send-btn"
            onClick={handleSubmit}
            disabled={disabled || !task.trim()}
            title="Send (⌘↵)"
          >
            <ArrowUp size={15} />
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
