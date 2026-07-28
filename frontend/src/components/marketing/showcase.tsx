"use client";

import { motion, useMotionValueEvent, useReducedMotion, useScroll } from "motion/react";
import { useRef, useState } from "react";

import { Reveal } from "@/components/marketing/demo";
import { Card, Eyebrow, ScoreBar } from "@/components/ui";

/** Pinned deliverables showcase: on large screens the section is 300vh tall and
 *  the viewport pins while scroll drives which deliverable is on stage —
 *  rewrite, match, rehearse. On small screens (and under reduced motion via
 *  shorter travel) it degrades to a simple stacked list of the same content. */

const ITEMS = [
  {
    n: "01",
    label: "Rewrite",
    title: "Your CV, rewritten for the role",
    body: "ATS-safe headers, your industry's vocabulary, duties turned into achievement bullets. Your facts only — sharpened, never invented.",
  },
  {
    n: "02",
    label: "Match",
    title: "Your best-fit roles, ranked",
    body: "Semantic search over real roles — ranked by fit against your actual experience, each with a reason, not just a keyword hit.",
  },
  {
    n: "03",
    label: "Rehearse",
    title: "A scored mock interview",
    body: "Role-specific questions, then honest 0–10 scoring with feedback you can use in the real room.",
  },
];

function CVPanel() {
  return (
    <Card className="p-6 shadow-lift">
      <p className="eyebrow mb-2 !text-[10px]">Before</p>
      <p className="text-sm text-muted/70 line-through">
        Responsible for taking care of patients on the night shift.
      </p>
      <p className="eyebrow mb-2 mt-5 flex items-center gap-2 !text-[10px] !text-accent">
        After — Ada&apos;s rewrite
      </p>
      <ul className="space-y-2.5 text-sm leading-relaxed">
        <li className="flex gap-2.5">
          <span className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
          Cut triage-to-treatment time 30% by redesigning the night-intake flow
        </li>
        <li className="flex gap-2.5">
          <span className="mt-2 size-1.5 shrink-0 rounded-full bg-accent" />
          Led a 12-nurse night team across two wards with zero missed handovers
        </li>
      </ul>
      <p className="mt-5 border-t border-line pt-3 text-xs text-muted">
        Same facts. Recruiter vocabulary. ATS-safe structure.
      </p>
    </Card>
  );
}

function MatchPanel() {
  return (
    <Card className="space-y-4 p-6 shadow-lift">
      {[
        ["Marketing Manager", "Nestlé · Lagos", 91],
        ["Brand Manager", "Unilever · Hybrid", 86],
        ["Growth Lead", "Piggyvest · Remote", 82],
      ].map(([title, meta, score]) => (
        <div key={title as string}>
          <div className="flex items-baseline justify-between gap-3">
            <div className="min-w-0">
              <p className="truncate text-sm font-medium">{title}</p>
              <p className="text-[11px] text-muted">{meta}</p>
            </div>
            <span className="display text-xl text-accent">{score}%</span>
          </div>
          <div className="mt-1.5">
            <ScoreBar value={score as number} />
          </div>
        </div>
      ))}
      <p className="border-t border-line pt-3 text-xs text-muted">
        Each match comes with the reason it fits — not just a keyword hit.
      </p>
    </Card>
  );
}

function InterviewPanel() {
  return (
    <Card className="p-6 shadow-lift">
      <p className="text-sm text-muted">
        “Tell me about a time you turned around an unhappy client.”
      </p>
      <p className="mt-3 border-l-2 border-line pl-3 text-sm italic leading-relaxed text-muted">
        “Our biggest account threatened to leave after two late deliveries, so I…”
      </p>
      <div className="mt-4 flex items-center gap-3">
        <ScoreBar value={8} max={10} />
        <span className="display shrink-0 text-lg">8/10</span>
      </div>
      <p className="mt-3 text-sm leading-relaxed text-muted">
        Clear story, strong result. Say how big the account you saved was — numbers
        land.
      </p>
    </Card>
  );
}

