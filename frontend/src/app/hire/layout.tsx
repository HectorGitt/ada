import type { Metadata } from "next";

/** Server-side metadata for the employer side (crawlers never run JS, so the
 *  uche.recrulus.com previews must be set here, not client-side). Applies to
 *  /hire and /hire/home — exactly the tree the uche host serves. */
export const metadata: Metadata = {
  metadataBase: new URL("https://uche.recrulus.com"),
  title: { absolute: "Uche — hiring that runs itself" },
  description:
    "Post a role once. Uche screens every applicant, ranks the shortlist worth your time, and preps your interviews. The autonomous employer agent from Recrulus.",
  openGraph: {
    title: "Uche — hiring that runs itself",
    description:
      "Post a role once. Uche screens every applicant, ranks the shortlist, and preps your interviews.",
    url: "https://uche.recrulus.com",
    siteName: "Uche",
  },
};

export default function HireLayout({ children }: { children: React.ReactNode }) {
  return children;
}
