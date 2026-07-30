"use client";

import { AlertCircle, Check, Loader2, Send } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { Button, Input, Label } from "@/components/ui";
import { ApiError, api, type ApplicationStatus } from "@/lib/api";

type Phase =
  | { kind: "idle" }
  | { kind: "identity" }
  | { kind: "working"; applicationId: string }
  | { kind: "done"; status: ApplicationStatus; detail: string | null };

const POLL_MS = 3000;
const POLL_LIMIT = 60;

export function ApplyButton({ jobId, runId }: { jobId: number; runId?: string }) {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const polls = useRef(0);

  const start = useCallback(async () => {
    setBusy(true);
    setError("");
    try {
      const res = await api.applyToJob(jobId, runId);
      if (res.already_applied && res.status !== "preparing") {
        const app = (await api.listApplications()).find((a) => a.id === res.application_id);
        setPhase({ kind: "done", status: res.status, detail: app?.detail ?? null });
      } else {
        polls.current = 0;
        setPhase({ kind: "working", applicationId: res.application_id });
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 428) {
        setPhase({ kind: "identity" });
      } else {
        setError(err instanceof ApiError ? err.message : "Couldn't start the application.");
      }
    } finally {
      setBusy(false);
    }
  }, [jobId, runId]);

  const saveIdentity = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api.putIdentity({ full_name: fullName.trim(), phone: phone.trim() || null });
      setPhase({ kind: "idle" });
      await start();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't save your details.");
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    if (phase.kind !== "working") return;
    const timer = setInterval(async () => {
      polls.current += 1;
      try {
        const app = (await api.listApplications()).find((a) => a.id === phase.applicationId);
        if (app && app.status !== "preparing") {
          setPhase({ kind: "done", status: app.status, detail: app.detail });
        } else if (polls.current >= POLL_LIMIT) {
          setPhase({
            kind: "done",
            status: "preparing",
            detail: "Still working — check the Applications page in a minute.",
          });
        }
      } catch {
        /* keep polling */
      }
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [phase]);

  if (phase.kind === "done") {
    if (phase.status === "submitted") {
      return (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-success-soft px-3 py-1.5 text-xs font-medium text-success">
          <Check className="size-3.5" /> Applied
        </span>
      );
    }
    return (
      <div className="flex flex-col items-end gap-1.5">
        <span
          title={phase.detail ?? undefined}
          className="inline-flex max-w-56 items-center gap-1.5 rounded-full bg-warn-soft px-3 py-1.5 text-xs font-medium text-warn"
        >
          <AlertCircle className="size-3.5 shrink-0" />
          <span className="truncate">
            {phase.status === "failed" ? "Failed — nothing sent" : "Needs your attention"}
          </span>
        </span>
        {phase.detail && (
          <p className="max-w-56 text-right text-[11px] leading-snug text-muted">{phase.detail}</p>
        )}
        <button
          onClick={() => {
            setPhase({ kind: "idle" });
            void start();
          }}
          className="text-xs font-medium text-accent underline-offset-2 hover:underline"
        >
          Try again
        </button>
      </div>
    );
  }

  if (phase.kind === "working") {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-3 py-1.5 text-xs font-medium text-accent">
        <Loader2 className="size-3.5 animate-spin" /> Ada is applying…
      </span>
    );
  }

  if (phase.kind === "identity") {
    return (
      <form onSubmit={saveIdentity} className="w-full space-y-2.5 rounded-xl border border-line bg-surface-2 p-3.5">
        <p className="text-xs text-muted">
          One-time setup — Ada needs your name (and phone) for application forms.
        </p>
        <div>
          <Label htmlFor={`name-${jobId}`}>Full name</Label>
          <Input
            id={`name-${jobId}`}
            required
            minLength={2}
            autoFocus
            placeholder="Jane Doe"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor={`phone-${jobId}`}>Phone (optional)</Label>
          <Input
            id={`phone-${jobId}`}
            placeholder="+234 800 000 0000"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />
        </div>
        {error && <p className="text-xs text-danger">{error}</p>}
        <Button type="submit" loading={busy} className="!px-4 !py-2 text-xs">
          Save & apply
        </Button>
      </form>
    );
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <Button onClick={start} loading={busy} className="!px-4 !py-2 text-xs">
        <Send className="size-3.5" /> Apply with Ada
      </Button>
      {error && <p className="max-w-52 text-right text-xs text-danger">{error}</p>}
    </div>
  );
}
