import type { NextConfig } from 'next'

const config: NextConfig = {
  output: 'export',
  basePath: '/app',
  assetPrefix: '/app',
  trailingSlash: true,
}

export default config
