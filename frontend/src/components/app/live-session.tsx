"use client";

import { AlertTriangle, Loader2, Mic, MicOff, Timer, Video } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button, Card } from "@/components/ui";
import { ApiError, api, type AssessmentResult, type AssessmentTask } from "@/lib/api";

// Minimal shape of the Web Speech API (no lib types ship for it).
type Recognition = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start: () => void;
  stop: () => void;
  onresult: ((e: SpeechResultEvent) => void) | null;
  onend: (() => void) | null;
  onerror: (() => void) | null;
};
type SpeechResultEvent = {
  resultIndex: number;
  results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }>;
};
type FaceDetectorType = { detect: (v: HTMLVideoElement) => Promise<unknown[]> };

const SNAPSHOT_EVERY_MS = 20_000;
const MAX_SNAPSHOTS = 6;
const DRAFT_KEY = (id: string) => `ada.assess.${id}`;

function fmt(seconds: number): string {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function getRecognition(): Recognition | null {
  const w = window as unknown as {
    SpeechRecognition?: new () => Recognition;
    webkitSpeechRecognition?: new () => Recognition;
  };
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  return Ctor ? new Ctor() : null;
}

export function LiveSession({
  task,
  onScoring,
  onDone,
  onError,
  onFallback,
}: {
  task: AssessmentTask;
  onScoring: () => void;
  onDone: (r: AssessmentResult) => void;
  onError: (m: string) => void;
  onFallback: () => void; // camera denied → switch to the written version
}) {
  const [camera, setCamera] = useState<"idle" | "requesting" | "granted" | "denied">("idle");
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState<string[]>(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(DRAFT_KEY(task.assessment_id)) ?? "null");
      if (Array.isArray(saved) && saved.length === task.questions.length) return saved;
    } catch {
      /* fresh */
    }
    return task.questions.map(() => "");
  });
  const [remaining, setRemaining] = useState(task.seconds_remaining);
  const [listening, setListening] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const snapshots = useRef<string[]>([]);
  const submitted = useRef(false);
  const integrity = useRef({ tab_switches: 0, blur_seconds: 0, paste_events: 0, face_absent_seconds: 0 });
  const blurStart = useRef<number | null>(null);
  const recognition = useRef<Recognition | null>(null);

  // Persist answers so a refresh (which re-enters via /assessment/active) keeps them.
  useEffect(() => {
    try {
      localStorage.setItem(DRAFT_KEY(task.assessment_id), JSON.stringify(answers));
    } catch {
      /* storage full / disabled — non-fatal */
    }
  }, [answers, task.assessment_id]);

  const cameraLive = () => {
    const track = streamRef.current?.getVideoTracks()[0];
    return !!track && track.readyState === "live" && track.enabled;
  };

  const submit = useCallback(async () => {
    if (submitted.current) return;
    submitted.current = true;
    recognition.current?.stop();
    // A final frame at submit time.
    if (videoRef.current && cameraLive() && snapshots.current.length < MAX_SNAPSHOTS + 1) {
      const frame = grabFrame(videoRef.current);
      if (frame) snapshots.current.push(frame);
    }
    onScoring();
    try {
      const result = await api.submitAssessment(
        task.assessment_id,
        answers,
        {
          ...integrity.current,
          blur_seconds: Math.round(integrity.current.blur_seconds),
          face_absent_seconds: Math.round(integrity.current.face_absent_seconds),
          mode: "voice_video",
          camera_present: cameraLive(),
        },
        snapshots.current,
      );
      localStorage.removeItem(DRAFT_KEY(task.assessment_id));
      onDone(result);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Couldn't submit — try again.");
    }
  }, [answers, task.assessment_id, onScoring, onDone, onError]);

  // Request camera + mic — on a user gesture (button), so the browser reliably prompts
  // and we avoid StrictMode's double-invoke racing two getUserMedia calls into a reject.
  const requestCamera = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setCamera("denied"); // no API (e.g. insecure context / unsupported browser)
      return;
    }
    setCamera("requesting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: 640, height: 480 },
        audio: true,
      });
      streamRef.current = stream;
      setCamera("granted");
    } catch {
      setCamera("denied");
    }
  }, []);

  // Attach the stream to the <video> once it's rendered (granted).
  useEffect(() => {
    if (camera === "granted" && videoRef.current && streamRef.current) {
      videoRef.current.srcObject = streamRef.current;
    }
  }, [camera]);

  // Release the camera/mic when leaving the session.
  useEffect(() => {
    return () => streamRef.current?.getTracks().forEach((t) => t.stop());
  }, []);

  // Snapshots + liveness (face-absent) sampling while granted.
  useEffect(() => {
    if (camera !== "granted") return;
    const FaceDetector = (window as unknown as { FaceDetector?: new () => FaceDetectorType })
      .FaceDetector;
    const detector = FaceDetector ? new FaceDetector() : null;
    const id = setInterval(async () => {
      const video = videoRef.current;
      if (!video) return;
      if (!cameraLive()) {
        integrity.current.face_absent_seconds += SNAPSHOT_EVERY_MS / 1000;
        return;
      }
      if (snapshots.current.length < MAX_SNAPSHOTS) {
        const frame = grabFrame(video);
        if (frame) snapshots.current.push(frame);
      }
      if (detector) {
        try {
          const faces = await detector.detect(video);
          if (faces.length === 0) integrity.current.face_absent_seconds += SNAPSHOT_EVERY_MS / 1000;
        } catch {
          /* detector hiccup — ignore */
        }
      }
    }, SNAPSHOT_EVERY_MS);
    return () => clearInterval(id);
  }, [camera]);

  // Ada reads the current question aloud.
  useEffect(() => {
    if (camera !== "granted") return;
    const q = task.questions[idx];
    if (!q || typeof speechSynthesis === "undefined") return;
    const utter = new SpeechSynthesisUtterance(`Question ${idx + 1}. ${q}`);
    utter.rate = 1;
    speechSynthesis.cancel();
    speechSynthesis.speak(utter);
    return () => speechSynthesis.cancel();
  }, [idx, camera, task.questions]);

  // Server-authoritative countdown → auto-submit at zero.
  useEffect(() => {
    const id = setInterval(() => {
      setRemaining((r) => {
        if (r <= 1) {
          clearInterval(id);
          void submit();
          return 0;
        }
        return r - 1;
      });
    }, 1000);
    return () => clearInterval(id);
  }, [submit]);

  // Tab-switch / off-tab telemetry (kept alongside the camera signals).
  useEffect(() => {
    const onVis = () => {
      if (document.hidden) {
        integrity.current.tab_switches += 1;
        blurStart.current = Date.now();
      } else if (blurStart.current) {
        integrity.current.blur_seconds += (Date.now() - blurStart.current) / 1000;
        blurStart.current = null;
      }
    };
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  const toggleMic = () => {
    if (listening) {
      recognition.current?.stop();
      return;
    }
    const rec = getRecognition();
    if (!rec) {
      setListening(false);
      return; // no speech API — the candidate types instead
    }
    rec.lang = "en-US";
    rec.continuous = true;
    rec.interimResults = false;
    rec.onresult = (e) => {
      let chunk = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) chunk += e.results[i][0].transcript;
      }
      if (chunk) {
        setAnswers((cur) => cur.map((a, j) => (j === idx ? `${a} ${chunk}`.trim() : a)));
      }
    };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recognition.current = rec;
    rec.start();
    setListening(true);
  };

  if (camera === "idle") {
    return (
      <Card className="mt-6 p-6">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Video className="size-4 text-accent" /> Voice + camera interview
        </p>
        <p className="mt-2 max-w-md text-sm text-muted">
          Ada reads each question aloud; you answer by voice (or type). Your camera stays on
          for liveness — we keep a few snapshots, never the full video. Your browser will ask
          for camera &amp; mic access next.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={requestCamera}>
            <Video className="size-4" /> Enable camera &amp; mic
          </Button>
          <button
            onClick={onFallback}
            className="text-xs text-muted underline-offset-2 hover:underline"
          >
            or take the written version
          </button>
        </div>
      </Card>
    );
  }

  if (camera === "requesting") {
    return (
      <Card className="mt-6 flex items-center gap-3 p-6 text-sm text-muted">
        <Loader2 className="size-4 animate-spin" /> Waiting for camera and microphone… allow
        access in your browser.
      </Card>
    );
  }

  if (camera === "denied") {
    return (
      <Card className="mt-6 p-6">
        <p className="flex items-center gap-2 text-sm font-medium">
          <Video className="size-4 text-warn" /> Camera access blocked
        </p>
        <p className="mt-2 max-w-md text-sm text-muted">
          We couldn&apos;t get your camera and mic — the browser may have blocked them, or this
          isn&apos;t a secure (https/localhost) page. Allow access in the address bar, then try
          again, or take the written version.
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-2">
          <Button onClick={requestCamera}>Try again</Button>
          <button
            onClick={onFallback}
            className="text-xs text-muted underline-offset-2 hover:underline"
          >
            or take the written version
          </button>
        </div>
      </Card>
    );
  }

  const last = idx === task.questions.length - 1;
  const overHalf = remaining <= task.time_limit_seconds / 2;

  return (
    <Card className="mt-6 p-6">
      <div className="mb-4 flex items-center justify-between">
        <p className="font-medium">Proctored · {task.skill}</p>
        <span
          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium tabular-nums ${
            overHalf ? "bg-warn-soft text-warn" : "bg-surface-2 text-muted"
          }`}
        >
          <Timer className="size-3.5" /> {fmt(remaining)}
        </span>
      </div>

      <div className="mb-5 flex flex-wrap items-start gap-4">
        <video
          ref={videoRef}
          autoPlay
          muted
          playsInline
          className="aspect-[4/3] w-40 shrink-0 rounded-xl border border-line bg-surface-2 object-cover"
        />
        <p className="flex-1 text-xs text-muted">
          <AlertTriangle className="mr-1 inline size-3.5" />
          You&apos;re being recorded for liveness. Ada reads each question aloud — answer by
          voice (or type). Leaving the tab, pasting, or going off-camera flags your result.
        </p>
      </div>

      <div>
        <p className="text-sm font-medium">
          Question {idx + 1} of {task.questions.length}
        </p>
        <p className="mt-1.5 text-[15px] leading-relaxed">{task.questions[idx]}</p>

        <div className="mt-3 flex items-center gap-2">
          <Button
            variant={listening ? "primary" : "secondary"}
            onClick={toggleMic}
            className="!py-2 text-xs"
          >
            {listening ? <MicOff className="size-4" /> : <Mic className="size-4" />}
            {listening ? "Stop" : "Answer by voice"}
          </Button>
          <span className="text-[11px] text-muted">or type below</span>
        </div>

        <textarea
          rows={4}
          value={answers[idx]}
          onPaste={(e) => {
            e.preventDefault();
            integrity.current.paste_events += 1;
          }}
          onChange={(e) => setAnswers((cur) => cur.map((a, j) => (j === idx ? e.target.value : a)))}
          placeholder="Your spoken answer appears here — edit if needed."
          className="mt-2 w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm outline-none transition-all focus:border-accent focus:ring-2 focus:ring-accent/20"
        />
      </div>

      <div className="mt-5 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setIdx((i) => Math.max(0, i - 1))}
          disabled={idx === 0}
          className="text-xs text-muted underline-offset-2 hover:underline disabled:opacity-40"
        >
          ← Previous
        </button>
        {last ? (
          <Button onClick={submit}>Submit assessment</Button>
        ) : (
          <Button onClick={() => setIdx((i) => i + 1)}>Next question</Button>
        )}
      </div>
    </Card>
  );
}

// Downscaled JPEG frame from the live video, as a data URL (or null if not drawable yet).
function grabFrame(video: HTMLVideoElement): string | null {
  const w = 320;
  const h = video.videoHeight && video.videoWidth ? (video.videoHeight / video.videoWidth) * w : 240;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  try {
    ctx.drawImage(video, 0, 0, w, h);
    return canvas.toDataURL("image/jpeg", 0.5);
  } catch {
    return null;
  }
}
