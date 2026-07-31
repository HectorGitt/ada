"use client";

import { LogOut, Menu, X } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { Logo, ThemeToggle } from "@/components/ui";
import { api } from "@/lib/api";

type NavItem = {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  exact?: boolean;
};
type NavGroup = { label: string; items: NavItem[] };

const isActive = (pathname: string, item: { href: string; exact?: boolean }) =>
  item.exact ? pathname === item.href : pathname.startsWith(item.href);

/** The full dashboard navigation on mobile. The bottom tab bar only fits a handful of
 *  destinations, so this hamburger opens a portaled overlay with every section — otherwise
 *  Documents, Applications, Intros, Verify, Voice, and Billing are unreachable on a phone. */
export function AppNavSheet({
  groups,
  pathname,
  email,
}: {
  groups: NavGroup[];
  pathname: string;
  email: string;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [entered, setEntered] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) {
      setEntered(false);
      return;
    }
    const id = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(id);
  }, [open]);

  // Scroll-lock, focus trap + return-to-trigger, Esc — only while open.
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

  const signOut = async () => {
    await api.logout().catch(() => {});
    router.replace("/login");
  };

  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls="app-nav-sheet"
        aria-label="Menu"
        className="flex size-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-line/40 hover:text-ink lg:hidden"
      >
        <Menu className="size-5" />
      </button>

      {open &&
        typeof document !== "undefined" &&
        createPortal(
          <div
            ref={dialogRef}
            id="app-nav-sheet"
            role="dialog"
            aria-modal="true"
            aria-label="Navigation"
            style={{ backgroundColor: "var(--bg)" }}
            className={`fixed inset-0 z-[100] flex flex-col transition-opacity duration-200 motion-reduce:transition-none lg:hidden ${
              entered ? "opacity-100" : "opacity-0"
            }`}
          >
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <Link href="/" onClick={() => setOpen(false)}>
                <Logo />
              </Link>
              <button
                type="button"
                onClick={() => setOpen(false)}
                aria-label="Close menu"
                className="flex size-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-line/40 hover:text-ink"
              >
                <X className="size-5" />
              </button>
            </div>

            <nav className="flex-1 space-y-6 overflow-y-auto px-4 py-6">
              {groups.map((group) => (
                <div key={group.label}>
                  <p className="eyebrow mb-2 px-2 !text-[10px]">{group.label}</p>
                  <div className="space-y-0.5">
                    {group.items.map((item) => {
                      const { href, label, icon: Icon } = item;
                      const active = isActive(pathname, item);
                      return (
                        <Link
                          key={href}
                          href={href}
                          onClick={() => setOpen(false)}
                          className={`flex items-center gap-3 rounded-xl px-3 py-3 text-[15px] transition-colors ${
                            active
                              ? "bg-accent-soft font-medium text-accent"
                              : "text-ink hover:bg-line/40"
                          }`}
                        >
                          <Icon className="size-5" />
                          {label}
                        </Link>
                      );
                    })}
                  </div>
                </div>
              ))}
            </nav>

            <div className="flex items-center justify-between gap-3 border-t border-line px-5 py-4">
              <Link
                href="/app/profile"
                onClick={() => setOpen(false)}
                className="flex min-w-0 items-center gap-2.5"
                title={email}
              >
                <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold uppercase text-accent">
                  {email[0]}
                </span>
                <span className="block truncate text-xs font-medium">{email}</span>
              </Link>
              <div className="flex items-center gap-1">
                <ThemeToggle />
                <button
                  type="button"
                  onClick={signOut}
                  aria-label="Sign out"
                  className="flex size-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-line/40 hover:text-ink"
                >
                  <LogOut className="size-4" />
                </button>
              </div>
            </div>
          </div>,
          document.body,
        )}
    </>
  );
}
