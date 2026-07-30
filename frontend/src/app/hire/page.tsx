"use client";

import { Check, Loader2, Plus, Sparkles, UserRound } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { EmployerShell } from "@/components/hire/shell";
import {
  Button,
  Card,
  EmptyState,
  Input,
  Label,
  PageHeader,
  ScoreRing,
  Skeleton,
  StatusBadge,
  Textarea,
} from "@/components/ui";
import {
  ApiError,
  api,
  type CandidateCard,
  type EmployerJob,
  type Shortlist,
} from "@/lib/api";

export default function HirePage() {
  return (
    <EmployerShell>
      <RolesConsole />
    </EmployerShell>
  );
}

function RolesConsole() {
  const [jobs, setJobs] = useState<EmployerJob[] | null>(null);
  const [activeId, setActiveId] = useState<number | null>(null);
  const [posting, setPosting] = useState(false);

  const load = useCallback(async () => {
    const list = await api.employerJobs().catch(() => []);
    setJobs(list);
    setActiveId((cur) => cur ?? list[0]?.id ?? null);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="Your roles."
        subtitle="Post a role and Uche builds a vetted shortlist — ranked, with the reason each candidate fits."
        action={
          <Button onClick={() => setPosting(true)}>
            <Plus className="size-4" /> Post a role
          </Button>
        }
      />

      {posting && (
        <PostRole
          onClose={() => setPosting(false)}
          onPosted={async (job) => {
            setPosting(false);
            await load();
            setActiveId(job.id);
          }}
        />
      )}

      {jobs === null ? (
        <Skeleton className="h-40 w-full" />
      ) : jobs.length === 0 && !posting ? (
        <EmptyState
          icon={<UserRound className="size-5" />}
          title="No roles yet"
          body="Post your first role and Uche builds a vetted shortlist in seconds."
          action={<Button onClick={() => setPosting(true)}>Post a role</Button>}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[0.85fr_1.6fr]">
          <div className="space-y-2.5">
            {jobs.map((job) => (
              <button
                key={job.id}
                onClick={() => setActiveId(job.id)}
                className={`w-full rounded-card border px-5 py-4 text-left transition-colors ${
                  activeId === job.id
                    ? "border-accent bg-accent-soft/50"
                    : "border-line bg-surface hover:border-line/80 hover:bg-surface-2"
                }`}
              >
                <p className="font-medium">{job.title}</p>
                <p className="mt-0.5 text-xs text-muted">
                  {job.company} · {job.remote ? "Remote" : job.location}
                </p>
              </button>
            ))}
          </div>
          <div>{activeId !== null && <ShortlistPanel jobId={activeId} />}</div>
        </div>
      )}
    </>
  );
}

function PostRole({
  onClose,
  onPosted,
}: {
  onClose: () => void;
  onPosted: (job: EmployerJob) => void;
}) {
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [remote, setRemote] = useState(false);
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const job = await api.postJob({
        title: title.trim(),
        company: company.trim() || "Company",
        location: location.trim() || "Remote",
        remote,
        description: description.trim(),
      });
      onPosted(job);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't post the role.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="mb-6 p-6">
      <form onSubmit={submit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label htmlFor="title">Role title</Label>
            <Input id="title" required placeholder="Regional Sales Manager" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="co">Company</Label>
            <Input id="co" placeholder="Acme Foods" value={company} onChange={(e) => setCompany(e.target.value)} />
          </div>
          <div>
            <Label htmlFor="loc">Location</Label>
            <Input id="loc" placeholder="Lagos" value={location} onChange={(e) => setLocation(e.target.value)} />
          </div>
          <label className="flex items-center gap-2.5 pt-6 text-sm">
            <input type="checkbox" checked={remote} onChange={(e) => setRemote(e.target.checked)} className="size-4 accent-[var(--accent)]" />
            Remote role
          </label>
        </div>
        <div>
          <Label htmlFor="desc">What you&apos;re looking for</Label>
          <Textarea
            id="desc"
            rows={5}
            required
            minLength={20}
            placeholder="The responsibilities, must-have experience, and the kind of person who thrives here. Uche reads this to rank candidates."
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
        <div className="flex gap-2.5">
          <Button type="submit" loading={busy}>
            Post &amp; find candidates
          </Button>
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Card>
  );
}

function ShortlistPanel({ jobId }: { jobId: number }) {
  const [data, setData] = useState<Shortlist | null>(null);

  useEffect(() => {
    setData(null);
    let live = true;
    api
      .curatedCandidates(jobId)
      .then((d) => live && setData(d))
      .catch(() => live && setData({ summary: "", candidates: [] }));
    return () => {
      live = false;
    };
  }, [jobId]);

  if (data === null) {
    return (
      <Card className="p-6">
        <div className="flex items-center gap-2.5 text-sm text-muted">
          <Loader2 className="size-4 animate-spin" /> Uche is reviewing candidates…
        </div>
      </Card>
    );
  }

  if (data.unavailable) {
    return (
      <Card className="p-6 text-sm text-muted">
        Candidate ranking needs the model service configured. Postings and consent still work.
      </Card>
    );
  }

  if (data.candidates.length === 0) {
    return (
      <EmptyState
        icon={<UserRound className="size-5" />}
        title="No matches yet"
        body="No consented candidates fit this role yet. As candidates opt in, Uche's shortlist fills in."
      />
    );
  }

  return (
    <div>
      {data.summary && (
        <Card className="mb-4 border-accent/30 bg-accent-soft/40 p-5">
          <p className="flex items-center gap-2 text-xs font-medium text-accent">
            <Sparkles className="size-3.5" /> Uche&apos;s read
          </p>
          <p className="mt-2 text-sm leading-relaxed">{data.summary}</p>
        </Card>
      )}
      <div className="space-y-3">
        {data.candidates.map((c) => (
          <CandidateRow key={c.user_id} jobId={jobId} c={c} />
        ))}
      </div>
    </div>
  );
}

const VERDICT: Record<string, { label: string; tone: "success" | "accent" | "warn" }> = {
  strong: { label: "Strong fit", tone: "success" },
  good: { label: "Good fit", tone: "accent" },
  stretch: { label: "Stretch", tone: "warn" },
};

function CandidateRow({ jobId, c }: { jobId: number; c: CandidateCard }) {
  const [requested, setRequested] = useState(!!c.intro_requested);
  const [busy, setBusy] = useState(false);
  const verdict = VERDICT[c.verdict] ?? VERDICT.good;

  const intro = async () => {
    setBusy(true);
    try {
      await api.requestIntro(jobId, c.user_id, null);
      setRequested(true);
    } catch {
      /* leave button */
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-5">
      <div className="flex items-start gap-4">
        <ScoreRing value={c.match} size={52} stroke={5} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">{c.headline ?? "Candidate"}</p>
            <StatusBadge tone={verdict.tone}>{verdict.label}</StatusBadge>
          </div>
          <p className="mt-0.5 text-xs text-muted">
            {[
              c.seniority,
              c.years_experience ? `${c.years_experience}y` : null,
              c.location,
              c.work_pref,
              c.compensation,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
          {c.rationale && <p className="mt-2 text-sm leading-relaxed text-muted">{c.rationale}</p>}
          {c.top_skills.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {c.top_skills.slice(0, 6).map((s) => (
                <span key={s} className="rounded-full bg-surface-2 px-2.5 py-0.5 text-[11px] text-muted">
                  {s}
                </span>
              ))}
            </div>
          )}
        </div>
        <div className="shrink-0">
          {requested ? (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-success-soft px-3 py-1.5 text-xs font-medium text-success">
              <Check className="size-3.5" /> Intro sent
            </span>
          ) : (
            <Button onClick={intro} loading={busy} variant="secondary" className="!px-4 !py-2 text-xs">
              Request intro
            </Button>
          )}
        </div>
      </div>
    </Card>
  );
}
