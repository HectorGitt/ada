"use client";

import { Eye, Loader2, Sparkles, TrendingUp } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Card, ScoreRing } from "@/components/ui";
import { api, type CandidateInsight } from "@/lib/api";

/** Ada's structured read of the candidate — the "elaborate profile" — plus the
 *  opt-in that lets Uche surface them to employers. Computed server-side on first
 *  view; we poll until it's ready. */
export function CandidateInsights() {
  const [insight, setInsight] = useState<CandidateInsight | null>(null);
  const [state, setState] = useState<"loading" | "computing" | "ready" | "none">("loading");
  const [discoverable, setDiscoverable] = useState(false);
  const [saving, setSaving] = useState(false);
  const polls = useRef(0);

  useEffect(() => {
    let live = true;
    const tick = async () => {
      try {
        const res = await api.getInsights();
        if (!live) return;
        if (res.ready && res.insights) {
          setInsight(res.insights);
          setDiscoverable(!!res.discoverable);
          setState("ready");
          return true;
        }
        if (res.reason === "no_profile") {
          setState("none");
          return true;
        }
        setState("computing");
        return false;
      } catch {
        setState("none");
        return true;
      }
    };
    void (async () => {
      if (await tick()) return;
      const id = setInterval(async () => {
        polls.current += 1;
        if ((await tick()) || polls.current > 20) clearInterval(id);
      }, 3000);
    })();
    return () => {
      live = false;
    };
  }, []);

  const toggle = async () => {
    const next = !discoverable;
    setSaving(true);
    setDiscoverable(next);
    try {
      await api.setDiscoverable(next);
    } catch {
      setDiscoverable(!next);
    } finally {
      setSaving(false);
    }
  };

  if (state === "none") return null;

  if (state !== "ready" || !insight) {
    return (
      <Card className="mb-6 p-6">
        <div className="flex items-center gap-2.5 text-sm text-muted">
          <Loader2 className="size-4 animate-spin" />
          Ada is analysing your profile…
        </div>
      </Card>
    );
  }

  return (
    <Card className="mb-6 overflow-hidden !p-0">
      <div className="flex items-start gap-5 border-b border-line p-6">
        <ScoreRing value={insight.readiness_score} size={72} stroke={6} />
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-1.5 text-xs font-medium text-accent">
            <Sparkles className="size-3.5" /> Ada&apos;s read of you
          </p>
          <h3 className="display mt-1 text-2xl">{insight.headline}</h3>
          <p className="mt-0.5 text-xs text-muted">
            {[insight.seniority, `${insight.years_experience} years`, insight.location]
              .filter(Boolean)
              .join(" · ")}
          </p>
          <p className="mt-3 text-sm leading-relaxed">{insight.summary}</p>
        </div>
      </div>

      <div className="grid gap-px bg-line sm:grid-cols-2">
        <InfoBlock label="Strengths" icon={<TrendingUp className="size-3.5" />} items={insight.strengths} />
        <InfoBlock label="Sharpen next" items={insight.growth_areas} muted />
      </div>

      <div className="border-t border-line p-6">
        <p className="eyebrow mb-2.5">Top skills</p>
        <div className="flex flex-wrap gap-1.5">
          {insight.top_skills.map((s) => (
            <span key={s} className="rounded-full bg-accent-soft px-3 py-1 text-xs font-medium text-accent">
              {s}
            </span>
          ))}
        </div>
        <p className="eyebrow mb-2 mt-5">Market fit</p>
        <p className="text-sm leading-relaxed text-muted">{insight.market_fit}</p>
      </div>

      {/* The consent wall — opt in to be found by employers via Uche */}
      <button
        onClick={toggle}
        disabled={saving}
        className={`flex w-full items-center gap-3 border-t border-line px-6 py-4 text-left transition-colors ${
          discoverable ? "bg-success-soft/40" : "hover:bg-surface-2"
        }`}
      >
        <span
          className={`relative h-6 w-10 shrink-0 rounded-full transition-colors ${
            discoverable ? "bg-success" : "bg-line"
          }`}
        >
          <span
            className={`absolute top-0.5 size-5 rounded-full bg-surface shadow-sm transition-all ${
              discoverable ? "left-[1.15rem]" : "left-0.5"
            }`}
          />
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5 text-sm font-medium">
            <Eye className="size-3.5" /> Let employers find me
          </span>
          <span className="mt-0.5 block text-xs text-muted">
            {discoverable
              ? "You're discoverable — Uche can surface you to employers hiring for your fit."
              : "Off — your profile is private. Turn on to be matched to employer roles."}
          </span>
        </span>
        {saving && <Loader2 className="size-4 animate-spin text-muted" />}
      </button>
    </Card>
  );
}

function InfoBlock({
  label,
  items,
  icon,
  muted,
}: {
  label: string;
  items: string[];
  icon?: React.ReactNode;
  muted?: boolean;
}) {
  return (
    <div className="bg-surface p-6">
      <p className="eyebrow mb-2.5 flex items-center gap-1.5">
        {icon}
        {label}
      </p>
      <ul className="space-y-1.5">
        {items.map((it) => (
          <li key={it} className={`text-sm leading-relaxed ${muted ? "text-muted" : ""}`}>
            {it}
          </li>
        ))}
      </ul>
    </div>
  );
}
