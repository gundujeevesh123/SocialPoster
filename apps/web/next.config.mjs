/** @type {import('next').NextConfig} */
const API = process.env.API_ORIGIN || "http://localhost:8000";

const nextConfig = {
  async rewrites() {
    // Proxy /api/* to FastAPI so the browser stays same-origin (cookies just work).
    return [{ source: "/api/:path*", destination: `${API}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
