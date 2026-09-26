import type { NextConfig } from "next";

// Render `fromService.hostAndPort` yields `host:port` (no scheme) — normalize.
const _raw = process.env.API_INTERNAL_URL ?? "http://localhost:8000";
const API_URL = /^https?:\/\//.test(_raw) ? _raw : `http://${_raw}`;

const nextConfig: NextConfig = {
  async rewrites() {
    // Browser calls /api/* — Caddy proxies this path in production;
    // the rewrite only matters for `next dev`.
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
