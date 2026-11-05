import { expect, test } from '@playwright/test'
import { spawn } from 'node:child_process'
import type { ChildProcess } from 'node:child_process'
import { closeSync, mkdirSync, openSync, writeFileSync, readFileSync } from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Real official data uploaded through the Vue page into a new isolated database.
const projectRoot = fileURLToPath(new URL('../..', import.meta.url))
const runDir = process.env.D0_E2E_RUN_DIR
if (!runDir) throw new Error('Run this suite through its Playwright configuration')
mkdirSync(runDir, { recursive: true })
const evidenceDir = path.join(runDir, 'business')
mkdirSync(evidenceDir, { recursive: true })
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
    database_kind: 'real_UCI_uploaded_in_browser',
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

test.describe.serial('D4 real business workflow', () => {
  let queryId = ''
  test.beforeAll(async () => {
    test.setTimeout(75_000)
    backendPort = await chooseFreePort()
    do { frontendPort = await chooseFreePort() } while (frontendPort === backendPort)
    baseURL = `http://127.0.0.1:${frontendPort}`
    localEnv = {
      ...process.env, APP_ENV: 'test', APP_HOST: '127.0.0.1', APP_PORT: String(backendPort), FRONTEND_PORT: String(frontendPort),
      DATABASE_URL: `sqlite:///${path.join(evidenceDir, 'real-ui.sqlite3').replace(/\\/g, '/')}`,
      IMPORT_CACHE_DIR: path.join(evidenceDir, 'imports'), D0_CACHE_DIR: evidenceDir,
      PYTHONDONTWRITEBYTECODE: '1', PYTHONUTF8: '1', ALLOW_PAID_MODEL_CALLS: 'false',
    }
    const migration = launch('alembic-upgrade', python, ['-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'], projectRoot)
    expect(await migration.done).toBe(0)
    await startBackend()
    frontend = launch('frontend', python, ['-X', 'utf8', 'scripts/manage.py', 'frontend'], projectRoot)
    await waitReady(frontend, baseURL)
  })
  test.afterAll(async () => {
    const cleanup = await Promise.allSettled([stop(frontend), stop(backend)])
    saveCommands()
    for (const result of cleanup) if (result.status === 'rejected') throw result.reason
  })

  test('official ZIP uploads in UI, progresses, survives refresh and deduplicates XLSX', async ({ page }) => {
    // A full 541909-row import can be slower on a busy developer workstation.
    // Keep the existing default, with an explicit bounded override for that environment.
    const importWaitMs = Number(process.env.E2E_IMPORT_TIMEOUT_MS ?? 240_000)
    if (!Number.isInteger(importWaitMs) || importWaitMs < 240_000 || importWaitMs > 900_000) throw new Error('E2E_IMPORT_TIMEOUT_MS must be between 240000 and 900000')
    test.setTimeout(importWaitMs + 60_000)
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`${baseURL}/?view=datasets`)
    await expect(page.getByLabel('源数据文件')).toBeVisible()
    await page.getByLabel('源数据文件').setInputFiles(path.join(projectRoot, 'data/raw/online_retail_uci352.zip'))
    const [accepted] = await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/datasets/imports') && response.request().method() === 'POST'),
      page.getByRole('button', { name: '上传并导入' }).click(),
    ])
    expect(accepted.status()).toBe(202)
    const initial = await accepted.json()
    expect(['QUEUED', 'IMPORTING']).toContain(initial.status)
    writeFileSync(path.join(evidenceDir, 'initial-import.json'), JSON.stringify(initial, null, 2))
    await expect(page.getByTestId('batch-status')).toHaveText(/等待导入|正在导入/)
    await page.screenshot({ path: path.join(evidenceDir, 'import-progress.png'), fullPage: true })
    await page.reload()
    await page.getByRole('button', { name: '数据与导入', exact: true }).click()
    await expect(page.getByTestId('batch-status')).toHaveText('可查询', { timeout: importWaitMs })
    await expect(page.getByTestId('raw-row-count')).toHaveText('541909')
    await expect(page.getByTestId('processed-rows')).toHaveText('541909')
    await page.screenshot({ path: path.join(evidenceDir, 'import-complete.png'), fullPage: true })
    await page.getByLabel('源数据文件').setInputFiles(path.join(projectRoot, 'data/raw/Online_Retail.xlsx'))
    const [duplicate] = await Promise.all([
      page.waitForResponse(response => response.url().endsWith('/datasets/imports') && response.request().method() === 'POST'),
      page.getByRole('button', { name: '上传并导入' }).click(),
    ])
    expect(duplicate.status()).toBe(200)
    const duplicateResult = await duplicate.json()
    expect(duplicateResult.dataset_id).toBe(initial.dataset_id)
    expect(duplicateResult.batch_id).toBe(initial.batch_id)
    expect(duplicateResult.processed_rows).toBe(541909)
    await expect(page.getByTestId('import-message')).toContainText('复用已有批次')
    await expect(page.getByTestId('raw-row-count')).toHaveText('541909')
    writeFileSync(path.join(evidenceDir, 'duplicate-import.json'), JSON.stringify(duplicateResult, null, 2))
    await page.screenshot({ path: path.join(evidenceDir, 'duplicate-import.png'), fullPage: true })
    expect(errors).toEqual([])
  })

  test('September and October values match real API and independent SQL; refresh and restart use saved GET', async ({ page }) => {
    test.setTimeout(90_000)
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto(`${baseURL}/?view=overview`)
    await expect(page.getByLabel('查询月份')).toBeEnabled()
    const results = []
    for (const month of ['2011-09', '2011-10']) {
      await page.getByLabel('查询月份').fill(month)
      const [response] = await Promise.all([
        page.waitForResponse(r => r.url().endsWith('/queries') && r.request().method() === 'POST'),
        page.getByRole('button', { name: '查询并保存' }).click(),
      ])
      expect(response.status()).toBe(201)
      const value = await response.json()
      results.push(value); queryId = value.query_id
      for (const name of ['positive_amount', 'cancellation_amount', 'net_amount']) {
        await expect(page.getByTestId(`${name}-exact`)).toHaveText(value.result[`${name}_exact`])
        await expect(page.getByTestId(`${name}-display`)).toHaveText(value.result[`${name}_display`])
      }
      await expect(page.getByTestId('invoice-count')).toHaveText(String(value.result.positive_invoice_count))
      await page.screenshot({ path: path.join(evidenceDir, `month-${month}.png`), fullPage: true })
    }
    writeFileSync(path.join(evidenceDir, 'monthly-ui-responses.json'), JSON.stringify(results, null, 2))
    const check = launch('independent-sql', python, ['scripts/verify_ui.py', '--database', path.join(evidenceDir, 'real-ui.sqlite3'), '--responses', path.join(evidenceDir, 'monthly-ui-responses.json'), '--output', path.join(evidenceDir, 'sql-verification.json')], projectRoot)
    expect(await check.done).toBe(0)
    const posts: string[] = []
    page.on('request', request => { if (request.method() === 'POST') posts.push(request.url()) })
    const last = results[1]
    await page.reload()
    await expect(page.getByTestId('net_amount-exact')).toHaveText(last.result.net_amount_exact)
    await stop(backend); await startBackend()
    await page.reload()
    await expect(page.getByTestId('net_amount-exact')).toHaveText(last.result.net_amount_exact)
    const historyResponse = await page.request.get(`${baseURL}/api/v1/queries/${queryId}`)
    expect(await historyResponse.json()).toEqual(last)
    expect(posts).toEqual([])
    await page.getByRole('button', { name: '查询历史', exact: true }).click()
    await expect(page.getByRole('heading', { name: '已保存查询 2 条' })).toBeVisible()
    await page.getByRole('button', { name: '打开查询' }).first().click()
    await expect(page.getByTestId('saved-result')).toBeVisible()
    await page.setViewportSize({ width: 390, height: 844 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    await page.screenshot({ path: path.join(evidenceDir, 'mobile-history-restored.png'), fullPage: true })
    writeFileSync(path.join(evidenceDir, 'refresh-restart.json'), JSON.stringify({ query_id: queryId, posts_during_refresh_restart_history: posts, history_json_unchanged: true, page_errors: errors }, null, 2))
    expect(errors).toEqual([])
  })

  test('partial, no-data, empty-filter, corrupt upload and real backend outage are explicit', async ({ page }) => {
    test.setTimeout(90_000)
    await page.goto(`${baseURL}/?view=overview`)
    await expect(page.getByLabel('查询月份')).toBeEnabled()
    for (const [month, filter, label, expected] of [
      ['2011-12', '', '月份覆盖不完整', null], ['2012-01', '', '无数据', '—'], ['2011-09', 'NO_SUCH_COUNTRY_TEST', '筛选结果为空', '0.000'],
    ]) {
      await page.getByLabel('查询月份').fill(month!)
      await page.getByLabel('国家筛选').fill(filter!)
      await page.getByRole('button', { name: '查询并保存' }).click()
      await expect(page.getByTestId('result-status')).toHaveText(label!)
      if (expected) await expect(page.getByTestId('net_amount-exact')).toHaveText(expected)
      await expect(page.getByLabel('查询月份')).toHaveValue(month!)
      await page.screenshot({ path: path.join(evidenceDir, `boundary-${month}-${filter ? 'empty' : 'all'}.png`), fullPage: true })
    }
    await page.getByRole('button', { name: '数据与导入', exact: true }).click()
    await page.getByLabel('源数据文件').setInputFiles({ name: 'test_fixture_corrupt.zip', mimeType: 'application/zip', buffer: Buffer.from('explicit_test_fixture_not_a_zip') })
    await page.getByRole('button', { name: '上传并导入' }).click()
    await expect(page.getByTestId('import-error')).toContainText('CORRUPT_SOURCE')
    await expect(page.getByTestId('raw-row-count')).toHaveText('541909')
    await page.screenshot({ path: path.join(evidenceDir, 'corrupt-upload-rejected.png'), fullPage: true })
    await stop(backend)
    await page.getByRole('button', { name: '刷新数据' }).click()
    await expect(page.getByTestId('workspace-error')).toBeVisible()
    await page.screenshot({ path: path.join(evidenceDir, 'business-backend-stopped.png'), fullPage: true })
    await startBackend()
    await page.getByRole('button', { name: '刷新数据' }).click()
    await expect(page.getByTestId('workspace-error')).toHaveCount(0)
    const history = await page.request.get(`${baseURL}/api/v1/datasets/ds_9561855056bc9d83ca5a82c198b5130b/queries`)
    expect((await history.json()).total).toBe(5)
    const proof = JSON.parse(readFileSync(path.join(evidenceDir, 'sql-verification.json'), 'utf8'))
    expect(proof.status).toBe('PASS')
  })
})
