import type { NextConfig } from "next";

const INTERNAL_API_URL = process.env.INTERNAL_API_URL || 'http://backend:8000';
const IDENTITY_SESSION_V2_ENABLED = process.env.NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED === 'true';
const CATALOG_WRITES_ENABLED = process.env.NEXT_PUBLIC_CATALOG_WRITES_ENABLED === 'true';
const CRM_CABINET_ENABLED = process.env.NEXT_PUBLIC_CRM_CABINET_ENABLED === 'true';

if (CATALOG_WRITES_ENABLED && !IDENTITY_SESSION_V2_ENABLED) {
  throw new Error(
    'NEXT_PUBLIC_CATALOG_WRITES_ENABLED requires NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED',
  );
}

if (CRM_CABINET_ENABLED && !IDENTITY_SESSION_V2_ENABLED) {
  throw new Error(
    'NEXT_PUBLIC_CRM_CABINET_ENABLED requires NEXT_PUBLIC_IDENTITY_SESSION_V2_ENABLED',
  );
}

const nextConfig: NextConfig = {
  async rewrites() {
    return {
      beforeFiles: [
        {
          source: '/service.php',
          destination: '/api/cdek-service',
        },
      ],
      afterFiles: [
        {
          source: '/api/:path*',
          destination: `${INTERNAL_API_URL}/api/:path*`,
        },
        {
          source: '/uploads/:path*',
          destination: `${INTERNAL_API_URL}/uploads/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
