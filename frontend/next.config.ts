import type { NextConfig } from "next";

const origin = process.env.GTA_REVIEW_ORIGIN ?? "http://127.0.0.1:8766";

const config: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/sessions/:path*", destination: origin + "/api/sessions/:path*" },
      { source: "/media/:path*", destination: origin + "/media/:path*" },
      { source: "/api/v1/:path*", destination: origin + "/api/v1/:path*" },
      { source: "/api/jobs", destination: origin + "/api/jobs" },
      { source: "/api/jobs/:path*", destination: origin + "/api/jobs/:path*" },
    ];
  },
};

export default config;
