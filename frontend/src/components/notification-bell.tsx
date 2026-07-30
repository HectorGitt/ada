"use client";

import { Bell, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { api, type AppNotification } from "@/lib/api";

/** Overall in-app notification centre — a bell with an unread badge that opens a
 *  panel of recent notifications. Shared by the candidate and employer shells;
 *  email + WhatsApp are fanned out server-side, this is the durable view. */
export function NotificationBell() {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<AppNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [toasts, setToasts] = useState<AppNotification[]>([]);
  const wrap = useRef<HTMLDivElement>(null);
  // Ids we've already surfaced, so a new arrival toasts exactly once. The first
  // poll seeds this silently — we don't toast the backlog you already had.
  const seen = useRef<Set<string> | null>(null);

  const dismiss = useCallback((id: string) => {
    setToasts((cur) => cur.filter((t) => t.id !== id));
  }, []);

  // OS-level notification (works while the tab is open or backgrounded). Full
  // closed-tab Web Push (service worker + VAPID) is a separate, larger add.
  const fireOsNotification = useCallback(
    (n: AppNotification) => {
      if (typeof window === "undefined" || !("Notification" in window)) return;
      if (Notification.permission !== "granted") return;
      try {
        const os = new Notification(n.title, { body: n.body ?? undefined, tag: n.id });
        os.onclick = () => {
          window.focus();
          if (n.link) router.push(n.link);
          os.close();
        };
      } catch {
        /* some browsers throw if constructed outside a SW — ignore */
      }
    },
    [router],
  );

  // Ask once (browsers gate this; if denied, in-app toasts still work).
  useEffect(() => {
    if (typeof window !== "undefined" && "Notification" in window &&
        Notification.permission === "default") {
      void Notification.requestPermission();
    }
  }, []);

  const load = useCallback(async () => {
    try {
      const res = await api.notifications();
      setItems(res.items);
      setUnread(res.unread);
      if (seen.current === null) {
        seen.current = new Set(res.items.map((n) => n.id)); // seed, no backlog toasts
        return;
      }
      const fresh = res.items.filter((n) => !seen.current!.has(n.id) && !n.read);
      if (fresh.length) {
        fresh.forEach((n) => seen.current!.add(n.id));
        setToasts((cur) => [...fresh.reverse(), ...cur].slice(0, 4));
        fresh.forEach(fireOsNotification); // OS-level push (tab open/backgrounded)
      }
      // keep `seen` from growing without bound
      res.items.forEach((n) => seen.current!.add(n.id));
    } catch {
      /* offline / not signed in — leave as-is */
    }
  }, [fireOsNotification]);

  useEffect(() => {
    void load();
    const t = setInterval(load, 12_000); // snappy enough to feel live
    return () => clearInterval(t);
  }, [load]);

  // Auto-dismiss each toast after a few seconds.
  useEffect(() => {
    if (toasts.length === 0) return;
    const timers = toasts.map((t) => setTimeout(() => dismiss(t.id), 6500));
    return () => timers.forEach(clearTimeout);
  }, [toasts, dismiss]);

  // Close on outside click.
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (wrap.current && !wrap.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    return () => document.removeEventListener("mousedown", onDown);
  }, [open]);

  const toggle = async () => {
    const next = !open;
    setOpen(next);
    if (next && unread > 0) {
      setUnread(0);
      setItems((cur) => cur.map((n) => ({ ...n, read: true })));
      await api.markNotificationsRead().catch(() => {});
    }
  };

  const go = (n: AppNotification) => {
    setOpen(false);
    if (n.link) router.push(n.link);
  };

  return (
    <>
    <div ref={wrap} className="relative">
      <button
        onClick={toggle}
        aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`}
        className="relative flex size-9 items-center justify-center rounded-full text-muted transition-colors hover:bg-line/40 hover:text-ink"
      >
        <Bell className="size-[18px]" />
        {unread > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold leading-4 text-accent-ink">
            {unread > 9 ? "9+" : unread}
          </span>
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -6, scale: 0.98 }}
            transition={{ duration: 0.16, ease: [0.16, 1, 0.3, 1] }}
            className="absolute right-0 z-50 mt-2 w-80 origin-top-right overflow-hidden rounded-2xl border border-line bg-surface shadow-lift"
          >
            <div className="border-b border-line px-4 py-3">
              <p className="text-sm font-medium">Notifications</p>
            </div>
            <div className="quiet-scroll max-h-96 overflow-y-auto">
              {items.length === 0 ? (
                <p className="px-4 py-10 text-center text-sm text-muted">
                  Nothing yet — we&apos;ll let you know.
                </p>
              ) : (
                items.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => go(n)}
                    className={`block w-full border-b border-line/60 px-4 py-3 text-left transition-colors last:border-0 hover:bg-line/30 ${
                      n.read ? "" : "bg-accent-soft/40"
                    }`}
                  >
                    <p className="text-sm font-medium leading-snug">{n.title}</p>
                    {n.body && (
                      <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-muted">
                        {n.body}
                      </p>
                    )}
                    <p className="mt-1 text-[10px] uppercase tracking-wide text-muted/70">
                      {new Date(n.created_at).toLocaleDateString(undefined, {
                        day: "numeric",
                        month: "short",
                      })}
                    </p>
                  </button>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>

      {/* Live toasts — a new notification pops in from anywhere in the app,
          whatever page you're on, then auto-dismisses. */}
      <div className="pointer-events-none fixed right-4 top-16 z-[100] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2 lg:top-4">
        <AnimatePresence initial={false}>
          {toasts.map((t) => (
            <motion.button
              key={t.id}
              layout
              initial={{ opacity: 0, x: 24, scale: 0.97 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, x: 24, scale: 0.97 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              onClick={() => {
                dismiss(t.id);
                if (t.link) router.push(t.link);
              }}
              className="pointer-events-auto w-full rounded-2xl border border-line bg-surface p-4 text-left shadow-lift"
            >
              <div className="flex items-start gap-2.5">
                <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
                  <Bell className="size-3.5" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block text-sm font-medium leading-snug">{t.title}</span>
                  {t.body && (
                    <span className="mt-0.5 line-clamp-2 block text-xs leading-relaxed text-muted">
                      {t.body}
                    </span>
                  )}
                </span>
                <span
                  role="button"
                  aria-label="Dismiss"
                  onClick={(e) => {
                    e.stopPropagation();
                    dismiss(t.id);
                  }}
                  className="shrink-0 rounded-full p-1 text-muted/60 transition-colors hover:text-ink"
                >
                  <X className="size-3.5" />
                </span>
              </div>
            </motion.button>
          ))}
        </AnimatePresence>
      </div>
    </>
  );
}
