/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Secure headers (spec §30) - CSP is deliberately not set here since it
  // needs to be tuned against actual third-party script/font origins in
  // use; setting one prematurely would silently break functionality.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
