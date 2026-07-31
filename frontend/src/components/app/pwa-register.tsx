"use client";

import { useEffect } from "react";

// Registers the service worker once on load so the installed PWA is fully wired — push
// delivery and notification clicks work whether or not the user has toggled push yet.
// Renders nothing; safe on browsers without service workers.
export function PwaRegister() {
  useEffect(() => {
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
  }, []);
  return null;
}
