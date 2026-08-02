"use client";

import { ArrowUp, Eraser, Mic, Square } from "lucide-react";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

import { api, streamChat, type ChatMessage } from "@/lib/api";

const SUGGESTIONS = [
  "Review my career trajectory",
  "What roles should I target next?",
  "How do I switch industries without starting over?",
  "Help me plan a salary negotiation",
];

function AdaMark() {
  return (
    <span className="display mt-0.5 flex size-7 shrink-0 select-none items-center justify-center rounded-full bg-accent-soft text-[13px] text-accent">
      A
    </span>
  );
}

/** Detect when the user is asking to speak with Ada or to practice an interview,
 *  so we can offer a voice call inline instead of making them find the page. */
function detectVoiceCue(text: string): "conversation" | "interview" | null {
  const t = text.toLowerCase();
  const wantsInterview =
    /\b(interview|mock|grill me|rehearse)\b/.test(t) ||
    (/\bpractice\b/.test(t) && /\b(question|answer|role|job|interview)\b/.test(t));
  if (wantsInterview) return "interview";
  const wantsVoice =
    /\b(voice|out ?loud|speak|call)\b/.test(t) ||
    /\b(talk|say) (it|this|that|to you|it through)\b/.test(t) ||
    /\b(hop on|jump on|get on) a? ?call\b/.test(t);
  return wantsVoice ? "conversation" : null;
}

function VoiceCue({ mode }: { mode: "conversation" | "interview" }) {
  const interview = mode === "interview";
  return (
    <div className="flex gap-3">
      <AdaMark />
      <Link
        href={interview ? "/app/voice?mode=interview" : "/app/voice"}
        className="group flex max-w-[88%] items-center gap-3.5 rounded-2xl rounded-tl-md border border-accent/30 bg-accent-soft/50 px-4 py-3 transition-colors hover:border-accent"
      >
        <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink">
          <Mic className="size-4" />
        </span>
        <span className="min-w-0">
          <span className="block text-sm font-medium">
            {interview ? "Practice out loud with a mock interview" : "Talk it through with Ada"}
          </span>
          <span className="block text-xs text-muted">
            {interview
              ? "A live spoken interview for your target role — tap to start."
              : "Skip the typing — have a real voice conversation. Tap to start."}
          </span>
        </span>
        <ArrowUp className="size-4 shrink-0 rotate-45 text-muted transition-transform group-hover:translate-x-0.5" />
      </Link>
    </div>
  );
}

