// Run with COMMLAB_API_ORIGIN=https://your-service.onrender.com before deployment.
import { writeFileSync } from 'node:fs';
const origin = new URL(process.env.COMMLAB_API_ORIGIN || '');
if (origin.protocol !== 'https:' || origin.username || origin.password || origin.pathname !== '/' || origin.search || origin.hash) {
  throw new Error('COMMLAB_API_ORIGIN must be a plain HTTPS origin without credentials');
}
writeFileSync(new URL('../vercel.json', import.meta.url), JSON.stringify({
  buildCommand: 'cd frontend && npm ci && npm run build',
  outputDirectory: 'frontend/dist', framework: null,
  rewrites: [
    { source: '/api/:path*', destination: `${origin.origin}/api/:path*` },
    { source: '/health', destination: `${origin.origin}/health` },
    { source: '/(.*)', destination: '/index.html' }
  ]
}, null, 2) + '\n');
