const backendUrl = process.env.NEUROLENS_BACKEND_URL || "http://127.0.0.1:8000";
const backend = new URL(backendUrl);
if (
  backend.protocol !== "http:" ||
  !["127.0.0.1", "localhost", "[::1]", "backend"].includes(backend.hostname) ||
  backend.username || backend.password || backend.search || backend.hash ||
  backend.pathname !== "/"
) {
  throw new Error("NEUROLENS_BACKEND_URL must be a local HTTP backend origin");
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  outputFileTracingRoot: __dirname,
  poweredByHeader: false,
  allowedDevOrigins: ["localhost", "127.0.0.1"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backend.origin}/api/:path*`,
      },
      // Also proxy /static so NiiVue can fetch brain mesh GIFTIs
      {
        source: "/static/:path*",
        destination: `${backend.origin}/static/:path*`,
      },
    ];
  },
  // NiiVue uses WebAssembly internally — allow WASM loading
  webpack(config) {
    config.experiments = { ...config.experiments, asyncWebAssembly: true };
    return config;
  },
};

module.exports = nextConfig;
