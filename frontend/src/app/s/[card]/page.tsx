import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { decodeCard, verdict } from "@/lib/share";
import { ShareView } from "./share-view";

// A shared CV-score card. Server component so the preview metadata (and the sibling
// opengraph-image) render from the URL payload — the growth loop back into /assess.
export async function generateMetadata(
  { params }: { params: Promise<{ card: string }> },
): Promise<Metadata> {
  const { card } = await params;
  const data = decodeCard(card);
  if (!data) return { title: "Ada" };
  const title = `${data.score}/100 — ${verdict(data.score)} · CV readiness by Ada`;
  const description = "See how ready your CV is — free, no signup. Scored by Ada.";
  return {
    title,
    description,
    openGraph: { title, description },
    twitter: { card: "summary_large_image", title, description },
  };
}

export default async function SharePage({ params }: { params: Promise<{ card: string }> }) {
  const { card } = await params;
  const data = decodeCard(card);
  if (!data) notFound();
  return <ShareView score={data.score} role={data.role} />;
}
