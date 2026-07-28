"use client";

import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";

import { Magnetic, Reveal, ScrollProgress } from "@/components/marketing/demo";
import { Button, ThemeToggle } from "@/components/ui";

/** Uche's front door — the marketing landing served at uche.recrulus.com/.
 *  Same design system as Ada's landing, employer voice. The console stays at /hire. */

function UcheMark({ className = "" }: { className?: string }) {
  return (
    <span className={`display select-none text-[1.35rem] leading-none text-ink ${className}`}>
      Uche<span className="text-accent">.</span>
    </span>
  );
}

function Nav() {
  return (
    <header className="fixed inset-x-0 top-4 z-40 px-4">
      <div className="mx-auto flex max-w-3xl items-center justify-between rounded-full border border-line/70 bg-surface/80 py-2 pl-5 pr-2 shadow-card backdrop-blur-xl">
        <Link href="/" aria-label="Uche home">
          <UcheMark />
        </Link>
        <nav className="flex items-center gap-1 text-sm text-muted max-sm:hidden">
          <a href="#how" className="rounded-full px-3 py-1.5 transition-colors hover:bg-line/40 hover:text-ink">
            How it works
          </a>
          <a
            href="https://ada.recrulus.com"
            className="rounded-full px-3 py-1.5 transition-colors hover:bg-line/40 hover:text-ink"
          >
            For candidates
          </a>
        </nav>
        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          <Link
            href="/login?next=/hire"
            className="px-2 text-sm text-muted transition-colors hover:text-ink max-sm:hidden"
          >
            Sign in
          </Link>
          <Link href="/hire">
            <Button className="!py-2 text-[13px]">Open the console</Button>
          </Link>
        </div>
      </div>
    </header>
  );
}

const PIPELINE = [
  { label: "Role posted", note: "one intake", done: true },
  { label: "Applicants screened", note: "142 reviewed", done: true },
  { label: "Shortlist ranked", note: "top 8 surfaced", done: true },
  { label: "Interviews prepped", note: "questions drafted", active: true },
];

function PipelineCard() {
  return (
    <div className="rounded-2xl border border-line bg-surface p-6 shadow-card">
      <div className="flex items-center justify-between border-b border-line pb-4">
        <UcheMark className="!text-lg" />
        <span className="rounded-full bg-accent-soft px-3 py-1 text-xs text-accent">
          pipeline live
        </span>
      </div>
      <ol className="mt-5 space-y-4 text-sm">
        {PIPELINE.map((s) => (
          <li key={s.label} className="flex items-center gap-4">
            <span
              className={`flex size-6 shrink-0 items-center justify-center rounded-full border text-[10px] ${
                s.active ? "border-accent text-accent" : "border-line text-muted"
              }`}
            >
              {s.done ? <Check className="size-3" /> : "●"}
            </span>
            <span className={s.active ? "text-ink" : "text-muted"}>{s.label}</span>
            <span className="ml-auto text-xs text-muted/70">{s.note}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

const STEPS = [
  {
    title: "Post the role once",
    body: "Title, must-haves, context — one form, a few minutes. That's the last hiring admin you do.",
  },
  {
    title: "Uche screens everyone",
    body: "Every applicant is assessed against your role — skills, evidence, trajectory — not keyword-matched.",
  },
  {
    title: "A shortlist worth your time",
    body: "The top candidates, ranked, each with the reason they fit. Candidates already assessed by Ada arrive with receipts.",
  },
  {
    title: "Interviews, prepped",
    body: "Role-specific questions drafted for each shortlisted candidate. You walk in ready; consented intros connect you.",
  },
];

export default function UcheLanding() {
  return (
    <>
      <ScrollProgress />
      <Nav />
      <main>
        <section className="glow-field relative overflow-hidden">
          <div className="dot-grid absolute inset-0 -z-10" aria-hidden />
          <div className="mx-auto grid max-w-6xl items-center gap-14 px-5 pb-24 pt-32 sm:pt-36 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <Reveal>
                <p className="eyebrow mb-8 flex items-center gap-3">
                  <span className="h-px w-10 bg-accent" aria-hidden />
                  Autonomous employer agent
                </p>
              </Reveal>
              <Reveal delay={0.15}>
                <h1 className="display text-5xl leading-[1.04] sm:text-6xl">
                  Hiring that <em className="text-accent">runs itself</em>.
                </h1>
              </Reveal>
              <Reveal delay={0.3}>
                <p className="mt-8 max-w-md text-lg leading-relaxed text-muted">
                  Post a role once. Uche screens every applicant against it, ranks
                  the shortlist worth your time, and preps your interviews — while
                  you do your actual job.
                </p>
              </Reveal>
              <Reveal delay={0.45}>
                <div className="mt-9 flex flex-wrap items-center gap-4">
                  <Magnetic>
                    <Link href="/hire">
                      <Button className="group !px-8 !py-4 text-base">
                        Post your first role
                        <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                      </Button>
                    </Link>
                  </Magnetic>
                  <a
                    href="https://ada.recrulus.com"
                    className="text-sm text-muted underline-offset-4 transition-colors hover:text-ink hover:underline"
                  >
                    Looking for a job instead? Meet Ada →
                  </a>
                </div>
              </Reveal>
            </div>
            <Reveal delay={0.35}>
              <PipelineCard />
            </Reveal>
          </div>
        </section>

        <section id="how" className="border-t border-line px-5 py-24">
          <div className="mx-auto max-w-6xl">
            <Reveal>
              <p className="eyebrow">How it works</p>
              <h2 className="display mt-4 max-w-xl text-3xl leading-tight sm:text-4xl">
                The other side of the table, finally automated.
              </h2>
            </Reveal>
            <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-line bg-line sm:grid-cols-2">
              {STEPS.map((s, i) => (
                <Reveal key={s.title} delay={i * 0.08}>
                  <div className="h-full bg-bg p-7 transition-colors hover:bg-surface">
                    <span className="text-xs text-muted/70">{String(i + 1).padStart(2, "0")}</span>
                    <h3 className="mt-3 font-medium">{s.title}</h3>
                    <p className="mt-2.5 text-sm leading-relaxed text-muted">{s.body}</p>
                  </div>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        <section className="border-t border-line px-5 py-24">
          <div className="mx-auto max-w-3xl text-center">
            <Reveal>
              <h2 className="display text-3xl leading-tight sm:text-5xl">
                Your next hire is already in the pipeline.
              </h2>
              <p className="mx-auto mt-5 max-w-md text-muted">
                Candidates on Ada arrive assessed, scored, and consenting to be
                found. Uche puts them in front of you.
              </p>
              <div className="mt-9">
                <Magnetic>
                  <Link href="/hire">
                    <Button className="group !px-8 !py-4 text-base">
                      Open the console
                      <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                    </Button>
                  </Link>
                </Magnetic>
              </div>
            </Reveal>
          </div>
        </section>
      </main>

      <footer className="border-t border-line px-5 py-10">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 text-sm text-muted">
          <UcheMark />
          <p>A Recrulus product — Ada gets people hired, Uche gets roles filled.</p>
          <span className="flex items-center gap-5">
            <a href="https://recrulus.com" className="transition-colors hover:text-ink">
              Recrulus ↗
            </a>
            <a href="https://ada.recrulus.com" className="transition-colors hover:text-ink">
              Ada ↗
            </a>
          </span>
        </div>
      </footer>
    </>
  );
}
