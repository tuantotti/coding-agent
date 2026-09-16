import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export type MessageKind = "user" | "agent" | "muted" | "system";
export type MessageVariant = "final";

export interface Message {
  id: string;
  kind: MessageKind;
  sender: string;
  avatarEmoji: string;
  avatarColor: string;
  text: string;
  variant?: MessageVariant;
}

interface Props {
  message: Message;
}

export function MessageBubble({ message }: Props) {
  const { kind, sender, avatarEmoji, avatarColor, text, variant } = message;
  const isMarkdown = kind === "agent";
  const isFinal = variant === "final";

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
        <div className={`message-bubble${isMarkdown ? "" : " plain"}${isFinal ? " output-card" : ""}`}>
          {isFinal && <div className="output-card-title">✅ Final output</div>}
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
