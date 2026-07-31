import { ArrowRight } from "lucide-react";
import Link from "next/link";

import {
  CareersBand,
  HeroHeadline,
  HeroShowcase,
  IntroVeil,
  Magnetic,
  Reveal,
  ScrollProgress,
  ScrubText,
  Timeline,
} from "@/components/marketing/demo";
import { PricingTiers } from "@/components/marketing/pricing";
import { DeliverablesShowcase } from "@/components/marketing/showcase";
import { AdaVoiceIntro } from "@/components/marketing/voice-intro";
import { Button, Eyebrow, Logo, ThemeToggle } from "@/components/ui";

const STEPS = [
  {
    title: "Tell Ada what you're going for",
    body: "Paste your CV and name the role — any role, any industry. Or just talk to her: a few minutes of voice intake is enough.",
  },
  {
    title: "Pay once, Ada runs",
    body: "₦2,000 or $9.99 unlocks the run. Paystack for Nigeria, cards for everywhere else.",
  },
  {
    title: "Your CV, rewritten for the role",
    body: "ATS-safe structure, recruiter vocabulary, achievement bullets — never invented facts.",
  },
  {
    title: "Your best-fit roles, ranked",
    body: "Semantic matching against real roles — scored, ranked, and explained.",
  },
  {
    title: "Interview-ready, with receipts",
    body: "Role-specific questions, then scored answers with feedback you can act on.",
  },
];

const FAQS = [
  {
    q: "What exactly do I get from a run?",
    a: "One complete run: your CV rewritten for a specific target role, a ranked list of best-fit roles with match scores, tailored interview questions, and scored feedback on your answers. Everything stays in your account.",
  },
  {
    q: "Is Ada only for tech jobs?",
    a: "No. Ada works for any career — nursing, sales, teaching, law, hospitality, finance, engineering, the lot. She rewrites for the vocabulary and conventions of your industry, not just software.",
  },
  {
    q: "Does a human read my CV?",
    a: "No. Ada does the entire run herself — rewrite, matching, interview prep, and scoring. That's the point: senior-level career help, delivered by an agent, in minutes.",
  },
  {
    q: "Will Ada invent experience I don't have?",
    a: "Never. Ada is explicitly constrained to work only with what you give her. She sharpens the truth; she doesn't fabricate employers, dates, or numbers.",
  },
  {
    q: "What if a run fails?",
    a: "Failed runs are never charged against — payment verification and execution are strictly tied, and a run that errors is flagged, not billed twice.",
  },
  {
    q: "How does Ada know my background for coaching?",
    a: "Import your LinkedIn profile (paste your profile text or export) once. Ada grounds every conversation and every run in it — advice about your actual career, not generic tips.",
  },
  {
    q: "Can I talk to Ada instead of typing?",
    a: "Yes. Voice intake is built in: Ada interviews you briefly, drafts your CV and target role from the conversation, and you review before paying.",
  },
];

function Nav() {
  return (
    <header className="fixed inset-x-0 top-4 z-40 px-4">
      <div className="mx-auto flex max-w-3xl items-center justify-between rounded-full border border-line/70 bg-surface/80 py-2 pl-5 pr-2 shadow-card backdrop-blur-xl">
        <Link href="/" aria-label="Ada home">
          <Logo />
        </Link>
        <nav className="flex items-center gap-1 text-sm text-muted max-sm:hidden">
          <a href="#how" className="rounded-full px-3 py-1.5 transition-colors hover:bg-line/40 hover:text-ink">
            How it works
          </a>
          <a href="#pricing" className="rounded-full px-3 py-1.5 transition-colors hover:bg-line/40 hover:text-ink">
            Pricing
          </a>
          <a href="#faqs" className="rounded-full px-3 py-1.5 transition-colors hover:bg-line/40 hover:text-ink">
            FAQs
          </a>
          <Link href="/assess" className="rounded-full px-3 py-1.5 transition-colors hover:bg-line/40 hover:text-ink">
            Free CV check
          </Link>
          <Link href="/hire" className="rounded-full px-3 py-1.5 transition-colors hover:bg-line/40 hover:text-ink">
            For employers
          </Link>
        </nav>
        <div className="flex items-center gap-1.5">
          <ThemeToggle />
          <Link href="/login" className="px-2 text-sm text-muted transition-colors hover:text-ink max-sm:hidden">
            Sign in
          </Link>
          <Link href="/app">
            <Button className="!py-2 text-[13px]">Open Ada</Button>
          </Link>
        </div>
      </div>
    </header>
  );
}

