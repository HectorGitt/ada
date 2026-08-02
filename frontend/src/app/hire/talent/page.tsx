"use client";

import { BadgeCheck, Check, Plus, Search } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { EmployerShell } from "@/components/hire/shell";
import { Button, Card, Input, PageHeader, StatusBadge } from "@/components/ui";
import { api, type TalentCard } from "@/lib/api";

const SENIORITY = ["", "entry", "junior", "mid", "senior", "lead", "executive"];

export default function TalentPage() {
  return (
    <EmployerShell>
      <TalentSearch />
    </EmployerShell>
  );
}

function CandidateCard({ c, onSaved }: { c: TalentCard; onSaved?: (id: string) => void }) {
  const [saved, setSaved] = useState(!!c.saved);
  const save = async () => {
    setSaved(true);
    try {
      await api.saveToShortlist(c.user_id, null, null);
      onSaved?.(c.user_id);
    } catch {
      setSaved(false);
    }
  };
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 font-medium">
            {c.headline ?? "Candidate"}
            {c.identity_verified && <BadgeCheck className="size-4 text-success" />}
          </p>
          <p className="mt-0.5 text-xs text-muted">
            {[c.seniority, c.years_experience ? `${c.years_experience}y` : null, c.location]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {onSaved !== undefined &&
          (saved ? (
            <StatusBadge tone="success">
              <Check className="size-3.5" /> Saved
            </StatusBadge>
          ) : (
            <Button variant="secondary" onClick={save} className="!px-3 !py-1.5 text-xs">
              <Plus className="size-3.5" /> Save
            </Button>
          ))}
      </div>
      {c.top_skills.length > 0 && (
        <div className="mt-2.5 flex flex-wrap gap-1.5">
          {c.top_skills.slice(0, 6).map((s) => (
            <span key={s} className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-muted">
              {s}
            </span>
          ))}
        </div>
      )}
      {(c.compensation || c.work_pref) && (
        <p className="mt-2 text-xs text-muted">
          {[c.compensation, c.work_pref].filter(Boolean).join(" · ")}
        </p>
      )}
    </Card>
  );
}

function TalentSearch() {
  const [q, setQ] = useState("");
  const [location, setLocation] = useState("");
  const [seniority, setSeniority] = useState("");
  const [verified, setVerified] = useState(false);
  const [rows, setRows] = useState<TalentCard[] | null>(null);

  const run = useCallback(() => {
    setRows(null);
    api
      .searchTalent({ q, location, seniority, verified })
      .then((r) => setRows(r.candidates))
      .catch(() => setRows([]));
  }, [q, location, seniority, verified]);

  useEffect(() => {
    run();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [verified]);

  return (
    <>
      <PageHeader
        title="Talent."
        subtitle="Search the consented, Ada-verified candidate pool — not just applicants to one role."
      />

      <Card className="mb-4 p-4">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            run();
          }}
          className="flex flex-wrap items-end gap-2"
        >
          <div className="relative min-w-[160px] flex-1">
            <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input placeholder="Skill or role…" value={q} onChange={(e) => setQ(e.target.value)} className="!pl-9" />
          </div>
          <Input placeholder="Location" value={location} onChange={(e) => setLocation(e.target.value)} className="min-w-[120px] flex-1" />
          <select
            value={seniority}
            onChange={(e) => setSeniority(e.target.value)}
            className="rounded-xl border border-line bg-surface px-3 py-2.5 text-sm"
          >
            {SENIORITY.map((s) => (
              <option key={s} value={s}>{s || "Any level"}</option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-sm text-muted">
            <input type="checkbox" checked={verified} onChange={(e) => setVerified(e.target.checked)} />
            Verified only
          </label>
          <Button type="submit">Search</Button>
        </form>
      </Card>

      {rows === null ? (
        <p className="text-sm text-muted">Searching…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-muted">
          No candidates match yet. Candidates appear here once they opt into discovery.
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {rows.map((c) => (
            <CandidateCard key={c.user_id} c={c} onSaved={() => {}} />
          ))}
        </div>
      )}
    </>
  );
}
