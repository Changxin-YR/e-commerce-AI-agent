import { expect, test } from '@playwright/test'
import { spawn } from 'node:child_process'
import type { ChildProcess } from 'node:child_process'
import { closeSync, mkdirSync, openSync, writeFileSync } from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Engineering-only fixture: an empty, migrated SQLite database; no trading data.
const projectRoot = fileURLToPath(new URL('../..', import.meta.url))
const runDir = process.env.D0_E2E_RUN_DIR
if (!runDir) throw new Error('Run this suite through its Playwright configuration')
mkdirSync(runDir, { recursive: true })
const evidenceDir: string = runDir
const python = path.join(projectRoot, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')

type CommandRecord = {
  label: string
  executable: string
  args: string[]
  cwd: string
  started_at: string
  pid?: number
  ended_at?: string
  exit_code?: number | null
  signal?: NodeJS.Signals | null
  intentional_stop?: boolean
  error?: string
  log: string
}
type ManagedProcess = { child: ChildProcess; record: CommandRecord; done: Promise<number | null> }
const records: CommandRecord[] = []
let backend: ManagedProcess | undefined
let frontend: ManagedProcess | undefined
let backendPort: number
let frontendPort: number
let backendStarts = 0
let localEnv: NodeJS.ProcessEnv
let baseURL: string

function saveCommands() {
  writeFileSync(path.join(evidenceDir, 'commands.json'), JSON.stringify({
    source_kind: 'development_test_evidence',
    database_kind: 'empty_engineering_fixture',
    backend_port: backendPort,
    frontend_port: frontendPort,
    commands: records,
  }, null, 2), 'utf8')
}

function launch(label: string, executable: string, args: string[], cwd: string, env = localEnv): ManagedProcess {
  const log = path.join(evidenceDir, `${label}.log`)
  const fd = openSync(log, 'a')
  const record: CommandRecord = { label, executable, args, cwd, started_at: new Date().toISOString(), log }
  let child: ChildProcess
  try {
    child = spawn(executable, args, { cwd, env, windowsHide: true, shell: false, stdio: ['ignore', fd, fd] })
  } finally {
    closeSync(fd)
  }
  record.pid = child.pid
  records.push(record)
  const done = new Promise<number | null>((resolve, reject) => {
    child.once('error', (error) => {
      record.error = error.message
      record.ended_at = new Date().toISOString()
      saveCommands()
      reject(error)
    })
    child.once('exit', (code, signal) => {
      record.exit_code = code
      record.signal = signal
      record.ended_at = new Date().toISOString()
      saveCommands()
      resolve(code)
    })
  })
  // A background startup failure is checked by waitReady, without an unhandled rejection.
  void done.catch(() => undefined)
  saveCommands()
  return { child, record, done }
}

async function chooseFreePort(): Promise<number> {
  return await new Promise<number>((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      if (!address || typeof address === 'string') return reject(new Error('Could not allocate a local test port'))
      server.close((error) => error ? reject(error) : resolve(address.port))
    })
  })
}

async function waitReady(process: ManagedProcess, url: string, health = false) {
  const deadline = Date.now() + 20_000
  while (Date.now() < deadline) {
    if (process.record.ended_at) throw new Error(`${process.record.label} exited before readiness; see ${process.record.log}`)
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1000) })
      if (response.ok && (!health || (await response.json() as { service?: string }).service === 'ecommerce-agent')) {
        // Give strict-port binding errors time to surface; never reuse an existing service.
        await new Promise((resolve) => setTimeout(resolve, 150))
        if (process.record.ended_at) throw new Error(`${process.record.label} unexpectedly exited`)
        return
      }
    } catch {
      // Transient connection failures are expected while our own server starts.
    }
    await new Promise((resolve) => setTimeout(resolve, 150))
  }
  throw new Error(`${process.record.label} readiness timed out; see ${process.record.log}`)
}

async function stop(process: ManagedProcess | undefined) {
  if (!process || process.record.ended_at || !process.child.pid) return
  process.record.intentional_stop = true
  saveCommands()
  if (globalThis.process.platform === 'win32') {
    const taskkill = path.join(globalThis.process.env.SystemRoot ?? 'C:\\Windows', 'System32/taskkill.exe')
    const kill = launch(`stop-${process.record.label}`, taskkill, ['/PID', String(process.child.pid), '/T', '/F'], projectRoot)
    const result = await kill.done
    // The target may have exited between the ownership check and taskkill.
    if (result !== 0 && !process.record.ended_at) throw new Error(`Could not stop owned ${process.record.label} process`)
  } else {
    process.child.kill('SIGTERM')
  }
  await Promise.race([
    process.done,
    new Promise((_, reject) => setTimeout(() => reject(new Error(`Timed out stopping ${process.record.label}`)), 8000)),
  ])
}