export default function CoachPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [hasProfile, setHasProfile] = useState<boolean | null>(null);
  const [runsCount, setRunsCount] = useState<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getProfile().then((p) => setHasProfile(p !== null)).catch(() => setHasProfile(false));
    api
      .listRuns()
      .then((rs) => setRunsCount(rs.filter((r) => r.status === "complete").length))
      .catch(() => setRunsCount(null));
  }, []);

  // Restore the saved conversation, then handle a question handed over from the
  // dashboard's "Ask Ada anything" box (in that order, so the send builds on history).
  const restored = useRef(false);
  useEffect(() => {
    if (restored.current) return;
    restored.current = true;
    void (async () => {
      let history: ChatMessage[] = [];
      try {
        history = await api.chatHistory();
        if (history.length) setMessages(history);
      } catch {
        /* fresh conversation */
      }
      const q = localStorage.getItem("ada.coach-ask");
      if (q) {
        localStorage.removeItem("ada.coach-ask");
        void send(q, history);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const clear = async () => {
    setMessages([]);
    try {
      await api.clearChatHistory();
    } catch {
      /* server copy survives; page reload restores it */
    }
  };

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text: string, base?: ChatMessage[]) => {
    const content = text.trim();
    if (!content || streaming) return;
    setInput("");
    const history: ChatMessage[] = [...(base ?? messages), { role: "user", content }];
    setMessages([...history, { role: "assistant", content: "" }]);
    setStreaming(true);
    abortRef.current = new AbortController();
    try {
      await streamChat(
        history,
        (delta) =>
          setMessages((prev) => {
            const next = [...prev];
            const lastIndex = next.length - 1;
            next[lastIndex] = {
              role: "assistant",
              content: next[lastIndex].content + delta,
            };
            return next;
          }),
        abortRef.current.signal,
      );
    } catch {
      setMessages((prev) => {
        const next = [...prev];
        const lastIndex = next.length - 1;
        if (!next[lastIndex].content) {
          next[lastIndex] = {
            role: "assistant",
            content: "Something interrupted me — ask that again?",
          };
        }
        return next;
      });
    } finally {
      setStreaming(false);
    }
  };

  const empty = messages.length === 0;
  // Offer a voice call once Ada has replied to a message that asked to speak or interview.
  const lastUser = [...messages].reverse().find((m) => m.role === "user")?.content ?? "";
  const voiceCue =
    !streaming && messages.at(-1)?.role === "assistant" && messages.at(-1)?.content
      ? detectVoiceCue(lastUser)
      : null;

  return (
    <div className="flex h-[calc(100dvh-9rem)] flex-col lg:h-[calc(100dvh-7rem)]">
      {!empty && (
        <div className="mb-4 flex items-baseline justify-between border-b border-line pb-4">
          <h1 className="display text-2xl">Ask Ada.</h1>
          <span className="flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-[11px] text-muted">
              <span className="pulse-soft size-1.5 rounded-full bg-success" />
              {runsCount
                ? `Grounded in ${runsCount} ${runsCount === 1 ? "run" : "runs"}`
                : "Grounded in your profile"}
            </span>
            <button
              type="button"
              onClick={() => void clear()}
              disabled={streaming}
              aria-label="Clear conversation"
              title="Clear conversation"
              className="flex items-center gap-1 text-[11px] text-muted transition-colors hover:text-danger disabled:opacity-40"
            >
              <Eraser className="size-3.5" /> Clear
            </button>
          </span>
        </div>
      )}
      {hasProfile === false && !empty && (
        <p className="mb-4 rounded-xl bg-accent-soft px-4 py-3 text-sm text-accent">
          Ada gives sharper advice when she knows your background —{" "}
          <Link href="/app/profile" className="underline">
            import your LinkedIn profile
          </Link>
          .
        </p>
      )}

      <div className="flex-1 space-y-6 overflow-y-auto pb-4 quiet-scroll">
        {empty && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <h1 className="display text-4xl">
              What&apos;s on your <em className="text-accent">mind</em>?
            </h1>
            <p className="mt-3 max-w-sm text-sm leading-relaxed text-muted">
              Career advice grounded in your profile and your runs — not generic tips.
            </p>
            {hasProfile === false && (
              <p className="mt-4 rounded-xl bg-accent-soft px-4 py-2.5 text-xs text-accent">
                Sharper advice when Ada knows your background —{" "}
                <Link href="/app/profile" className="underline">
                  import your profile
                </Link>
                .
              </p>
            )}
            <div className="mt-8 flex max-w-md flex-wrap justify-center gap-2">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => void send(s)}
                  className="rounded-full border border-line bg-surface px-4 py-2 text-sm text-muted shadow-card transition-all hover:-translate-y-px hover:border-accent hover:text-accent"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={m.role === "user" ? "flex justify-end" : "flex gap-3"}>
            {m.role === "user" ? (
              <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-accent px-4 py-2.5 text-sm text-accent-ink">
                {m.content}
              </p>
            ) : (
              <>
                <AdaMark />
                <div className="prose-ada max-w-[88%] pt-0.5">
                  {m.content ? (
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  ) : (
                    <span className="pulse-soft text-sm text-muted">Ada is thinking…</span>
                  )}
                </div>
              </>
            )}
          </div>
        ))}
        {voiceCue && <VoiceCue mode={voiceCue} />}
        <div ref={endRef} />
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send(input);
        }}
        className="pt-2"
      >
        <div className="flex items-end gap-2 rounded-3xl border border-line bg-surface p-2 shadow-card transition-colors focus-within:border-accent">
          <textarea
            rows={1}
            placeholder="Ask Ada anything…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void send(input);
              }
            }}
            className="max-h-40 flex-1 resize-none bg-transparent px-3 py-2 text-sm outline-none quiet-scroll placeholder:text-muted/70"
          />
          <Link
            href="/app/voice"
            aria-label="Switch to talking with Ada"
            className="flex size-9 shrink-0 items-center justify-center rounded-full text-muted transition-colors hover:bg-line/40 hover:text-ink"
          >
            <Mic className="size-4" />
          </Link>
          {streaming ? (
            <button
              type="button"
              onClick={() => abortRef.current?.abort()}
              aria-label="Stop"
              className="rounded-full bg-ink p-2.5 text-bg transition-transform hover:scale-105"
            >
              <Square className="size-4" />
            </button>
          ) : (
            <button
              type="submit"
              aria-label="Send"
              disabled={!input.trim()}
              className="rounded-full bg-accent p-2.5 text-accent-ink shadow-btn transition-transform hover:scale-105 disabled:opacity-40 disabled:shadow-none"
            >
              <ArrowUp className="size-4" />
            </button>
          )}
        </div>
        <p className="mt-2 text-center text-[11px] text-muted/70">
          Enter to send · Shift+Enter for a new line
        </p>
      </form>
    </div>
  );
}
