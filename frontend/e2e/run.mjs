// Load cache locations before Playwright initializes its transform cache or browser profiles.
import { spawn } from 'node:child_process'
import { createWriteStream, mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { loadEnv } from 'vite'

const frontendRoot = fileURLToPath(new URL('..', import.meta.url))
const projectRoot = path.resolve(frontendRoot, '..')
const env = loadEnv('test', projectRoot, '')
const cacheRoot = process.env.D0_CACHE_DIR ?? env.D0_CACHE_DIR
if (!cacheRoot || !path.isAbsolute(cacheRoot)) {
  throw new Error('Set an absolute D0_CACHE_DIR in the root .env before running browser tests')
}
const runDir = path.join(cacheRoot, 'playwright', `${new Date().toISOString().replace(/[:.]/g, '-')}-${process.pid}`)
const tmpDir = path.join(runDir, 'tmp')
const transformDir = path.join(runDir, 'transform-cache')
mkdirSync(tmpDir, { recursive: true })
mkdirSync(transformDir, { recursive: true })
const cli = path.join(frontendRoot, 'node_modules', '@playwright', 'test', 'cli.js')
const args = [cli, 'test', ...process.argv.slice(2)]
const record = {
  executable: process.execPath,
  args,
  cwd: frontendRoot,
  started_at: new Date().toISOString(),
  ended_at: null,
  exit_code: null,
  signal: null,
  error: null,
}
const save = () => writeFileSync(path.join(runDir, 'launcher.json'), JSON.stringify(record, null, 2), 'utf8')
save()
const log = createWriteStream(path.join(runDir, 'runner.log'), { flags: 'a' })
const child = spawn(process.execPath, args, {
  cwd: frontendRoot,
  windowsHide: true,
  shell: false,
  env: {
    ...process.env,
    D0_CACHE_DIR: cacheRoot,
    D0_E2E_RUN_DIR: runDir,
    PWTEST_CACHE_DIR: transformDir,
    TEMP: tmpDir,
    TMP: tmpDir,
    TMPDIR: tmpDir,
  },
  stdio: ['inherit', 'pipe', 'pipe'],
})
child.stdout.on('data', (chunk) => { process.stdout.write(chunk); log.write(chunk) })
child.stderr.on('data', (chunk) => { process.stderr.write(chunk); log.write(chunk) })
child.once('error', (error) => {
  record.error = error.message
  save()
  process.exitCode = 1
})
child.once('close', (code, signal) => {
  record.ended_at = new Date().toISOString()
  record.exit_code = code
  record.signal = signal
  save()
  log.end()
  process.exitCode = code ?? 1
})

// Interruption only terminates the subprocess tree created by this invocation.
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => {
    if (child.exitCode !== null || child.signalCode !== null || !child.pid) return
    if (process.platform === 'win32') {
      spawn(path.join(process.env.SystemRoot ?? 'C:\\Windows', 'System32/taskkill.exe'),
        ['/PID', String(child.pid), '/T', '/F'], { windowsHide: true, shell: false, stdio: 'ignore' })
    } else child.kill(signal)
  })
}