async function startBackend() {
  backendStarts += 1
  backend = launch(`backend-${backendStarts}`, python, [
    '-X', 'utf8', 'scripts/manage.py', 'backend',
  ], projectRoot)
  await waitReady(backend, `http://127.0.0.1:${backendPort}/healthz`, true)
}

test.describe.serial('D0 real local service', () => {
  test.beforeAll(async () => {
    test.setTimeout(75_000)
    backendPort = await chooseFreePort()
    do { frontendPort = await chooseFreePort() } while (frontendPort === backendPort)
    baseURL = `http://127.0.0.1:${frontendPort}`
    localEnv = {
      ...process.env,
      APP_ENV: 'test',
      APP_HOST: '127.0.0.1',
      APP_PORT: String(backendPort),
      FRONTEND_PORT: String(frontendPort),
      DATABASE_URL: `sqlite:///${path.join(evidenceDir, 'engineering-fixture.sqlite3').replace(/\\/g, '/')}`,
      D0_CACHE_DIR: evidenceDir,
      PYTHONDONTWRITEBYTECODE: '1',
      PYTHONUTF8: '1',
      ALLOW_PAID_MODEL_CALLS: 'false',
    }
    const migration = launch('alembic-upgrade', python, ['-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'], projectRoot)
    expect(await migration.done, 'isolated database migration').toBe(0)
    await startBackend()
    frontend = launch('frontend', python, ['-X', 'utf8', 'scripts/manage.py', 'frontend'], projectRoot)
    await waitReady(frontend, baseURL)
  })

  test.afterAll(async () => {
    const cleanup = await Promise.allSettled([stop(frontend), stop(backend)])
    saveCommands()
    for (const result of cleanup) if (result.status === 'rejected') throw result.reason
  })

  test('page receives real health JSON and remains connected after reload', async ({ page }) => {
    const browserErrors: string[] = []
    page.on('pageerror', (error) => browserErrors.push(error.message))
    const [firstResponse] = await Promise.all([
      page.waitForResponse((response) => response.url() === `${baseURL}/healthz`),
      page.goto(baseURL),
    ])
    expect(firstResponse.status()).toBe(200)
    expect(await firstResponse.json()).toMatchObject({
      status: 'ok', service: 'ecommerce-agent', stage: 'D0',
      database: { status: 'ok', engine: 'sqlite', schema_revision: '0001_bootstrap' },
    })
    await expect(page.getByTestId('health-status')).toHaveText('本地服务已连接')
    await page.screenshot({ path: path.join(evidenceDir, 'desktop-connected.png'), fullPage: true })
    const [reloadedResponse] = await Promise.all([
      page.waitForResponse((response) => response.url() === `${baseURL}/healthz`),
      page.reload(),
    ])
    expect(reloadedResponse.status()).toBe(200)
    await expect(page.getByTestId('health-status')).toHaveText('本地服务已连接')
    await page.setViewportSize({ width: 390, height: 844 })
    await expect(page.getByRole('button', { name: '重新检查' })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: path.join(evidenceDir, 'mobile-connected.png'), fullPage: true })
    expect(browserErrors).toEqual([])
  })

  test('stopping and restarting the real backend shows failure and recovery', async ({ page }) => {
    await page.goto(baseURL)
    await expect(page.getByTestId('health-status')).toHaveText('本地服务已连接')
    await stop(backend)
    await page.getByRole('button', { name: '重新检查' }).click()
    await expect(page.getByTestId('health-status')).toHaveText('本地服务暂不可用')
    await expect(page.getByRole('alert')).toBeVisible()
    await expect(page.getByText('0001_bootstrap', { exact: true })).toHaveCount(0)
    await page.screenshot({ path: path.join(evidenceDir, 'backend-stopped.png'), fullPage: true })
    await startBackend()
    await page.getByRole('button', { name: '重新检查' }).click()
    await expect(page.getByTestId('health-status')).toHaveText('本地服务已连接')
    await expect(page.getByRole('alert')).toHaveCount(0)
    await expect(page.getByText('0001_bootstrap', { exact: true })).toBeVisible()
    await page.screenshot({ path: path.join(evidenceDir, 'backend-recovered.png'), fullPage: true })
  })
})
