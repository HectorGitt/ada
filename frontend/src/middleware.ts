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
  // API, assets, and already-/hire paths pass through untouched.
  if (
    pathname.startsWith("/hire") ||
    pathname.startsWith("/api") ||
    pathname.startsWith("/_next") ||
    pathname.includes(".")
  ) {
    return NextResponse.next();
  }
  const url = request.nextUrl.clone();
  url.pathname = pathname === "/" ? "/hire" : `/hire${pathname}`;
  return NextResponse.rewrite(url);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