const PANELS = [CVPanel, MatchPanel, InterviewPanel];

export function DeliverablesShowcase() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const [active, setActive] = useState(0);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start start", "end end"],
  });
  useMotionValueEvent(scrollYProgress, "change", (v) => {
    setActive(Math.min(ITEMS.length - 1, Math.floor(v * ITEMS.length)));
  });

  return (
    <section className="mx-auto max-w-6xl px-5 py-28 lg:py-0">
      <div className="lg:pt-28">
        <Reveal>
          <Eyebrow>What you get</Eyebrow>
          <h2 className="display fluid-h2">One run. Three deliverables.</h2>
        </Reveal>
      </div>

      {/* Pinned, scroll-driven (desktop) */}
      <div ref={ref} className="relative hidden h-[300vh] lg:block">
        <div className="sticky top-0 flex h-dvh items-center">
          <div className="grid w-full grid-cols-[1fr_1.1fr] items-center gap-16">
            <div className="space-y-9">
              {ITEMS.map((item, i) => {
                const on = i === active;
                return (
                  <div
                    key={item.n}
                    className={`border-l-2 pl-6 transition-all duration-500 ${
                      on ? "border-accent" : "border-line"
                    }`}
                  >
                    <p
                      className={`display text-3xl transition-colors duration-500 ${
                        on ? "text-accent" : "text-muted/50"
                      }`}
                    >
                      {item.n}
                    </p>
                    <h3
                      className={`mb-1.5 mt-2 font-semibold transition-opacity duration-500 ${
                        on ? "opacity-100" : "opacity-45"
                      }`}
                    >
                      {item.title}
                    </h3>
                    <p
                      className={`max-w-sm text-sm leading-relaxed text-muted transition-opacity duration-500 ${
                        on ? "opacity-100" : "opacity-45"
                      }`}
                    >
                      {item.body}
                    </p>
                  </div>
                );
              })}
            </div>
            <div className="relative">
              <div
                className="absolute -inset-8 -z-10 rounded-[2.5rem] bg-accent/[0.07] blur-2xl"
                aria-hidden
              />
              {/* Stage: panels crossfade in place */}
              <div className="relative min-h-[22rem]">
                {PANELS.map((Panel, i) => {
                  const on = i === active;
                  return (
                    <motion.div
                      key={i}
                      className={`${i === 0 ? "relative" : "absolute inset-0"} flex items-center`}
                      initial={false}
                      animate={
                        reduce
                          ? { opacity: on ? 1 : 0 }
                          : { opacity: on ? 1 : 0, y: on ? 0 : 28, scale: on ? 1 : 0.97 }
                      }
                      transition={{ duration: 0.45, ease: [0.21, 0.6, 0.35, 1] }}
                      style={{ pointerEvents: on ? "auto" : "none" }}
                      aria-hidden={!on}
                    >
                      <div className="w-full">
                        <Panel />
                      </div>
                    </motion.div>
                  );
                })}
              </div>
              {/* Progress rail */}
              <div className="mt-8 flex items-center gap-2" aria-hidden>
                {ITEMS.map((item, i) => (
                  <div key={item.n} className="h-0.5 flex-1 overflow-hidden rounded-full bg-line">
                    <div
                      className={`h-full rounded-full bg-accent transition-all duration-500 ${
                        i < active ? "w-full" : i === active ? "w-full" : "w-0"
                      }`}
                    />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Stacked (mobile / tablet) */}
      <div className="mt-12 space-y-12 lg:hidden">
        {ITEMS.map((item, i) => {
          const Panel = PANELS[i];
          return (
            <Reveal key={item.n} delay={i * 0.05}>
              <p className="display mb-3 text-3xl text-accent">{item.n}</p>
              <h3 className="mb-1.5 font-semibold">{item.title}</h3>
              <p className="mb-5 text-sm leading-relaxed text-muted">{item.body}</p>
              <Panel />
            </Reveal>
          );
        })}
      </div>
    </section>
  );
}
