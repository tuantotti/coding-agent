import { useRef, useState } from "react";

interface Props {
  onSubmit: (task: string, sourceFolder: string) => void;
  disabled: boolean;
  defaultFolder?: string;
}

export function TaskBar({ onSubmit, disabled, defaultFolder = "." }: Props) {
  const [task, setTask] = useState("");
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
    // Try File System Access API first (Chrome/Edge, gives folder name as hint)
    if ("showDirectoryPicker" in window) {
      try {
        const handle = await (window as unknown as {
          showDirectoryPicker: () => Promise<{ name: string }>;
        }).showDirectoryPicker();
        // Browser can't reveal absolute path — fill name as hint, user edits if needed
        setFolder((prev) => {
          const base = prev.replace(/[^/\\]+$/, "").replace(/[/\\]$/, "");
          return base ? `${base}/${handle.name}` : handle.name;
        });
      } catch {
        /* user cancelled */
      }
    } else {
      // Fallback: native file input (shows folder name from first file)
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

  return (
    <div className="taskbar-wrap">
      {/* Folder row */}
      <div className="taskbar-folder">
        <span className="taskbar-folder-icon">📁</span>
        <input
          className="taskbar-folder-path"
          type="text"
          value={folder}
          onChange={(e) => setFolder(e.target.value)}
          placeholder="/absolute/path/to/your/project"
          disabled={disabled}
        />
        <button
          className="taskbar-browse-btn"
          onClick={handleBrowse}
          disabled={disabled}
          type="button"
          title="Browse for folder"
        >
          Browse…
        </button>
        {/* Hidden fallback input */}
        <input
          ref={fileInputRef}
          type="file"
          style={{ display: "none" }}
          // @ts-expect-error webkitdirectory is non-standard
          webkitdirectory=""
          onChange={handleFileInput}
        />
      </div>

      {/* Task input row */}
      <div className="taskbar-input-row">
        <textarea
          ref={textareaRef}
          className="taskbar-textarea"
          value={task}
          onChange={(e) => { setTask(e.target.value); autoResize(); }}
          onKeyDown={handleKeyDown}
          placeholder="Describe your coding task… (⌘↵ to send)"
          rows={1}
          disabled={disabled}
        />
        <button
          className="taskbar-send-btn"
          onClick={handleSubmit}
          disabled={disabled || !task.trim()}
          title="Send (⌘↵)"
        >
          ➤
        </button>
      </div>
    </div>
  );
}
