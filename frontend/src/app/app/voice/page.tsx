"use client";

import { Mic, MicOff, PhoneOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Button, Card, PageHeader } from "@/components/ui";
import { voiceWsUrl } from "@/lib/api";
import { createVoicePlayer, startMic, type MicSession, type VoicePlayer } from "@/lib/audio";

type CallState = "idle" | "connecting" | "live" | "extracting" | "error";

export default function VoicePage() {
  const router = useRouter();
  const [state, setState] = useState<CallState>("idle");
  const [error, setError] = useState("");
  const [seconds, setSeconds] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);
  const micRef = useRef<MicSession | null>(null);
  const playerRef = useRef<VoicePlayer | null>(null);

  // Session clock, shown in the eyebrow while Ada listens.
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
      const ws = new WebSocket(voiceWsUrl());
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
          target_role?: string;
          cv_text?: string;
          message?: string;
        };
        if (msg.type === "audio" && msg.data) {
          playerRef.current?.play(msg.data);
        } else if (msg.type === "interrupt") {
          playerRef.current?.clear();
        } else if (msg.type === "intake") {
          localStorage.setItem(
            "ada.intake-draft",
            JSON.stringify({ target_role: msg.target_role, cv_text: msg.cv_text }),
          );
          cleanup();
          router.push("/app/new");
        } else if (msg.type === "error") {
          setError(msg.message ?? "Ada's voice is unavailable right now.");
          setState("error");
          cleanup();
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
      setState("extracting");
      wsRef.current.send(JSON.stringify({ type: "end" }));
    } else {
      setState("idle");
    }
  };

  return (
    <>
      <PageHeader
        title="Talk to Ada."
        subtitle="A real spoken conversation — Ada asks about your background out loud, you answer, and she drafts your run. Interrupt her any time."
      />

      {state === "idle" || state === "error" ? (
        <Card className="flex flex-col items-center gap-6 p-10">
          <div className="flex size-20 items-center justify-center rounded-full bg-accent-soft">
            <Mic className="size-8 text-accent" />
          </div>
          {error && <p className="text-center text-sm text-danger">{error}</p>}
          <Button onClick={start} className="!px-7 !py-3">
            Start the conversation
          </Button>
          <p className="text-center text-xs text-muted">
            Uses your microphone. Prefer typing? Use{" "}
            <a href="/app/new" className="underline underline-offset-2 transition-colors hover:text-ink">
              the form
            </a>
            .
          </p>
        </Card>
      ) : (
        /* Live session: always dark, whatever the app theme — hardcoded to the
           dark palette per the mobile design canvas ("Voice session · dark"). */
        <div className="relative overflow-hidden rounded-card border border-[#2b2925] bg-[#12110e] text-[#f2f0ea] shadow-lift">
          <div
            className="pointer-events-none absolute left-1/2 top-8 size-80 -translate-x-1/2 rounded-full bg-[#8b85f4]/15 blur-3xl"
            aria-hidden
          />
          <div className="relative flex flex-col items-center px-7 pb-7 pt-10 text-center">
            <p className="eyebrow mb-2 !text-[#a09a8c]">
              In conversation{state === "live" ? ` · ${clock}` : ""}
            </p>
            <h2 className="display mb-9 text-3xl">
              Talking with Ada
              <br />
              about your work.
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
              {state === "live" && "Just talk — Ada replies out loud. Interrupt any time."}
              {state === "extracting" && "Wrapping up — drafting your run..."}
            </p>
            <div className="mt-8 flex w-full gap-2.5">
              <button
                onClick={() => {
                  cleanup();
                  setState("idle");
                }}
                disabled={state === "extracting"}
                className="flex-1 rounded-full border border-[#2b2925] bg-[#1a1916] py-3 text-sm font-medium text-[#a09a8c] transition-colors hover:text-[#f2f0ea] disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={end}
                disabled={state === "extracting"}
                className="flex flex-1 items-center justify-center gap-2 rounded-full bg-[#8b85f4] py-3 text-sm font-medium text-[#12110e] shadow-[0_4px_14px_rgba(139,133,244,0.25)] transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                <PhoneOff className="size-4" /> End &amp; draft my run
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
