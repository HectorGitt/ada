"use client";

import { Mic, MicOff, PhoneOff } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { Button, Card, PageHeader } from "@/components/ui";
import { voiceWsUrl } from "@/lib/api";
import { createVoicePlayer, startMic, type MicSession, type VoicePlayer } from "@/lib/audio";

type CallState = "idle" | "connecting" | "live" | "ending" | "error";
type Mode = "conversation" | "interview";

const COPY: Record<Mode, { title: string; subtitle: string; cta: string; live: string }> = {
  conversation: {
    title: "Talk to Ada.",
    subtitle:
      "A real spoken conversation — Ada already knows your background, so she picks up where you are. Interrupt her any time.",
    cta: "Start the conversation",
    live: "Just talk — Ada replies out loud. Interrupt any time.",
  },
  interview: {
    title: "Mock interview.",
    subtitle:
      "A realistic spoken interview for your target role, grounded in your background — with honest feedback at the end.",
    cta: "Start the interview",
    live: "Answer out loud — Ada follows up like a real interviewer.",
  },
};

function VoiceCall() {
  const mode: Mode =
    useSearchParams().get("mode") === "interview" ? "interview" : "conversation";
  const copy = COPY[mode];
  const [state, setState] = useState<CallState>("idle");
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const micRef = useRef<MicSession | null>(null);
  const playerRef = useRef<VoicePlayer | null>(null);

  useEffect(() => {
    if (state !== "live") return;
    const id = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, [state]);
  const clock = `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(seconds % 60).padStart(2, "0")}`;

  const cleanup = () => {
    micRef.current?.stop();
    micRef.current = null;
    playerRef.current?.close();
    playerRef.current = null;
    wsRef.current?.close();
    wsRef.current = null;
  };
  useEffect(() => cleanup, []);

  const start = async () => {
    setState("connecting");
    setError("");
    setSeconds(0);
    try {
      const ws = new WebSocket(voiceWsUrl(mode));
      wsRef.current = ws;

      ws.onopen = async () => {
        try {
          playerRef.current = createVoicePlayer();
          micRef.current = await startMic((frame) => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ type: "audio", data: frame }));
            }
          });
          setState("live");
        } catch {
          setError("Microphone access was denied.");
          setState("error");
          cleanup();
        }
      };

      ws.onmessage = (event) => {
        const msg = JSON.parse(event.data as string) as {
          type: string;
          data?: string;
          message?: string;
        };
        if (msg.type === "audio" && msg.data) {
          playerRef.current?.play(msg.data);
        } else if (msg.type === "interrupt") {
          playerRef.current?.clear();
        } else if (msg.type === "ended") {
          cleanup();
          setState("idle");
        } else if (msg.type === "error") {
          setError(msg.message ?? "Ada's voice is unavailable right now.");
          setState("error");
          cleanup();
        }
      };

      ws.onclose = () => {
        if (wsRef.current) {
          cleanup();
          setState((s) => (s === "error" ? s : "idle"));
        }
      };

      ws.onerror = () => {
        setError("Couldn't reach the voice service.");
        setState("error");
      };
    } catch {
      setError("Couldn't start the call.");
      setState("error");
    }
  };

  const end = () => {
    micRef.current?.stop();
    micRef.current = null;
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setState("ending");
      wsRef.current.send(JSON.stringify({ type: "end" }));
    } else {
      cleanup();
      setState("idle");
    }
  };

  return (
    <>
      <PageHeader title={copy.title} subtitle={copy.subtitle} />

      {state === "idle" || state === "error" ? (
        <Card className="flex flex-col items-center gap-6 p-10">
          <div className="flex size-20 items-center justify-center rounded-full bg-accent-soft">
            <Mic className="size-8 text-accent" />
          </div>
          {error && <p className="text-center text-sm text-danger">{error}</p>}
          <Button onClick={start} className="!px-7 !py-3">
            {copy.cta}
          </Button>
          <p className="text-center text-xs text-muted">Uses your microphone.</p>
        </Card>
      ) : (
        <div className="relative overflow-hidden rounded-card border border-[#2b2925] bg-[#12110e] text-[#f2f0ea] shadow-lift">
          <div
            className="pointer-events-none absolute left-1/2 top-8 size-80 -translate-x-1/2 rounded-full bg-[#8b85f4]/15 blur-3xl"
            aria-hidden
          />
          <div className="relative flex flex-col items-center px-7 pb-7 pt-10 text-center">
            <p className="eyebrow mb-2 !text-[#a09a8c]">
              {mode === "interview" ? "Interview" : "In conversation"}
              {state === "live" ? ` · ${clock}` : ""}
            </p>
            <h2 className="display mb-9 text-3xl">
              {mode === "interview" ? (
                <>
                  Interviewing
                  <br />
                  with Ada.
                </>
              ) : (
                <>
                  Talking with Ada
                  <br />
                  about your work.
                </>
              )}
            </h2>
            <div className="relative mb-8 size-32">
              {state === "live" &&
                ["0s", "0.6s", "1.2s"].map((delay) => (
                  <span
                    key={delay}
                    className="ring-ping absolute inset-0 rounded-full border-[1.5px] border-[#8b85f4]/45"
                    style={{ animationDelay: delay }}
                    aria-hidden
                  />
                ))}
              <div
                className={`absolute inset-2.5 flex items-center justify-center rounded-full ${
                  state === "live"
                    ? "bg-[#8b85f4] text-[#12110e] shadow-[0_0_60px_rgba(139,133,244,0.4)]"
                    : "pulse-soft bg-[#232145] text-[#8b85f4]"
                }`}
              >
                {state === "connecting" ? (
                  <MicOff className="size-8" />
                ) : (
                  <Mic className="size-8" />
                )}
              </div>
            </div>
            {state === "live" && (
              <div className="mb-6 flex h-6 items-end gap-[3px]" aria-hidden>
                {[8, 16, 22, 12, 18, 7, 14].map((h, i) => (
                  <span
                    key={i}
                    className="eq-bar w-[3px] rounded-full bg-[#8b85f4]"
                    style={{ height: h, animationDelay: `${i * 0.13}s` }}
                  />
                ))}
              </div>
            )}
            <p className="text-sm text-[#a09a8c]">
              {state === "connecting" && "Connecting to Ada..."}
              {state === "live" && copy.live}
              {state === "ending" && "Ending — saving what you shared..."}
            </p>
            <div className="mt-8 flex w-full justify-center">
              <button
                onClick={end}
                disabled={state === "ending"}
                className="flex items-center justify-center gap-2 rounded-full bg-[#8b85f4] px-8 py-3 text-sm font-medium text-[#12110e] shadow-[0_4px_14px_rgba(139,133,244,0.25)] transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                <PhoneOff className="size-4" /> End call
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default function VoicePage() {
  return (
    <Suspense>
      <VoiceCall />
    </Suspense>
  );
}
