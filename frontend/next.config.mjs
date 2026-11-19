/** @type {import('next').NextConfig} */

// Si API_PROXY_TARGET está definida (p. ej. https://api-interna.railway.internal), el navegador habla solo con
// el dominio del frontend y Next reenvía /api/* al backend. Así las cookies httpOnly (SameSite=Strict) funcionan
// aunque front y API estén en dominios distintos, y se usa NEXT_PUBLIC_API_URL=/api/v1.
const target = process.env.API_PROXY_TARGET;

const nextConfig = {
  async rewrites() {
    if (!target) return [];
    return [{ source: '/api/:path*', destination: `${target.replace(/\/$/, '')}/api/:path*` }];
  },
};

export default nextConfig;
