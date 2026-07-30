"use client";

import { AnimatePresence, motion } from "motion/react";
import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";

// Stable, organic-looking bar heights (0–1). Fixed so the waveform never reflows.
const BARS = [
  0.32, 0.5, 0.72, 0.44, 0.9, 0.6, 0.38, 0.66, 0.85, 0.52, 0.3, 0.58, 0.78, 0.46,
  0.94, 0.62, 0.4, 0.7, 0.55, 0.34, 0.82, 0.5, 0.68, 0.42, 0.88, 0.6, 0.36, 0.64,
  0.8, 0.48, 0.3, 0.56, 0.74, 0.44, 0.9, 0.58, 0.4, 0.68, 0.52, 0.34,
];

function fmt(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

/** Custom voice-intro player shared by both agents — a pill that expands into a
 *  scrubbable waveform. `src` is the audio asset, `name` the agent (Ada / Uche). */
function VoiceIntro({ src, name, fallbackDuration = 24 }: {
  src: string;
  name: string;
  fallbackDuration?: number;
}) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const [open, setOpen] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(fallbackDuration);

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;
    const onTime = () => setCurrent(audio.currentTime);
    const onMeta = () => setDuration(audio.duration || fallbackDuration);
    const onEnd = () => setPlaying(false);
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("loadedmetadata", onMeta);
    audio.addEventListener("ended", onEnd);
    return () => {
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("loadedmetadata", onMeta);
      audio.removeEventListener("ended", onEnd);
    };
  }, [open]);

  const play = () => {
    void audioRef.current?.play();
    setPlaying(true);
  };
  const pause = () => {
    audioRef.current?.pause();
    setPlaying(false);
  };
  const toggle = () => (playing ? pause() : play());

  const openAndPlay = () => {
    setOpen(true);
    // The pill click is an explicit user gesture, so this is not autoplay.
    requestAnimationFrame(play);
  };

  const seekTo = (fraction: number) => {
    const audio = audioRef.current;
    if (!audio || !duration) return;
    audio.currentTime = Math.min(duration, Math.max(0, fraction * duration));
    setCurrent(audio.currentTime);
  };

  const onScrubKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") seekTo((current + 2) / duration);
    else if (e.key === "ArrowLeft") seekTo((current - 2) / duration);
    else if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      toggle();
    }
  };

  const progress = duration ? current / duration : 0;

  return (
    <div className="w-full max-w-md">
      <audio ref={audioRef} src={src} preload="metadata" />

      <AnimatePresence initial={false} mode="wait">
        {!open ? (
          <motion.button
            key="pill"
            type="button"
            onClick={openAndPlay}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            className="group inline-flex items-center gap-3 rounded-full border border-line bg-surface/70 py-2 pl-2.5 pr-4 shadow-card backdrop-blur-sm transition-colors hover:border-accent/50"
          >
            <span className="flex size-8 items-center justify-center rounded-full bg-accent text-accent-ink shadow-btn transition-transform group-hover:scale-105">
              <Play className="ml-0.5 size-3.5" />
            </span>
            <span className="flex items-end gap-[2px]" aria-hidden>
              {[0.5, 0.85, 0.4, 0.7, 0.55].map((h, i) => (
                <span
                  key={i}
                  className="w-[2px] rounded-full bg-accent/70 transition-all group-hover:bg-accent"
                  style={{ height: `${h * 14 + 4}px` }}
                />
              ))}
            </span>
            <span className="text-sm font-medium text-ink">Hear from {name}</span>
            <span className="text-xs tabular-nums text-muted">{fmt(duration)}</span>
          </motion.button>
        ) : (
          <motion.div
            key="player"
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
            className="rounded-2xl border border-line bg-surface/90 p-4 shadow-lift backdrop-blur-md"
          >
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={toggle}
                aria-label={playing ? `Pause ${name}'s introduction` : `Play ${name}'s introduction`}
                className="flex size-11 shrink-0 items-center justify-center rounded-full bg-accent text-accent-ink shadow-btn transition-transform hover:scale-105 active:scale-95"
              >
                {playing ? (
                  <Pause className="size-4" />
                ) : (
                  <Play className="ml-0.5 size-4" />
                )}
              </button>

              <div
                role="slider"
                tabIndex={0}
                aria-label={`Seek ${name}'s introduction`}
                aria-valuemin={0}
                aria-valuemax={Math.round(duration)}
                aria-valuenow={Math.round(current)}
                aria-valuetext={`${fmt(current)} of ${fmt(duration)}`}
                onKeyDown={onScrubKey}
                onClick={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  seekTo((e.clientX - rect.left) / rect.width);
                }}
                className="flex h-9 flex-1 cursor-pointer items-center gap-[2px] rounded-md outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
              >
                {BARS.map((h, i) => {
                  const filled = i / BARS.length <= progress;
                  const atHead = playing && Math.abs(i / BARS.length - progress) < 0.03;
                  return (
                    <span
                      key={i}
                      className={`flex-1 rounded-full transition-colors ${
                        filled ? "bg-accent" : "bg-line"
                      } ${atHead ? "vi-bar-live" : ""}`}
                      style={{ height: `${h * 26 + 4}px` }}
                    />
                  );
                })}
              </div>

              <span className="w-16 shrink-0 text-right text-xs tabular-nums text-muted">
                {fmt(current)} / {fmt(duration)}
              </span>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export function AdaVoiceIntro() {
  return <VoiceIntro src="/ada-intro.mp3" name="Ada" fallbackDuration={24} />;
}

export function UcheVoiceIntro() {
  return <VoiceIntro src="/uche-intro.mp3" name="Uche" fallbackDuration={19} />;
}
