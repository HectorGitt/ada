"use client";

import { Loader2, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui";
import { type IntroMessage } from "@/lib/api";

/** The in-app conversation for an accepted intro. Same component on both sides; `me` marks
 *  which bubbles are mine. Polls for new messages while open. */
export function IntroThread({
  introId,
  me,
  fetchThread,
  send,
}: {
  introId: string;
  me: "employer" | "candidate";
  fetchThread: (id: string) => Promise<IntroMessage[]>;
  send: (id: string, body: string) => Promise<IntroMessage>;
}) {
  const [messages, setMessages] = useState<IntroMessage[] | null>(null);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const load = useCallback(() => {
    fetchThread(introId).then(setMessages).catch(() => setMessages([]));
  }, [introId, fetchThread]);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const body = draft.trim();
    if (!body || sending) return;
    setSending(true);
    // Optimistic append.
    const optimistic: IntroMessage = { sender: me, body, created_at: new Date().toISOString() };
    setMessages((m) => [...(m ?? []), optimistic]);
    setDraft("");
    try {
      await send(introId, body);
      load();
    } catch {
      // revert the optimistic message on failure
      setMessages((m) => (m ?? []).filter((x) => x !== optimistic));
      setDraft(body);
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="mt-3 rounded-2xl border border-line bg-surface-2/50">
      <div className="max-h-72 space-y-2 overflow-y-auto p-3">
        {messages === null ? (
          <p className="flex items-center gap-2 p-2 text-xs text-muted">
            <Loader2 className="size-3.5 animate-spin" /> Loading…
          </p>
        ) : messages.length === 0 ? (
          <p className="p-2 text-xs text-muted">
            You&apos;re connected — say hello to start the conversation.
          </p>
        ) : (
          messages.map((m, i) => {
            const mine = m.sender === me;
            return (
              <div key={i} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                    mine ? "bg-accent text-accent-ink" : "bg-surface text-ink"
                  }`}
                >
                  {m.body}
                </div>
              </div>
            );
          })
        )}
        <div ref={endRef} />
      </div>
      <form onSubmit={submit} className="flex items-center gap-2 border-t border-line p-2">
        <input
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="Write a message…"
          className="flex-1 rounded-xl border border-line bg-surface px-3 py-2 text-sm outline-none focus:border-accent"
        />
        <Button type="submit" disabled={!draft.trim() || sending} className="!px-3 !py-2">
          {sending ? <Loader2 className="size-4 animate-spin" /> : <Send className="size-4" />}
        </Button>
      </form>
    </div>
  );
}
