import { FormEvent, useEffect, useRef, useState } from "react";
import { api } from "../api";

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
};

type StartResponse = {
  conversationId: string;
  messageId: string;
  status: string;
};

type PollResponse = {
  status: string;
  text: string | null;
  done: boolean;
  error: string | null;
};

export default function AskGenieChat({
  team,
  season,
}: {
  team: string;
  season: number;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setMessages([]);
    setConversationId(null);
    setInput("");
    setError(null);
    setBusy(false);
  }, [team, season]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  async function pollUntilDone(convId: string, messageId: string) {
    for (let i = 0; i < 120; i++) {
      const poll = await api<PollResponse>(
        `/api/genie/chat/${encodeURIComponent(convId)}/messages/${encodeURIComponent(messageId)}`
      );
      if (poll.done) {
        if (poll.error) throw new Error(poll.error);
        return poll.text || "No answer returned.";
      }
      await new Promise((r) => setTimeout(r, 2500));
    }
    throw new Error("Genie timed out");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    const question = input.trim();
    if (!question || busy) return;

    setBusy(true);
    setError(null);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);

    try {
      const started = await api<StartResponse>("/api/genie/chat", {
        method: "POST",
        body: JSON.stringify({
          question,
          conversationId,
          team,
          season,
        }),
      });
      setConversationId(started.conversationId);
      const answer = await pollUntilDone(started.conversationId, started.messageId);
      setMessages((prev) => [...prev, { role: "assistant", text: answer }]);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Ask Genie failed";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: `Sorry - ${msg}` },
      ]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="section">
      <h2>Ask Genie</h2>
      <p className="lede">
        Ask questions about {team}&apos;s {season} season preview data.
      </p>
      <div className="card genie-chat">
        <div className="genie-chat-log">
          {messages.length === 0 && (
            <p className="meta" style={{ margin: 0 }}>
              Example: How transfer-dependent is the offense? Who are the biggest portal arrivals?
            </p>
          )}
          {messages.map((m, i) => (
            <div key={i} className={`genie-bubble ${m.role}`}>
              <div className="genie-bubble-role">
                {m.role === "user" ? "You" : "Genie"}
              </div>
              <p>{m.text}</p>
            </div>
          ))}
          {busy && <p className="meta">Genie is thinking…</p>}
          <div ref={bottomRef} />
        </div>
        <form className="genie-chat-form" onSubmit={onSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Ask about ${team}…`}
            disabled={busy}
            aria-label="Ask Genie"
          />
          <button type="submit" disabled={busy || !input.trim()}>
            Send
          </button>
        </form>
        {error && <p className="meta" style={{ marginTop: "0.5rem" }}>{error}</p>}
      </div>
    </section>
  );
}
