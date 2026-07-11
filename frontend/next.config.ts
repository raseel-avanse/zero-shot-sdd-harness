import type { NextConfig } from 'next'

const config: NextConfig = {
  output: 'export',
  basePath: '/app',
  trailingSlash: true,
  // Serialise the build workers. Next 15.3's parallel build-trace worker races
  // the static-export step on some filesystems (WSL), intermittently failing
  // with a spurious `.next/server/pages-manifest.json` ENOENT. One worker makes
  // `pnpm build` deterministic; the export itself stays fast for a one-page app.
  experimental: {
    cpus: 1,
    workerThreads: false,
  },
}

export default config