export default function Landing() {
  return (
    <>
      <IntroVeil />
      <ScrollProgress />
      <Nav />
      <main>
        {/* Hero — asymmetric editorial composition: type carries the left
            column, the live demo overlaps in from the right */}
        <section className="glow-field relative overflow-hidden">
          <div className="dot-grid absolute inset-0 -z-10" aria-hidden />
          <div className="mx-auto grid max-w-6xl items-start gap-14 px-5 pb-24 pt-32 sm:pt-36 lg:grid-cols-[1.15fr_0.85fr] lg:gap-4">
            <div>
              <Reveal>
                <p className="eyebrow mb-8 flex items-center gap-3">
                  <span className="h-px w-10 bg-accent" aria-hidden />
                  Autonomous career agent
                  <span className="flex items-center gap-1.5 normal-case tracking-normal text-success">
                    <span className="pulse-soft size-1.5 rounded-full bg-success" />
                    live
                  </span>
                </p>
              </Reveal>
              <HeroHeadline />
              <Reveal delay={0.5}>
                <p className="mt-8 max-w-md text-lg leading-relaxed text-muted">
                  One run: your CV rewritten for the role you want — in any industry —
                  your best-fit jobs ranked, and a scored mock interview. No humans in
                  the loop.
                </p>
              </Reveal>
              <Reveal delay={0.6}>
                <div className="mt-9 flex flex-wrap items-center gap-4">
                  <Magnetic>
                    <Link href="/app/new">
                      <Button className="group !px-8 !py-4 text-base">
                        Start your run
                        <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                      </Button>
                    </Link>
                  </Magnetic>
                  <Link
                    href="/app/voice"
                    className="text-sm text-muted underline-offset-4 transition-colors hover:text-ink hover:underline"
                  >
                    or talk to Ada first
                  </Link>
                </div>
              </Reveal>
              <Reveal delay={0.65}>
                <div className="mt-6">
                  <AdaVoiceIntro />
                </div>
              </Reveal>
              <Reveal delay={0.7}>
                {/* Sidenote, not a stat grid: the numbers live inside a sentence */}
                <p className="mt-12 max-w-md border-l-2 border-accent/40 pl-5 text-sm leading-loose text-muted">
                  Under <em className="display text-xl text-ink">three minutes</em> from
                  start to results. Pay{" "}
                  <em className="display text-xl text-ink">per run</em>, or go
                  unlimited from ₦5,000 a month.{" "}
                  <em className="display text-xl text-ink">Zero</em> humans reading
                  your CV.
                </p>
              </Reveal>
            </div>
            <Reveal delay={0.35} className="lg:mt-20">
              <HeroShowcase />
            </Reveal>
          </div>
        </section>

        {/* Every-career band */}
        <CareersBand />

        {/* Problem band — words brighten as you scroll through the statement */}
        <section className="bg-ink py-32 text-bg">
          <div className="mx-auto max-w-4xl px-5">
            <p className="eyebrow mb-6 !text-bg/50">The problem</p>
            <ScrubText
              className="display fluid-band leading-snug"
              segments={[
                {
                  text: "Job searching is a full-time job you didn’t apply for. Rewriting your CV for every role. Guessing what recruiters search for. Walking into interviews cold. Ada does all of it — in",
                },
                { text: "one run.", className: "text-accent italic" },
              ]}
            />
          </div>
        </section>

        {/* Deliverables — pinned scroll showcase on desktop, stacked on mobile */}
        <DeliverablesShowcase />

        {/* How it works — sticky editorial intro on the left, a timeline that
            draws itself on the right */}
        <section id="how" className="scroll-mt-24 border-y border-line bg-surface py-28">
          <div className="mx-auto grid max-w-6xl gap-14 px-5 lg:grid-cols-[0.9fr_1.1fr]">
            <div className="lg:sticky lg:top-28 lg:self-start">
              <Reveal>
                <Eyebrow>How it works</Eyebrow>
                <h2 className="display fluid-h2">
                  From CV to prepared, in five steps.
                </h2>
                <p className="mt-4 max-w-sm text-muted">
                  Starting the run takes a minute. Everything after that is Ada
                  working — the rail on the right is the whole process.
                </p>
                <Link href="/app/new" className="mt-8 inline-block">
                  <Button className="group">
                    Start a run
                    <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                  </Button>
                </Link>
              </Reveal>
            </div>
            <Timeline steps={STEPS} />
          </div>
        </section>

        {/* Pricing */}
        <section id="pricing" className="mx-auto max-w-6xl scroll-mt-24 px-5 py-28">
          <Reveal>
            <Eyebrow>Pricing</Eyebrow>
          </Reveal>
          <Reveal delay={0.05}>
            <PricingTiers />
          </Reveal>
        </section>

        {/* FAQs */}
        <section id="faqs" className="scroll-mt-24 border-t border-line bg-surface py-28">
          <div className="mx-auto grid max-w-6xl gap-10 px-5 lg:grid-cols-[1fr_2fr]">
            <Reveal>
              <Eyebrow>Questions</Eyebrow>
              <h2 className="display fluid-h2">FAQs.</h2>
            </Reveal>
            <div className="divide-y divide-line">
              {FAQS.map((faq, i) => (
                <Reveal key={faq.q} delay={i * 0.03}>
                  <details className="group py-5">
                    <summary className="flex cursor-pointer list-none items-center gap-4 text-[15px] font-medium transition-colors hover:text-accent [&::-webkit-details-marker]:hidden">
                      <span className="display w-8 shrink-0 text-lg text-muted/50">
                        {String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="flex-1">{faq.q}</span>
                      <span className="flex size-7 shrink-0 items-center justify-center rounded-full border border-line text-lg text-muted transition-transform duration-200 group-open:rotate-45">
                        +
                      </span>
                    </summary>
                    <p className="mt-3 max-w-2xl pl-12 text-sm leading-relaxed text-muted">
                      {faq.a}
                    </p>
                  </details>
                </Reveal>
              ))}
            </div>
          </div>
        </section>

        {/* CTA band */}
        <section className="relative overflow-hidden bg-ink py-32 text-center text-bg">
          <div
            className="absolute left-1/2 top-0 h-72 w-[46rem] -translate-x-1/2 rounded-full bg-accent/25 blur-3xl"
            aria-hidden
          />
          <Reveal className="relative">
            <h2 className="display fluid-hero mx-auto max-w-3xl px-5">
              Go in <em className="text-accent">prepared</em>.
            </h2>
            <p className="mx-auto mt-5 max-w-md px-5 text-balance text-bg/60">
              The next role is already out there. Ada gets you ready for it — whatever
              the industry.
            </p>
            <Magnetic className="mt-9">
              <Link href="/app/new" className="inline-block">
                <Button className="group !bg-bg !px-9 !py-4 text-base !text-ink !shadow-none hover:!opacity-90">
                  Start your run
                  <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                </Button>
              </Link>
            </Magnetic>
            <p className="mt-6 text-xs text-bg/50">
              ₦2,000 / $9.99 per run · Unlimited from ₦5,000 / $19 a month · Results in
              minutes
            </p>
          </Reveal>
        </section>
      </main>

      <footer className="overflow-hidden border-t border-line">
        <div className="mx-auto max-w-6xl px-5 pt-10">
          <div className="flex flex-wrap items-start justify-between gap-8">
            <div>
              <Logo className="text-base" />
              <p className="mt-2 max-w-xs text-xs leading-relaxed text-muted">
                An autonomous career agent — no human reads your CV. Rewrite, match,
                rehearse. One run at a time, for every industry.
              </p>
            </div>
            <nav className="flex gap-10 text-xs text-muted">
              <div className="space-y-2">
                <p className="font-medium text-ink">Product</p>
                <a href="#how" className="block transition-colors hover:text-ink">How it works</a>
                <a href="#pricing" className="block transition-colors hover:text-ink">Pricing</a>
                <a href="#faqs" className="block transition-colors hover:text-ink">FAQs</a>
              </div>
              <div className="space-y-2">
                <p className="font-medium text-ink">App</p>
                <Link href="/app/new" className="block transition-colors hover:text-ink">Start a run</Link>
                <Link href="/app/coach" className="block transition-colors hover:text-ink">Ask Ada</Link>
                <Link href="/login" className="block transition-colors hover:text-ink">Sign in</Link>
              </div>
              <div className="space-y-2">
                <p className="font-medium text-ink">Legal</p>
                <a href="https://recrulus.com/privacy" className="block transition-colors hover:text-ink">Privacy</a>
                <a href="https://recrulus.com/terms" className="block transition-colors hover:text-ink">Terms</a>
              </div>
            </nav>
          </div>
          <p className="mt-8 border-t border-line pt-6 text-xs text-muted">
            © {new Date().getFullYear()} Ada · Built for the next role, not the last one.
          </p>
        </div>
        {/* Oversized wordmark, cropped by the viewport */}
        <div className="pointer-events-none select-none" aria-hidden>
          <p className="display -mb-[0.24em] text-center text-[26vw] leading-[0.8] text-ink/[0.045]">
            Ada.
          </p>
        </div>
      </footer>
    </>
  );
}
