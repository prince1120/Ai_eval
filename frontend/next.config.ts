import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ["localhost:3001"],
  devIndicators: false,
  // Emits .next/standalone with only the traced files needed to run, so the
  // Docker image does not have to carry the full node_modules tree.
  output: "standalone",
};

export default nextConfig;
