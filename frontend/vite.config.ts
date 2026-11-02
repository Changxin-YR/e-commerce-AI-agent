import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { loadEnv } from 'vite'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

const frontendRoot = fileURLToPath(new URL('.', import.meta.url))
const projectRoot = path.resolve(frontendRoot, '..')

function port(value: string | undefined, fallback: number): number {
  if (!value) return fallback
  const parsed = Number(value)
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    throw new Error('APP_PORT and FRONTEND_PORT must be valid TCP ports')
  }
  return parsed
}

export default defineConfig(({ mode }) => {
  // Only explicit port values are used server-side. No env object is exposed to the client.
  const env = loadEnv(mode, projectRoot, '')
  const backendPort = port(process.env.APP_PORT ?? env.APP_PORT, 8000)
  const frontendPort = port(process.env.FRONTEND_PORT ?? env.FRONTEND_PORT, 5173)
  const cacheRoot = process.env.D0_CACHE_DIR ?? env.D0_CACHE_DIR
  const target = `http://127.0.0.1:${backendPort}`
  const proxy = { '/healthz': { target }, '/api': { target } }
  return {
    plugins: [vue()],
    // Keep .env loading rooted in the project, without changing VITE_ exposure rules.
    envDir: projectRoot,
    cacheDir: cacheRoot ? path.join(cacheRoot, 'vite') : 'node_modules/.vite',
    server: { host: '127.0.0.1', port: frontendPort, strictPort: true, proxy },
    preview: { host: '127.0.0.1', port: frontendPort, strictPort: true, proxy },
    build: {
      outDir: cacheRoot ? path.join(cacheRoot, 'frontend-dist') : 'dist',
      // Never empty an external directory; output names are content-hashed.
      emptyOutDir: !cacheRoot,
    },
    test: {
      environment: 'jsdom',
      include: ['tests/**/*.test.ts'],
      clearMocks: true,
      restoreMocks: true,
    },
  }
})
