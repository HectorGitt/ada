"use client";

import { Plus, Trophy } from "lucide-react";
import { useEffect, useState } from "react";

import { Button, Card, Input, StatusBadge } from "@/components/ui";
import { api, type Outcome, type OutcomeStage, type Pipeline } from "@/lib/api";

// Forward funnel, in order. 'rejected' is terminal and lives outside the progression.
const STAGES: { key: OutcomeStage; label: string }[] = [
  { key: "applied", label: "Applied" },
  { key: "interviewing", label: "Interviewing" },
  { key: "offer", label: "Offer" },
  { key: "hired", label: "Hired" },
];

const STAGE_TONE: Record<OutcomeStage, "neutral" | "accent" | "success" | "warn" | "danger"> = {
  applied: "neutral",
  interviewing: "accent",
  offer: "warn",
  hired: "success",
  rejected: "danger",
};

const ALL_STAGES: OutcomeStage[] = ["applied", "interviewing", "offer", "hired", "rejected"];
const LABEL: Record<OutcomeStage, string> = {
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  hired: "Hired",
  rejected: "Rejected",
};

export function PipelinePanel() {
  const [data, setData] = useState<Pipeline | null>(null);
  const [adding, setAdding] = useState(false);
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");

  useEffect(() => {
    api.getPipeline().then(setData).catch(() => setData({ outcomes: [], funnel: {} }));
  }, []);

  const advance = async (o: Outcome, stage: OutcomeStage) => {
    if (stage === o.stage || !data) return;
    // Optimistic — revert on failure.
    const prev = data;
    setData({
      ...data,
      outcomes: data.outcomes.map((x) => (x.id === o.id ? { ...x, stage } : x)),
    });
    try {
      await api.advanceOutcome(o.id, stage);
      setData(await api.getPipeline());
    } catch {
      setData(prev);
    }
  };

  const add = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!company.trim() || !role.trim()) return;
    await api.addOutcome(company.trim(), role.trim(), "applied");
    setCompany("");
    setRole("");
    setAdding(false);
    setData(await api.getPipeline());
  };

  if (!data) return null;

  const hired = data.funnel.hired ?? 0;

  return (
    <section className="mb-8">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="eyebrow">Your pipeline</p>
          <p className="mt-1 text-sm text-muted">
            Where every role you&apos;re chasing stands — Ada logs each apply; you move it forward.
          </p>
        </div>
        <Button variant="ghost" onClick={() => setAdding((v) => !v)} className="!px-3 !py-2">
          <Plus className="size-4" /> Add a role
        </Button>
      </div>

      {/* Funnel summary */}
      <Card className="mb-3 flex flex-wrap items-stretch gap-2 p-3">
        {STAGES.map((s) => (
          <div key={s.key} className="min-w-[70px] flex-1 rounded-xl bg-surface-2 px-3 py-2.5 text-center">
            <p className="display text-2xl leading-none">{data.funnel[s.key] ?? 0}</p>
            <p className="mt-1 text-[11px] uppercase tracking-wide text-muted">{s.label}</p>
          </div>
        ))}
      </Card>

      {adding && (
        <Card className="mb-3 p-4">
          <form onSubmit={add} className="flex flex-wrap items-end gap-2">
            <div className="min-w-[140px] flex-1">
              <Input placeholder="Company" value={company} onChange={(e) => setCompany(e.target.value)} />
            </div>
            <div className="min-w-[140px] flex-1">
              <Input placeholder="Role" value={role} onChange={(e) => setRole(e.target.value)} />
            </div>
            <Button type="submit" className="!py-2.5">Track it</Button>
          </form>
        </Card>
      )}

      {data.outcomes.length === 0 ? (
        <Card className="flex items-center gap-3 px-5 py-4 text-sm text-muted">
          <Trophy className="size-4 shrink-0" />
          Nothing tracked yet. When Ada applies for you it shows up here — or add a role you&apos;re
          chasing elsewhere.
        </Card>
      ) : (
        <div className="space-y-2">
          {data.outcomes.map((o) => (
            <Card key={o.id} className="flex flex-wrap items-center justify-between gap-3 px-5 py-3.5">
              <div className="min-w-0">
                <p className="truncate font-medium">{o.role_title}</p>
                <p className="mt-0.5 text-xs text-muted">{o.company}</p>
              </div>
              <div className="flex items-center gap-2.5">
                <StatusBadge tone={STAGE_TONE[o.stage]}>{LABEL[o.stage]}</StatusBadge>
                <select
                  value={o.stage}
                  onChange={(e) => advance(o, e.target.value as OutcomeStage)}
                  aria-label={`Update stage for ${o.role_title}`}
                  className="rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs text-ink outline-none transition-colors focus:border-accent"
                >
                  {ALL_STAGES.map((s) => (
                    <option key={s} value={s}>{LABEL[s]}</option>
                  ))}
                </select>
              </div>
            </Card>
          ))}
        </div>
      )}

      {hired > 0 && (
        <p className="mt-3 flex items-center justify-center gap-1.5 text-sm font-medium text-success">
          <Trophy className="size-4" /> {hired} hire{hired > 1 ? "s" : ""} tracked. That&apos;s the whole point.
        </p>
      )}
    </section>
  );
}
