"use client";

import { ArrowRight, Check, Loader2, Share2, Sparkles, Upload } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { Button, Card, Input, Label, Logo, ScoreRing, Textarea, ThemeToggle } from "@/components/ui";
import { ApiError, api, type CvAssessment } from "@/lib/api";
import { encodeCard } from "@/lib/share";

export default function AssessPage() {
  const [cv, setCv] = useState("");
  const [role, setRole] = useState("");
  const [result, setResult] = useState<CvAssessment | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [shared, setShared] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  // Upload a CV file → extract its text into the box (nothing is stored).
  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const { cv_text } = await api.extractCv(file);
      setCv(cv_text);
      setFileName(file.name);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't read that file — try a PDF or DOCX.");
    } finally {
      setUploading(false);
      if (fileInput.current) fileInput.current.value = ""; // allow re-selecting the same file
    }
  };

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      setResult(await api.assessCv(cv.trim(), role.trim() || null));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Couldn't assess that — try again.");
    } finally {
      setBusy(false);
    }
  };

  // Share the score: native share sheet where available, clipboard everywhere else.
  const share = async () => {
    if (!result) return;
    const url = `${location.origin}/s/${encodeCard({ score: result.score, role: role.trim() })}`;
    const text = `My CV scored ${result.score}/100 on Ada. Check yours free:`;
    try {
      if (navigator.share) {
        await navigator.share({ title: "My CV readiness", text, url });
        return;
      }
    } catch {
      return; // user dismissed the share sheet
    }
    await navigator.clipboard.writeText(url).catch(() => {});
    setShared(true);
    setTimeout(() => setShared(false), 2000);
  };

  // Hand the CV to the paid run flow — signup picks it up and pre-fills.
  const upgrade = () => {
    localStorage.setItem(
      "ada.intake-draft",
      JSON.stringify({ target_role: role.trim(), cv_text: cv.trim() }),
    );
  };

  return (
    <div className="min-h-dvh bg-bg">
      <header className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
        <Link href="/" aria-label="Ada home">
          <Logo />
        </Link>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <Link href="/login" className="text-sm text-muted transition-colors hover:text-ink">
            Sign in
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 pb-24 pt-8">
        <p className="eyebrow mb-3">Free CV check</p>
        <h1 className="display text-4xl sm:text-5xl">How ready is your CV?</h1>
        <p className="mt-3 max-w-xl text-muted">
          Paste it in — Ada scores it and gives you the three highest-impact fixes, free.
          No signup. The full rewrite is one click away.
        </p>

        {!result ? (
          <Card className="mt-8 p-6">
            <form onSubmit={run} className="space-y-4">
              <div>
                <Label htmlFor="role">Target role (optional)</Label>
                <Input
                  id="role"
                  placeholder="e.g. Product Manager"
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                />
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between gap-3">
                  <label htmlFor="cv" className="block text-[13px] font-medium text-ink">
                    Your CV
                  </label>
                  <input
                    ref={fileInput}
                    type="file"
                    accept=".pdf,.docx,.txt"
                    onChange={onFile}
                    className="hidden"
                  />
                  <button
                    type="button"
                    onClick={() => fileInput.current?.click()}
                    disabled={uploading}
                    className="inline-flex items-center gap-1.5 rounded-full border border-line px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-ink/30 hover:text-ink disabled:opacity-60"
                  >
                    {uploading ? <Loader2 className="size-3.5 animate-spin" /> : <Upload className="size-3.5" />}
                    {uploading ? "Reading…" : fileName ? "Replace file" : "Upload PDF / DOCX"}
                  </button>
                </div>
                {fileName && (
                  <p className="mb-1.5 flex items-center gap-1.5 text-xs text-success">
                    <Check className="size-3.5" /> {fileName} — text pulled in below, edit if needed.
                  </p>
                )}
                <Textarea
                  id="cv"
                  rows={12}
                  required
                  minLength={100}
                  placeholder="Paste the whole thing — or upload a file above. Experience, education, the lot."
                  value={cv}
                  onChange={(e) => setCv(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-danger">{error}</p>}
              <Button type="submit" loading={busy} className="!py-3">
                {busy ? <Loader2 className="size-4 animate-spin" /> : "Assess my CV"}
              </Button>
            </form>
          </Card>
        ) : (
          <div className="mt-8 space-y-5">
            <Card className="flex items-center gap-5 p-6">
              <ScoreRing value={result.score} size={80} stroke={7} />
              <div className="min-w-0 flex-1">
                <p className="eyebrow !text-[10px]">Readiness</p>
                <p className="display mt-1 text-2xl">{result.headline}</p>
              </div>
              <Button variant="secondary" onClick={share} className="shrink-0 !px-4 !py-2.5">
                {shared ? <Check className="size-4" /> : <Share2 className="size-4" />}
                {shared ? "Link copied" : "Share"}
              </Button>
            </Card>

            <div>
              <p className="eyebrow mb-3">Your three highest-impact fixes</p>
              <div className="space-y-3">
                {result.fixes.map((f, i) => (
                  <Card key={i} className="p-5">
                    <p className="flex items-center gap-2 font-medium">
                      <span className="flex size-5 items-center justify-center rounded-full bg-accent-soft text-[11px] font-semibold text-accent">
                        {i + 1}
                      </span>
                      {f.title}
                    </p>
                    <p className="mt-1.5 text-sm leading-relaxed text-muted">{f.detail}</p>
                    {f.quote && (
                      <p className="mt-2 border-l-2 border-line pl-3 text-xs italic text-muted/80">
                        “{f.quote}”
                      </p>
                    )}
                  </Card>
                ))}
              </div>
            </div>

            <Card className="border-accent/30 bg-accent-soft/40 p-6 text-center">
              <p className="flex items-center justify-center gap-2 text-sm font-medium text-accent">
                <Sparkles className="size-4" /> That&apos;s the free taste.
              </p>
              <p className="mx-auto mt-2 max-w-md text-sm text-muted">
                Ada does the full rewrite for the role you want, ranks your best-fit jobs, and
                preps a scored mock interview — in minutes.
              </p>
              <Link href="/login?next=/app/new" onClick={upgrade}>
                <Button className="group mt-4 !px-7 !py-3">
                  Get the full rewrite
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </Button>
              </Link>
              <button
                onClick={() => setResult(null)}
                className="mt-3 block w-full text-xs text-muted underline-offset-2 hover:underline"
              >
                <Check className="mr-1 inline size-3" /> Assess another
              </button>
            </Card>
          </div>
        )}
      </main>
    </div>
  );
}
