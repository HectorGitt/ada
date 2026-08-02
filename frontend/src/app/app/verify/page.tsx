"use client";

import { AlertTriangle, BadgeCheck, Loader2, ShieldCheck, Timer } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { FocusStage } from "@/components/app/focus-stage";
import { LiveSession } from "@/components/app/live-session";
import { Button, Card, Input, Label, PageHeader, Skeleton, StatusBadge } from "@/components/ui";
import {
  ApiError,
  api,
  type AssessmentResult,
  type AssessmentTask,
  type Credential,
} from "@/lib/api";

type Mode = "voice_video" | "written";
const MODE_KEY = (id: string) => `ada.assess.mode.${id}`;

type Phase =
  | { kind: "idle" }
  | { kind: "starting" }
  | { kind: "active"; task: AssessmentTask; mode: Mode }
  | { kind: "scoring" }
  | { kind: "done"; result: AssessmentResult };

const VERDICT: Record<string, { label: string; tone: "success" | "warn" | "danger" }> = {
  verified: { label: "Verified", tone: "success" },
  needs_review: { label: "Needs review", tone: "warn" },
  failed: { label: "Below the bar", tone: "danger" },
};

function fmt(seconds: number): string {
  const s = Math.max(0, seconds);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export default function VerifyPage() {
  const [cred, setCred] = useState<Credential | null | undefined>(undefined);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [skill, setSkill] = useState("");
  const [mode, setMode] = useState<Mode>("voice_video");
  const [error, setError] = useState("");

  const reload = useCallback(() => {
    api.myCredential().then(setCred).catch(() => setCred(null));
  }, []);
  useEffect(reload, [reload]);

  // Resume an in-flight assessment after a refresh — the server timer keeps running, so we
  // pick up where it stands (answers are restored from local draft inside the session).
  useEffect(() => {
    api
      .activeAssessment()
      .then(({ active }) => {
        if (!active) return;
        const savedMode = (localStorage.getItem(MODE_KEY(active.assessment_id)) as Mode) || "voice_video";
        setPhase((p) => (p.kind === "idle" ? { kind: "active", task: active, mode: savedMode } : p));
      })
      .catch(() => {});
  }, []);

  const start = async () => {
    if (skill.trim().length < 2) return;
    setPhase({ kind: "starting" });
    setError("");
    try {
      const task = await api.startAssessment(skill.trim());
      try {
        localStorage.setItem(MODE_KEY(task.assessment_id), mode);
      } catch {
        /* non-fatal */
      }
      setPhase({ kind: "active", task, mode });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't start the assessment.");
      setPhase({ kind: "idle" });
    }
  };

  return (
    <>
      <PageHeader
        title="Get verified."
        subtitle="A short, proctored assessment plus an identity check. It becomes a credential employers trust — evidence, not our opinion."
      />

      {cred === undefined ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <CredentialCard cred={cred} onAttest={reload} />
      )}

      {phase.kind === "done" ? (
        <ResultCard result={phase.result} onRetake={() => { setPhase({ kind: "idle" }); reload(); }} />
      ) : phase.kind === "active" ? (
        <FocusStage
          title={`Proctored assessment · ${phase.task.skill}`}
          onExit={() => setPhase({ kind: "idle" })}
        >
          {phase.mode === "voice_video" ? (
            <LiveSession
              task={phase.task}
              onScoring={() => setPhase({ kind: "scoring" })}
              onDone={(result) => setPhase({ kind: "done", result })}
              onError={(m) => { setError(m); setPhase({ kind: "idle" }); }}
              onFallback={() => setPhase({ kind: "active", task: phase.task, mode: "written" })}
            />
          ) : (
            <ProctoredSession
              task={phase.task}
              onScoring={() => setPhase({ kind: "scoring" })}
              onDone={(result) => setPhase({ kind: "done", result })}
              onError={(m) => { setError(m); setPhase({ kind: "idle" }); }}
            />
          )}
        </FocusStage>
      ) : (
        <Card className="mt-6 p-6">
          <p className="font-medium">Take a skills assessment</p>
          <p className="mt-1 text-sm text-muted">
            Name the skill or role you want verified. You&apos;ll get a few timed questions —
            no switching tabs or pasting; that&apos;s the point.
          </p>
          <div className="mt-4">
            <Label>How would you like to take it?</Label>
            <div className="mt-1.5 inline-flex rounded-full border border-line p-0.5 text-xs">
              {(
                [
                  { key: "voice_video", label: "Voice + camera" },
                  { key: "written", label: "Written" },
                ] as const
              ).map((m) => (
                <button
                  key={m.key}
                  type="button"
                  onClick={() => setMode(m.key)}
                  className={`rounded-full px-3 py-1.5 font-medium transition-colors ${
                    mode === m.key ? "bg-accent text-accent-ink" : "text-muted hover:text-ink"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-xs text-muted">
              {mode === "voice_video"
                ? "Ada reads each question aloud; you answer by voice with your camera on for liveness."
                : "Type your answers. Timed and proctored, no camera."}
            </p>
          </div>
          <div className="mt-4 flex flex-wrap items-end gap-3">
            <div className="min-w-56 flex-1">
              <Label htmlFor="skill">Skill or role</Label>
              <Input
                id="skill"
                placeholder="e.g. Backend Engineering, Sales, Nursing"
                value={skill}
                onChange={(e) => setSkill(e.target.value)}
              />
            </div>
            <Button onClick={start} loading={phase.kind === "starting"} disabled={skill.trim().length < 2}>
              Start assessment
            </Button>
          </div>
          {error && <p className="mt-3 text-sm text-danger">{error}</p>}
        </Card>
      )}

      {phase.kind === "scoring" && (
        <Card className="mt-6 p-6">
          <p className="flex items-center gap-2.5 text-sm text-muted">
            <Loader2 className="size-4 animate-spin" /> Scoring your assessment…
          </p>
        </Card>
      )}
    </>
  );
}

// Friendly labels for the government IDs Smile supports (backend SUPPORTED_ID_TYPES).
const ID_LABELS: Record<string, string> = {
  NIN: "National ID (NIN)",
  NIN_SLIP: "NIN slip",
  BVN: "Bank Verification Number (BVN)",
  DRIVERS_LICENSE: "Driver's licence",
  VOTER_ID: "Voter's card",
  PASSPORT: "Passport",
  CAC: "CAC (business)",
  TIN: "Tax ID (TIN)",
};

function IdentityPanel({ cred, onDone }: { cred: Credential | null; onDone: () => void }) {
  const [methods, setMethods] = useState<{ kyc_enabled: boolean; id_types: string[] } | null>(null);
  const [open, setOpen] = useState(false);
  const [idType, setIdType] = useState("");
  const [idNumber, setIdNumber] = useState("");
  const [dob, setDob] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.identityMethods().then(setMethods).catch(() => setMethods({ kyc_enabled: false, id_types: [] }));
  }, []);

  const attest = async () => {
    setBusy(true);
    try {
      await api.attestIdentity();
      onDone();
    } catch {
      /* keep */
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.verifyIdentity(idType, idNumber.trim(), dob || null);
      onDone();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't verify that ID — check the details.");
    } finally {
      setBusy(false);
    }
  };

  const types = methods?.id_types ?? [];

  return (
    <div className="bg-surface p-6">
      <p className="flex items-center gap-2 text-sm font-medium">
        <ShieldCheck className={`size-4 ${cred?.identity_verified ? "text-success" : "text-muted"}`} />
        Identity
      </p>

      {cred?.identity_verified ? (
        <p className="mt-2 text-sm text-muted">
          {cred.identity_method === "attested"
            ? "Self-attested."
            : `Verified with ${ID_LABELS[cred.identity_method?.split(":")[1]?.toUpperCase() ?? ""] ?? "a government ID"}.`}{" "}
          Employers see this on your profile.
        </p>
      ) : methods === null ? (
        <Skeleton className="mt-3 h-8 w-40" />
      ) : methods.kyc_enabled ? (
        <>
          <p className="mt-2 text-sm text-muted">
            Verify with a government ID — a real check employers trust.
          </p>
          {!open ? (
            <Button variant="secondary" onClick={() => setOpen(true)} className="mt-3 !py-2 text-xs">
              Verify with government ID
            </Button>
          ) : (
            <form onSubmit={verify} className="mt-3 space-y-2.5">
              <select
                required
                value={idType}
                onChange={(e) => setIdType(e.target.value)}
                aria-label="ID type"
                className="w-full rounded-xl border border-line bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
              >
                <option value="" disabled>
                  Choose ID type
                </option>
                {types.map((t) => (
                  <option key={t} value={t}>
                    {ID_LABELS[t] ?? t}
                  </option>
                ))}
              </select>
              <Input
                required
                placeholder="ID number"
                value={idNumber}
                onChange={(e) => setIdNumber(e.target.value)}
              />
              <Input
                type="date"
                aria-label="Date of birth (if the ID needs it)"
                value={dob}
                onChange={(e) => setDob(e.target.value)}
              />
              {error && <p className="text-xs text-danger">{error}</p>}
              <Button type="submit" loading={busy} className="w-full !py-2 text-xs">
                Verify identity
              </Button>
              <button
                type="button"
                onClick={attest}
                className="block w-full text-center text-[11px] text-muted underline-offset-2 hover:underline"
              >
                or self-attest instead
              </button>
            </form>
          )}
        </>
      ) : (
        <>
          <p className="mt-2 text-sm text-muted">
            Confirm your identity so employers know you&apos;re real.
          </p>
          <Button variant="secondary" onClick={attest} loading={busy} className="mt-3 !py-2 text-xs">
            Verify my identity
          </Button>
        </>
      )}
    </div>
  );
}

function CredentialCard({ cred, onAttest }: { cred: Credential | null; onAttest: () => void }) {
  const a = cred?.assessment;
  const verdict = a?.verdict ? VERDICT[a.verdict] : null;

  return (
    <Card className="grid gap-px overflow-hidden !p-0 sm:grid-cols-2">
      <IdentityPanel cred={cred} onDone={onAttest} />
      <div className="bg-surface p-6">
        <p className="flex items-center gap-2 text-sm font-medium">
          <BadgeCheck className={`size-4 ${verdict?.tone === "success" ? "text-success" : "text-muted"}`} />
          Skills assessment
        </p>
        {a ? (
          <div className="mt-2 flex items-center gap-3">
            <span className="display text-3xl">{a.score}</span>
            {verdict && <StatusBadge tone={verdict.tone}>{verdict.label}</StatusBadge>}
            <span className="text-xs text-muted">{a.skill}</span>
          </div>
        ) : (
          <p className="mt-2 text-sm text-muted">Not taken yet — one proctored assessment below.</p>
        )}
      </div>
    </Card>
  );
}

function ProctoredSession({
  task,
  onScoring,
  onDone,
  onError,
}: {
  task: AssessmentTask;
  onScoring: () => void;
  onDone: (r: AssessmentResult) => void;
  onError: (m: string) => void;
}) {
  const [answers, setAnswers] = useState<string[]>(() => task.questions.map(() => ""));
  const [remaining, setRemaining] = useState(task.seconds_remaining);
  const submitted = useRef(false);
  // Integrity telemetry — advisory to the client, gated server-side too.
  const integrity = useRef({ tab_switches: 0, blur_seconds: 0, paste_events: 0 });
  const blurStart = useRef<number | null>(null);

  const submit = useCallback(async () => {
    if (submitted.current) return;
    submitted.current = true;
    onScoring();
    try {
      const result = await api.submitAssessment(task.assessment_id, answers, {
        ...integrity.current,
        blur_seconds: Math.round(integrity.current.blur_seconds),
      });
      onDone(result);
    } catch (err) {
      onError(err instanceof ApiError ? err.message : "Couldn't submit — try again.");
    }
  }, [answers, task.assessment_id, onScoring, onDone, onError]);

  // Countdown → auto-submit at zero (server enforces the real limit regardless).
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

  // Proctoring: count tab-switches + accumulate time spent off-tab.
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
      <p className="mb-5 flex items-center gap-1.5 text-xs text-muted">
        <AlertTriangle className="size-3.5" /> Leaving this tab or pasting is recorded and
        flags your result for review.
      </p>
      <div className="space-y-5">
        {task.questions.map((q, i) => (
          <div key={i}>
            <Label htmlFor={`q-${i}`}>
              {i + 1}. {q}
            </Label>
            <textarea
              id={`q-${i}`}
              rows={4}
              value={answers[i]}
              onPaste={(e) => {
                e.preventDefault();
                integrity.current.paste_events += 1;
              }}
              onChange={(e) =>
                setAnswers((cur) => cur.map((a, j) => (j === i ? e.target.value : a)))
              }
              className="mt-1 w-full rounded-xl border border-line bg-surface px-3.5 py-2.5 text-sm outline-none transition-all focus:border-accent focus:ring-2 focus:ring-accent/20"
            />
          </div>
        ))}
      </div>
      <Button onClick={submit} className="mt-5">
        Submit assessment
      </Button>
    </Card>
  );
}

function ResultCard({ result, onRetake }: { result: AssessmentResult; onRetake: () => void }) {
  const v = VERDICT[result.verdict] ?? VERDICT.needs_review;
  return (
    <Card className="mt-6 p-6">
      <div className="flex items-center gap-4">
        <span className="display text-4xl">{result.score}</span>
        <StatusBadge tone={v.tone}>{v.label}</StatusBadge>
      </div>
      {result.summary && (
        <p className="mt-3 text-sm leading-relaxed text-muted">{result.summary}</p>
      )}
      {result.verdict === "needs_review" && (
        <p className="mt-3 rounded-lg bg-warn-soft/50 px-3 py-2 text-xs text-warn">
          Your session tripped a proctoring flag (tab-switch, paste, over time, or camera off/
          out of frame), so the score isn&apos;t certified. Retake it cleanly to earn the verified badge.
        </p>
      )}
      <Button variant="secondary" onClick={onRetake} className="mt-4 !py-2 text-xs">
        Back
      </Button>
    </Card>
  );
}
