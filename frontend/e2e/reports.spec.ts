import { expect, test } from '@playwright/test'
import { spawn } from 'node:child_process'
import type { ChildProcess } from 'node:child_process'
import { copyFileSync, closeSync, mkdirSync, openSync, writeFileSync, readFileSync } from 'node:fs'
import net from 'node:net'
import { createServer } from 'node:http'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

// Real UCI snapshot copied to an isolated database; browser upload verifies workbook reuse.
const projectRoot = fileURLToPath(new URL('../..', import.meta.url))
const runDir = process.env.D0_E2E_RUN_DIR
if (!runDir) throw new Error('Run this suite through its Playwright configuration')
mkdirSync(runDir, { recursive: true })
const evidenceDir = path.join(runDir, 'reports')
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
let fixtureMode = false
let localEnv: NodeJS.ProcessEnv
let baseURL: string

function saveCommands() {
  writeFileSync(path.join(evidenceDir, 'commands.json'), JSON.stringify({
    source_kind: 'development_test_evidence',
    database_kind: 'real_UCI_copy_with_browser_upload_reuse',
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
  backend = launch(`backend-${backendStarts}`, python, fixtureMode
    ? ['-m', 'uvicorn', 'scripts.verify_agent:server_app', '--factory', '--host', '127.0.0.1', '--port', String(backendPort)]
    : ['-X', 'utf8', 'scripts/manage.py', 'backend'], projectRoot)
  await waitReady(backend, `http://127.0.0.1:${backendPort}/healthz`, true)
}


test.describe.serial('D7 real data reports and scripted clarification', () => {
  const captured: unknown[] = []
  let reportId = '', waitingRunId = '', waitingThreadId = ''
  test.beforeAll(async () => {
    test.setTimeout(75000)
    const sourceDatabase = process.env.E2E_SOURCE_DATABASE ?? process.env.D7_SOURCE_DATABASE
    if (!sourceDatabase) throw new Error('E2E_SOURCE_DATABASE must point to an audited real database')
    copyFileSync(sourceDatabase, path.join(evidenceDir, 'real-ui.sqlite3'))
    backendPort = await chooseFreePort()
    do { frontendPort = await chooseFreePort() } while (frontendPort === backendPort)
    baseURL = `http://127.0.0.1:${frontendPort}`
    localEnv = {
      ...process.env, APP_ENV: 'test', APP_HOST: '127.0.0.1', APP_PORT: String(backendPort), FRONTEND_PORT: String(frontendPort),
      DATABASE_URL: `sqlite:///${path.join(evidenceDir, 'real-ui.sqlite3').replace(/\\/g, '/')}`,
      IMPORT_CACHE_DIR: path.join(evidenceDir, 'imports'), D0_CACHE_DIR: evidenceDir,
      PYTHONDONTWRITEBYTECODE: '1', PYTHONUTF8: '1', ALLOW_PAID_MODEL_CALLS: 'false',
      MODEL_MAX_TOTAL_REQUESTS: '0', MODEL_MAX_TOTAL_TOKENS: '0', MODEL_MAX_TOKENS_PER_RUN: '0',
      AGENT_FIXTURE_DATABASE: path.join(evidenceDir, 'real-ui.sqlite3'), AGENT_FIXTURE_OUTPUT: evidenceDir,
      AGENT_FIXTURE_PORT: String(backendPort),
    }
    await startBackend()
    frontend = launch('frontend', python, ['-X', 'utf8', 'scripts/manage.py', 'frontend'], projectRoot)
    await waitReady(frontend, baseURL)
  })
  test.afterAll(async () => {
    const cleanup = await Promise.allSettled([stop(frontend), stop(backend)])
    saveCommands()
    for (const result of cleanup) if (result.status === 'rejected') throw result.reason
  })
  test('real upload reuse -> B0 comparison -> exact report -> downloads -> GET history after restart', async ({ page }) => {
    test.setTimeout(120000)
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
    await page.goto(baseURL)
    await expect(page).toHaveTitle(/电商/)
    await page.getByRole('button', { name: '数据与导入', exact: true }).click()
    await page.getByLabel('源数据文件').setInputFiles(path.join(projectRoot, 'data/raw/Online_Retail.xlsx'))
    await page.getByRole('button', { name: '上传并导入' }).click()
    await expect(page.getByTestId('import-message')).toContainText('复用已有批次')
    await page.getByRole('button', { name: '智能分析', exact: true }).click()
    await expect(page.getByTestId('model-blocked')).toContainText('BLOCKED_AUTHORIZATION')
    await expect(page.getByRole('button', { name: '提交分析任务' })).toBeDisabled()
    await page.screenshot({ path: path.join(evidenceDir, 'no-model-b0.png'), fullPage: true })
    await page.getByLabel('起始日期', { exact: true }).fill('2011-10-01')
    await page.getByLabel('结束日期（不含）', { exact: true }).fill('2011-11-01')
    await page.getByText('可选：与基期比较', { exact: true }).click()
    await page.getByLabel('基期起始日期').fill('2011-09-01')
    await page.getByLabel('基期结束日期（不含）').fill('2011-10-01')
    const [response] = await Promise.all([page.waitForResponse(r => r.url().endsWith('/reports') && r.request().method() === 'POST'), page.getByRole('button', { name: '生成确定性报表' }).click()])
    expect(response.status()).toBe(201)
    const report = await response.json(); captured.push(report); reportId = report.report_id
    await expect(page.getByTestId('report-detail')).toContainText('1070704.670')
    await expect(page.getByTestId('report-detail')).toContainText('51017.048')
    await page.screenshot({ path: path.join(evidenceDir, 'b0-report-desktop.png'), fullPage: false })
    const downloadJson = page.waitForEvent('download'); await page.getByRole('link', { name: '导出 JSON' }).click()
    const jsonFile = path.join(evidenceDir, 'downloaded-report.json'); await (await downloadJson).saveAs(jsonFile)
    expect(JSON.parse(readFileSync(jsonFile, 'utf8'))).toEqual(report)
    const downloadMd = page.waitForEvent('download'); await page.getByRole('link', { name: '导出 Markdown' }).click()
    await (await downloadMd).saveAs(path.join(evidenceDir, 'downloaded-report.md'))
    const posts: string[] = []
    page.on('request', request => { if (request.method() === 'POST') posts.push(request.url()) })
    await stop(backend); await startBackend(); await page.reload()
    await expect(page.getByTestId('report-detail')).toContainText('1070704.670')
    expect(await (await page.request.get(`${baseURL}/api/v1/reports/${reportId}`)).json()).toEqual(report)
    await page.getByRole('button', { name: '查看来源任务' }).click()
    await expect(page.getByTestId('run-status')).toHaveText('已完成')
    await expect(page.getByTestId('run-detail')).toContainText('deterministic_no_model')
    await page.setViewportSize({ width: 390, height: 844 })
    await page.screenshot({ path: path.join(evidenceDir, 'task-mobile.png'), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    expect(posts).toEqual([]); expect(errors).toEqual([])
    writeFileSync(path.join(evidenceDir, 'console-b0.json'), JSON.stringify(errors))
  })
  test('partial and empty reports keep distinct states', async ({ page }) => {
    test.setTimeout(90000)
    await page.goto(`${baseURL}/?view=analysis`)
    for (const [from, to, status] of [['2011-12-01', '2012-01-01', 'PARTIAL_PERIOD'], ['2012-01-01', '2012-02-01', 'NO_DATA']]) {
      await page.getByRole('button', { name: '智能分析', exact: true }).click()
      await page.getByLabel('起始日期', { exact: true }).fill(from!)
      await page.getByLabel('结束日期（不含）', { exact: true }).fill(to!)
      const [response] = await Promise.all([page.waitForResponse(r => r.url().endsWith('/reports') && r.request().method() === 'POST'), page.getByRole('button', { name: '生成确定性报表' }).click()])
      expect(response.status()).toBe(201)
      const report = await response.json(); captured.push(report)
      expect(report.content.business_result).toBe(status)
      await expect(page.getByTestId('report-detail')).toBeVisible()
      if (status === 'NO_DATA') await expect(page.getByTestId('report-detail')).toContainText('没有可引用数值')
      await page.screenshot({ path: path.join(evidenceDir, `report-${status}.png`), fullPage: false })
    }
    writeFileSync(path.join(evidenceDir, 'captured-reports.json'), JSON.stringify(captured, null, 2))
    const check = launch('independent-report-sql', python, ['scripts/verify_reports.py', '--database', path.join(evidenceDir, 'real-ui.sqlite3'), '--reports', path.join(evidenceDir, 'captured-reports.json'), '--output', path.join(evidenceDir, 'report-sql.json')], projectRoot)
    expect(await check.done).toBe(0)
  })
  test('scripted B2 clarification survives restart, replies in the same run and exports cited real values', async ({ page }) => {
    test.setTimeout(90000)
    await stop(backend); fixtureMode = true; await startBackend()
    await page.goto(`${baseURL}/?view=analysis`)
    await expect(page.getByTestId('fixture-banner')).toBeVisible()
    await page.getByLabel('经营问题').fill('test_fixture_case=clarify')
    await page.getByRole('button', { name: '提交分析任务' }).click()
    await expect(page.getByTestId('run-status')).toHaveText('等待补充条件')
    waitingRunId = new URL(page.url()).searchParams.get('run')!
    const waiting = await (await page.request.get(`${baseURL}/api/v1/runs/${waitingRunId}`)).json()
    waitingThreadId = waiting.thread_id
    await page.screenshot({ path: path.join(evidenceDir, 'waiting-input.png'), fullPage: false })
    await stop(backend); await startBackend(); await page.reload()
    await expect(page.getByTestId('run-status')).toHaveText('等待补充条件')
    await page.getByLabel('period', { exact: true }).fill('2011-09')
    await page.getByRole('button', { name: '补答并继续同一任务' }).click()
    await expect(page.getByTestId('run-status')).toHaveText('已完成')
    expect(new URL(page.url()).searchParams.get('run')).toBe(waitingRunId)
    const completed = await (await page.request.get(`${baseURL}/api/v1/runs/${waitingRunId}`)).json()
    expect(completed.thread_id).toBe(waitingThreadId)
    expect(completed.usage.requests_reserved).toBe(3)
    await page.getByRole('button', { name: '查看报告', exact: true }).click()
    await expect(page.getByTestId('report-fixture')).toBeVisible()
    await expect(page.getByTestId('report-detail')).toContainText('1019687.622')
    await page.screenshot({ path: path.join(evidenceDir, 'scripted-report.png'), fullPage: false })
    const before = await (await page.request.get(`${baseURL}/api/v1/runs/${waitingRunId}`)).json()
    await page.reload(); await expect(page.getByTestId('report-detail')).toContainText('1019687.622')
    expect(await (await page.request.get(`${baseURL}/api/v1/runs/${waitingRunId}`)).json()).toEqual(before)
    const exported = await (await page.request.get(`${baseURL}/api/v1/reports/${completed.result_ref}/export`)).json()
    expect(exported.content.claims[0].value).toBe('1019687.622')
    writeFileSync(path.join(evidenceDir, 'scripted-run.json'), JSON.stringify(completed, null, 2))
  })
  test('D8 browser escapes stored questions and rejects an actual foreign-origin form', async ({ page }) => {
    const dialogs: string[] = []
    page.on('dialog', dialog => { dialogs.push(dialog.message()); void dialog.dismiss() })
    const home = await page.goto(`${baseURL}/?view=analysis`)
    expect(home?.headers()['x-frame-options']).toBe('DENY')
    expect(home?.headers()['content-security-policy']).toContain("frame-ancestors 'none'")
    const attack = '<img src=x onerror=alert(1)> test_fixture_case=unsupported'
    await page.getByLabel('经营问题').fill(attack)
    await page.getByRole('button', { name: '提交分析任务' }).click()
    await expect(page.getByTestId('run-status')).toHaveText('已完成')
    await expect(page.getByTestId('run-detail')).toContainText(attack)
    expect(await page.locator('img[src="x"]').count()).toBe(0)
    await page.reload()
    await expect(page.getByTestId('run-detail')).toContainText(attack)
    expect(dialogs).toEqual([])
    await page.screenshot({ path: path.join(evidenceDir, 'security-escaped-question.png'), fullPage: false })
    const before = await (await page.request.get(`${baseURL}/api/v1/reports`)).json()
    const oversized = await page.request.post(`${baseURL}/api/v1/reports`, {
      headers: { Origin: baseURL, 'Content-Type': 'application/json' }, data: ' '.repeat(65537),
    })
    expect(oversized.status()).toBe(413)
    const attacker = createServer((_req, res) => {
      res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' })
      res.end(`<form action="${baseURL}/api/v1/reports" method="POST"><input name="idempotency_key" value="test_fixture_csrf"><button>提交跨源测试表单</button></form>`)
    })
    await new Promise<void>(resolve => attacker.listen(0, '127.0.0.1', resolve))
    try {
      const address = attacker.address()
      if (!address || typeof address === 'string') throw new Error('Missing test origin')
      await page.goto(`http://127.0.0.1:${address.port}`)
      const [rejected] = await Promise.all([
        page.waitForResponse(r => r.url() === `${baseURL}/api/v1/reports` && r.request().method() === 'POST'),
        page.getByRole('button', { name: '提交跨源测试表单' }).click(),
      ])
      expect(rejected.status()).toBe(403)
      expect((await rejected.json()).error.code).toBe('UNTRUSTED_ORIGIN')
      await page.screenshot({ path: path.join(evidenceDir, 'security-cross-origin-rejected.png'), fullPage: false })
      expect(await (await page.request.get(`${baseURL}/api/v1/reports`)).json()).toEqual(before)
      writeFileSync(path.join(evidenceDir, 'security-browser.json'), JSON.stringify({
        source_kind: 'test_fixture_attacks_on_real_local_services', xss_dialogs: dialogs,
        cross_origin_status: rejected.status(), oversized_json_status: oversized.status(), reports_unchanged: true,
      }, null, 2))
    } finally {
      await new Promise<void>((resolve, reject) => attacker.close(error => error ? reject(error) : resolve()))
    }
  })
})
