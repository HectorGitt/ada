"use client";

import { BadgeCheck, Trophy } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { EmployerShell } from "@/components/hire/shell";
import { Card, PageHeader, StatusBadge } from "@/components/ui";
import { api, type ShortlistStage, type TalentCard } from "@/lib/api";

const STAGES: ShortlistStage[] = [
  "shortlisted", "contacted", "interviewing", "offer", "hired", "passed",
];
const FUNNEL: ShortlistStage[] = ["shortlisted", "contacted", "interviewing", "offer", "hired"];
const TONE: Record<ShortlistStage, "neutral" | "accent" | "warn" | "success" | "danger"> = {
  shortlisted: "neutral",
  contacted: "accent",
  interviewing: "accent",
  offer: "warn",
  hired: "success",
  passed: "danger",
};

export default function ShortlistPage() {
  return (
    <EmployerShell>
      <Pipeline />
    </EmployerShell>
  );
}

function Pipeline() {
  const [rows, setRows] = useState<TalentCard[] | null>(null);
  const [funnel, setFunnel] = useState<Record<string, number>>({});

  const load = useCallback(() => {
    api.getShortlist()
      .then((r) => {
        setRows(r.candidates);
        setFunnel(r.funnel);
      })
      .catch(() => setRows([]));
  }, []);
  useEffect(load, [load]);

  const setStage = async (c: TalentCard, stage: ShortlistStage) => {
    if (!rows) return;
    setRows(rows.map((x) => (x.user_id === c.user_id ? { ...x, stage } : x)));
    await api.updateShortlist(c.user_id, stage, null).catch(() => {});
    load();
  };

  const remove = async (c: TalentCard) => {
    if (!confirm("Remove this candidate from your pipeline?")) return;
    await api.removeFromShortlist(c.user_id).catch(() => {});
    load();
  };

  const hires = funnel.hired ?? 0;

  return (
    <>
      <PageHeader title="Pipeline." subtitle="Everyone you've saved, moving from shortlisted to hired." />

      <Card className="mb-4 flex flex-wrap gap-2 p-3">
        {FUNNEL.map((s) => (
          <div key={s} className="min-w-[80px] flex-1 rounded-xl bg-surface-2 px-3 py-2.5 text-center">
            <p className="display text-2xl leading-none">{funnel[s] ?? 0}</p>
            <p className="mt-1 text-[11px] capitalize text-muted">{s}</p>
          </div>
        ))}
      </Card>

      {rows === null ? (
        <p className="text-sm text-muted">Loading…</p>
      ) : rows.length === 0 ? (
        <Card className="flex items-center gap-3 px-5 py-4 text-sm text-muted">
          <Trophy className="size-4 shrink-0" />
          No one saved yet. Search Talent and save candidates to build your pipeline.
        </Card>
      ) : (
        <div className="space-y-2">
          {rows.map((c) => (
            <Card key={c.user_id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
              <div className="min-w-0">
                <p className="flex items-center gap-1.5 text-sm font-medium">
                  {c.headline ?? "Candidate"}
                  {c.identity_verified && <BadgeCheck className="size-4 text-success" />}
                </p>
                <p className="mt-0.5 text-xs text-muted">
                  {[c.seniority, c.location].filter(Boolean).join(" · ")}
                </p>
              </div>
              <div className="flex items-center gap-2">
                {c.stage && <StatusBadge tone={TONE[c.stage]}>{c.stage}</StatusBadge>}
                <select
                  value={c.stage ?? "shortlisted"}
                  onChange={(e) => setStage(c, e.target.value as ShortlistStage)}
                  className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs"
                >
                  {STAGES.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <button
                  onClick={() => remove(c)}
                  className="text-xs text-muted underline-offset-2 hover:text-danger hover:underline"
                >
                  remove
                </button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {hires > 0 && (
        <p className="mt-3 flex items-center justify-center gap-1.5 text-sm font-medium text-success">
          <Trophy className="size-4" /> {hires} hire{hires > 1 ? "s" : ""} — that&apos;s the whole point.
        </p>
      )}
    </>
  );
}
