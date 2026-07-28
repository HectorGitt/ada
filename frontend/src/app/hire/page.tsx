"use client";

import {
  ArrowRight,
  Briefcase,
  Check,
  Loader2,
  Plus,
  Sparkles,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import {
  Button,
  Card,
  EmptyState,
  Input,
  Label,
  Logo,
  ScoreRing,
  Skeleton,
  StatusBadge,
  Textarea,
  ThemeToggle,
} from "@/components/ui";
import {
  ApiError,
  api,
  type CandidateCard,
  type EmployerJob,
  type MeOut,
  type Shortlist,
} from "@/lib/api";

type Gate = "loading" | "anon" | "candidate" | "employer";

export default function HirePage() {
  const router = useRouter();
  const [gate, setGate] = useState<Gate>("loading");
  const [me, setMe] = useState<MeOut | null>(null);

  useEffect(() => {
    api
      .me()
      .then((m) => {
        setMe(m);
        setGate(m.account_type === "employer" ? "employer" : "candidate");
      })
      .catch(() => setGate("anon"));
  }, []);

  useEffect(() => {
    if (gate === "anon") router.replace("/login?next=/hire");
  }, [gate, router]);

  return (
    <div className="min-h-dvh bg-bg">
      <header className="sticky top-0 z-20 border-b border-line bg-surface/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-3">
          <Link href="/" className="flex items-center gap-2.5">
            <Logo />
            <span className="hidden rounded-full bg-accent-soft px-2 py-0.5 text-[11px] font-medium text-accent sm:inline">
              for employers
            </span>
          </Link>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            {me && <span className="hidden text-sm text-muted sm:inline">{me.company ?? me.email}</span>}
            <Link href="/app" className="text-sm text-muted transition-colors hover:text-ink">
              Candidate view
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-10">
        {gate === "loading" && <Skeleton className="h-64 w-full" />}
        {gate === "candidate" && me && <BecomeEmployer email={me.email} onDone={setMe} />}
        {gate === "employer" && <Console />}
      </main>
    </div>
  );
}

function BecomeEmployer({ email, onDone }: { email: string; onDone: (m: MeOut) => void }) {
  const [company, setCompany] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const m = await api.setAccount("employer", company.trim());
      onDone(m);
      location.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't switch to hiring mode.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-lg pt-10">
      <div className="mb-8 text-center">
        <span className="mb-4 inline-flex size-14 items-center justify-center rounded-2xl bg-ink text-bg">
          <Briefcase className="size-6" />
        </span>
        <h1 className="display text-4xl">Hire with Uche.</h1>
        <p className="mx-auto mt-3 max-w-sm text-muted">
          Uche reads your role and brings you a shortlist of vetted candidates — each
          already assessed by Ada, each with a reason they fit. No job boards, no noise.
        </p>
      </div>
      <Card className="p-7">
        <form onSubmit={submit} className="space-y-4">
          <div>
            <Label htmlFor="company">Company name</Label>
            <Input
              id="company"
              required
              autoFocus
              placeholder="Acme Foods"
              value={company}
              onChange={(e) => setCompany(e.target.value)}
            />
          </div>
          <p className="text-xs text-muted">
            Signed in as {email}. Switching to hiring mode keeps your candidate data intact.
          </p>
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" loading={busy} className="w-full !py-3">
            Enter hiring mode
            <ArrowRight className="size-4" />
          </Button>
        </form>
      </Card>
    </div>
  );
}

function Console() {
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
    <div>
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <p className="eyebrow mb-2">Hiring console</p>
          <h1 className="display text-4xl">Your open roles.</h1>
        </div>
        <Button onClick={() => setPosting(true)} className="shrink-0">
          <Plus className="size-4" /> Post a role
        </Button>
      </div>

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
          icon={<Briefcase className="size-5" />}
          title="No roles yet"
          body="Post your first role and Uche builds a vetted shortlist in seconds."
          action={<Button onClick={() => setPosting(true)}>Post a role</Button>}
        />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[0.9fr_1.6fr]">
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
    </div>
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
            Post & find candidates
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
            {[c.seniority, c.years_experience ? `${c.years_experience}y` : null, c.location]
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
