import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

/** Host-based routing: uche.recrulus.com is the employer front door.
 *  Same app, same deploy — requests on the uche host are rewritten into the
 *  /hire tree so the subdomain feels like its own product. */
const UCHE_HOSTS = new Set(["uche.recrulus.com", "uche.localhost:3000"]);

export function middleware(request: NextRequest) {
  const host = request.headers.get("host")?.toLowerCase() ?? "";
  if (!UCHE_HOSTS.has(host)) return NextResponse.next();

  const { pathname } = request.nextUrl;
  // API, assets, shared auth pages, and already-/hire paths pass through untouched
  // (login/auth are one shared flow for both products — only the branding adapts).
  if (
    pathname.startsWith("/hire") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next") ||
    pathname.startsWith("/login") ||
    pathname.startsWith("/auth") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }
  const url = request.nextUrl.clone();
  // The subdomain root is Uche's marketing landing; the console lives at /hire.
  url.pathname = pathname === "/" ? "/hire/home" : `/hire${pathname}`;
  return NextResponse.rewrite(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
