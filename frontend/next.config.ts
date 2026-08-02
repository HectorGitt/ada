import type { NextConfig } from "next";

// All /api/* traffic is proxied to the FastAPI backend so the session cookie is
// first-party and CORS never applies. The voice WebSocket connects directly
// (rewrites do not carry the upgrade handshake reliably) via NEXT_PUBLIC_WS_URL.
const BACKEND_URL = process.env.BACKEND_URL ?? "http://localhost:8080";

// Security response headers. CSP ships Report-Only first (per the audit) so we can tighten
// it from real violation reports without breaking the inline theme bootstrap, Paystack
// inline checkout, the voice WebSocket, audio, or data:-URI images. camera/microphone are
// explicitly allowed — the proctored voice+camera assessment needs them.
const CSP_REPORT_ONLY = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' https://js.paystack.co",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob: https:",
  "font-src 'self' data:",
  "connect-src 'self' https: wss:",
  "frame-src https://checkout.paystack.com",
  "media-src 'self' blob: data:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'self'",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Strict-Transport-Security", value: "max-age=63072000; includeSubDomains; preload" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "SAMEORIGIN" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(self), microphone=(self), geolocation=(), payment=(self)" },
  { key: "Content-Security-Policy-Report-Only", value: CSP_REPORT_ONLY },
];

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` }];
  },
  async headers() {
    return [{ source: "/:path*", headers: SECURITY_HEADERS }];
  },
};

export default nextConfig;
