import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type MessageKind = "user" | "agent" | "muted" | "system";

export interface Message {
  id: string;
  kind: MessageKind;
  sender: string;
  avatarEmoji: string;
  avatarColor: string;
  text: string;
}

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const { kind, sender, avatarEmoji, avatarColor, text } = message;
  const isMarkdown = kind === "agent";

  return (
    <div className={`message-row ${kind === "user" ? "user" : "agent"}${kind === "muted" ? " muted" : ""}`}>
      {kind !== "user" && (
        <div
          className="message-avatar"
          style={{ background: avatarColor, color: "#fff" }}
          title={sender}
        >
          {avatarEmoji}
        </div>
      )}

      <div className="message-content">
        <div className="message-sender">{sender}</div>
        <div className={`message-bubble${isMarkdown ? "" : " plain"}`}>
          {isMarkdown ? (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
            </div>
          ) : (
            text
          )}
        </div>
      </div>

      {kind === "user" && (
        <div
          className="message-avatar"
          style={{ background: "var(--accent)", color: "#fff" }}
        >
          👤
        </div>
      )}
    </div>
  );
}
