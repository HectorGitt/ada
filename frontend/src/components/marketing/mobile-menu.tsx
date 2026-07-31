"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Button, Logo, ThemeToggle } from "@/components/ui";

// The mobile nav — a full-screen editorial overlay opened by a quiet "Menu" word (a serif
// brand deserves a word, not a hamburger glyph). Reuses the header pill's blurred material;
// links render large in the display serif and stagger in. Fully accessible: focus trap +
// return, Esc, scroll-lock, and motion gated by prefers-reduced-motion.
const LINKS: { href: string; label: string }[] = [
  { href: "#how", label: "How it works" },
  { href: "#pricing", label: "Pricing" },
  { href: "#faqs", label: "FAQs" },
  { href: "/assess", label: "Free CV check" },
  { href: "/hire/home", label: "For employers" },
];

export function MobileMenu() {
  const [open, setOpen] = useState(false);
  const [entered, setEntered] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  // Fade/scale in after mount; instant close.
  useEffect(() => {
    if (!open) {
      setEntered(false);
      return;
    }
    const id = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(id);
  }, [open]);

  // Scroll-lock, focus trap + return, Esc — only while open.
  useEffect(() => {
    if (!open) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusables = () =>
      Array.from(
        dialogRef.current?.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])',
        ) ?? [],
      );
    focusables()[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        return;
      }
      if (e.key !== "Tab") return;
      const items = focusables();
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prevOverflow;
      triggerRef.current?.focus();
    };
  }, [open]);

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls="mobile-menu"
        className="rounded-full px-3 py-2.5 text-sm text-muted transition-colors hover:text-ink sm:hidden"
      >
        Menu
      </button>

      {open &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            ref={dialogRef}
            id="mobile-menu"
            role="dialog"
            aria-modal="true"
            aria-label="Menu"
            // Portaled to <body> so it escapes any transformed/stacking ancestor on the
            // landing (framer-motion Reveal/ScrollProgress). Opaque bg set inline as a
            // belt-and-braces guarantee nothing behind can show through.
            style={{ backgroundColor: "var(--bg)" }}
            className={`fixed inset-0 z-[100] flex flex-col transition-opacity duration-200 motion-reduce:transition-none sm:hidden ${
              entered ? "opacity-100" : "opacity-0"
            }`}
          >
          <div className="flex items-center justify-between px-6 pt-6">
            <Logo />
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Close menu"
              className="rounded-full px-3 py-2.5 text-sm text-muted transition-colors hover:text-ink"
            >
              Close
            </button>
          </div>

          <nav className="flex flex-1 flex-col justify-center gap-1 px-6">
            {LINKS.map((l, i) => {
              const inner = (
                <span
                  className={`display block py-2 text-4xl text-ink transition-all duration-300 hover:text-accent motion-reduce:transition-none ${
                    entered ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"
                  }`}
                  style={{ transitionDelay: `${80 + i * 45}ms` }}
                >
                  {l.label}
                </span>
              );
              return l.href.startsWith("#") ? (
                <a key={l.href} href={l.href} onClick={() => setOpen(false)}>
                  {inner}
                </a>
              ) : (
                <Link key={l.href} href={l.href} onClick={() => setOpen(false)}>
                  {inner}
                </Link>
              );
            })}
          </nav>

          <div className="flex items-center justify-between gap-4 border-t border-line/60 px-6 py-6">
            <div className="flex items-center gap-4">
              <Link
                href="/login"
                onClick={() => setOpen(false)}
                className="text-sm text-muted transition-colors hover:text-ink"
              >
                Sign in
              </Link>
              <ThemeToggle />
            </div>
            <Link href="/app" onClick={() => setOpen(false)}>
              <Button className="!py-2.5">Open Ada</Button>
            </Link>
          </div>
        </div>,
          document.body,
        )}
    </>
  );
}
