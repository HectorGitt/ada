"use client";

import { Bell } from "lucide-react";
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
  const wrap = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.notifications();
      setItems(res.items);
      setUnread(res.unread);
    } catch {
      /* offline / not signed in — leave as-is */
    }
  }, []);

  useEffect(() => {
    void load();
    const t = setInterval(load, 30_000); // gentle poll
    return () => clearInterval(t);
  }, [load]);

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
  );
}
