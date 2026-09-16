import { ArrowUp, FolderOpen, Paperclip, Settings2, LayoutGrid, Sparkles, AlertCircle, Loader2 } from "lucide-react";
import { useRef, useState } from "react";
import { api } from "../services/api";

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
  defaultFolder = "",
  variant = "center",
}: Props) {
  const [task, setTask] = useState(initialTask);
  const [folder, setFolder] = useState(defaultFolder);
  const [folderError, setFolderError] = useState("");
  const [searching, setSearching] = useState(false);
  const [pathChoices, setPathChoices] = useState<string[]>([]);
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
      setFolderError(`Must be an absolute path — e.g. /Users/yourname/${f || "project"}`);
      return;
    }
    setFolderError("");
    setPathChoices([]);
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
        const name = handle.name;

        // Ask backend to resolve the full path
        setSearching(true);
        setFolderError("");
        setPathChoices([]);
        try {
          const { paths } = await api.findDir(name);
          if (paths.length === 1) {
            setFolder(paths[0]);
          } else if (paths.length > 1) {
            setFolder(paths[0]);
            setPathChoices(paths);
          } else {
            // Not found — fill name as hint, ask user to type prefix
            setFolder(name);
            setFolderError(`Không tìm thấy "${name}" trong home directory. Nhập đường dẫn đầy đủ.`);
          }
        } finally {
          setSearching(false);
        }
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
        <span className="input-card-folder-icon">
          {searching ? <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> : <FolderOpen size={13} />}
        </span>
        <input
          className="input-card-folder-path"
          type="text"
          value={folder}
          onChange={(e) => { setFolder(e.target.value); setFolderError(""); setPathChoices([]); }}
          placeholder="/absolute/path/to/your/project"
          disabled={disabled || searching}
          style={folderError ? { color: "#f87171" } : {}}
        />
        <button className="input-card-browse" onClick={handleBrowse} disabled={disabled || searching} type="button">
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

      {/* Multiple matches — let user pick */}
      {pathChoices.length > 1 && (
        <div style={{ fontSize: 11, padding: "4px 4px 2px" }}>
          <span style={{ color: "var(--text-faint)", marginBottom: 4, display: "block" }}>
            Tìm thấy {pathChoices.length} thư mục — chọn một:
          </span>
          {pathChoices.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => { setFolder(p); setPathChoices([]); }}
              style={{
                display: "block", width: "100%", textAlign: "left",
                padding: "3px 8px", borderRadius: 5, border: "none",
                background: folder === p ? "var(--accent-light)" : "transparent",
                color: folder === p ? "var(--accent-text)" : "var(--text-muted)",
                fontFamily: "monospace", fontSize: 11, cursor: "pointer",
                marginBottom: 2,
              }}
            >
              {p}
            </button>
          ))}
        </div>
      )}

      {/* Validation error */}
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
            disabled={disabled || !task.trim() || searching}
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
