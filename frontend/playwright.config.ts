import { defineConfig } from '@playwright/test'
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadEnv } from 'vite'

const projectRoot = fileURLToPath(new URL('..', import.meta.url))
const env = loadEnv('test', projectRoot, '')
const cacheRoot = process.env.D0_CACHE_DIR ?? env.D0_CACHE_DIR
if (!cacheRoot || !path.isAbsolute(cacheRoot)) {
  throw new Error('Playwright requires an absolute D0_CACHE_DIR in the environment or root .env')
}

// Workers inherit this directory; repeated invocations keep separate evidence.
const runDir = process.env.D0_E2E_RUN_DIR
  ?? path.join(cacheRoot, 'playwright', `${new Date().toISOString().replace(/[:.]/g, '-')}-${process.pid}`)
process.env.D0_E2E_RUN_DIR = runDir
mkdirSync(runDir, { recursive: true })

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  outputDir: path.join(runDir, 'artifacts'),
  reporter: [['list'], ['json', { outputFile: path.join(runDir, 'results.json') }]],
  use: {
    channel: 'msedge',
    headless: true,
    viewport: { width: 1280, height: 900 },
    trace: 'on',
    screenshot: 'only-on-failure',
  },
})
