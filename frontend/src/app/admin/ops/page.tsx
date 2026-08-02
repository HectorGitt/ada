"use client";

import { Loader2, RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";

import { Button, Card, StatusBadge } from "@/components/ui";
import { api, type AdminEvent, type AdminRun } from "@/lib/api";

const RUN_STATES = ["", "pending_payment", "paid", "running", "complete", "failed"];
const TONE: Record<string, "neutral" | "accent" | "success" | "warn" | "danger"> = {
  pending_payment: "warn",
  paid: "accent",
  running: "accent",
  complete: "success",
  failed: "danger",
};

export default function AdminOpsPage() {
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState("");
  const [status, setStatus] = useState("");
  const [runs, setRuns] = useState<AdminRun[] | null>(null);
  const [events, setEvents] = useState<AdminEvent[] | null>(null);

  const loadRuns = (s: string) => api.admin.runs(s).then(setRuns).catch(() => setRuns([]));
  useEffect(() => {
    void loadRuns(status);
  }, [status]);
  useEffect(() => {
    api.admin.events().then(setEvents).catch(() => setEvents([]));
  }, []);

  const trigger = async (label: string, fn: () => Promise<{ message: string }>) => {
    setBusy(label);
    setMsg("");
    try {
      setMsg((await fn()).message);
    } catch {
      setMsg("Failed to start.");
    } finally {
      setBusy("");
    }
  };

  return (
    <>
      <h1 className="display mb-4 text-3xl">Operations.</h1>

      <Card className="mb-5 p-4">
        <p className="text-sm font-medium">Job pipeline</p>
        <p className="mt-1 text-xs text-muted">
          Fetching is free; embedding needs billing — run them separately.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button loading={busy === "ingest"} onClick={() => trigger("ingest", api.admin.ingest)}>
            Run ingestion
          </Button>
          <Button
            variant="secondary"
            loading={busy === "embed"}
            onClick={() => trigger("embed", api.admin.embed)}
          >
            Backfill embeddings
          </Button>
          {msg && <span className="text-xs text-muted">{msg}</span>}
        </div>
      </Card>

      <div className="mb-3 flex items-center justify-between">
        <p className="text-sm font-medium">Runs</p>
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs"
        >
          {RUN_STATES.map((s) => (
            <option key={s} value={s}>
              {s || "all statuses"}
            </option>
          ))}
        </select>
      </div>

      {runs === null ? (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="size-4 animate-spin" /> Loading…
        </p>
      ) : (
        <div className="space-y-1.5">
          {runs.map((r) => (
            <Card key={r.id} className="flex flex-wrap items-center justify-between gap-2 px-4 py-2.5">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium">{r.target_role}</p>
                <p className="text-xs text-muted">
                  {r.currency} {(r.amount / 100).toLocaleString()} ·{" "}
                  {new Date(r.created_at).toLocaleDateString()}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <StatusBadge tone={TONE[r.status] ?? "neutral"}>{r.status}</StatusBadge>
                {(r.status === "paid" || r.status === "failed") && (
                  <button
                    onClick={() => api.admin.redispatch(r.id).then(() => setMsg(`Re-dispatched ${r.id.slice(0, 8)}`))}
                    className="flex items-center gap-1 text-xs text-muted hover:text-ink"
                  >
                    <RefreshCw className="size-3" /> re-dispatch
                  </button>
                )}
              </div>
            </Card>
          ))}
          {runs.length === 0 && <p className="text-sm text-muted">No runs.</p>}
        </div>
      )}

      <p className="mb-2 mt-6 text-sm font-medium">Payment events ledger</p>
      <Card className="p-4">
        {events === null ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : events.length === 0 ? (
          <p className="text-sm text-muted">No processed events.</p>
        ) : (
          <div className="space-y-1 font-mono text-xs">
            {events.map((e) => (
              <div key={e.id} className="flex justify-between text-muted">
                <span>{e.provider}</span>
                <span className="truncate pl-4">{e.reference}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
