"use client";

import { X } from "lucide-react";
import { useEffect } from "react";
import { createPortal } from "react-dom";

import { Logo } from "@/components/ui";

// A full-screen "exam room" for a proctored assessment — portaled over the whole app so
// the sidebar/tab chrome is gone and there's nothing to wander to. Distraction-free is the
// point of a proctored test.
export function FocusStage({
  title,
  onExit,
  children,
}: {
  title: string;
  onExit?: () => void;
  children: React.ReactNode;
}) {
  useEffect(() => {
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden"; // lock the page behind the stage
    return () => {
      document.body.style.overflow = prev;
    };
  }, []);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div className="fixed inset-0 z-[80] flex flex-col overflow-y-auto bg-bg">
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-bg/90 px-5 py-3 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <Logo />
          <span className="hidden text-xs font-medium text-muted sm:inline">{title}</span>
        </div>
        {onExit && (
          <button
            onClick={() => {
              if (confirm("Leave the assessment? Your timer keeps running — you can resume it.")) {
                onExit();
              }
            }}
            className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-muted transition-colors hover:bg-line/40 hover:text-ink"
          >
            <X className="size-4" /> Exit
          </button>
        )}
      </header>
      <div className="mx-auto w-full max-w-3xl flex-1 px-5 py-6">{children}</div>
    </div>,
    document.body,
  );
}
