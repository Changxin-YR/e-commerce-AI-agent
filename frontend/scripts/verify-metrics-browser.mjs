// D3 transport evidence only: real persisted JSON in Edge, no D4 business-page claim.
import { chromium } from '@playwright/test'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'

const [base, queryId, output] = process.argv.slice(2)
if (!/^http:\/\/127\.0\.0\.1:\d+$/.test(base ?? '') || !/^q_[a-f0-9]{32}$/.test(queryId ?? '') || !output) {
  throw new Error('Usage: node verify-metrics-browser.mjs LOCAL_BASE QUERY_ID OUTPUT')
}
mkdirSync(output, { recursive: true })
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
await context.tracing.start({ screenshots: true, snapshots: true })
const page = await context.newPage()
const requests = []
page.on('request', r => requests.push({ method: r.method(), url: r.url() }))
const result = { scope: 'D3_saved_real_JSON_refresh_not_D4_business_UI', status: 'FAIL' }
try {
  const response = await page.goto(`${base}/api/v1/queries/${queryId}`)
  if (response.status() !== 200) throw new Error('History HTTP failed')
  const first = await response.json()
  if (first.query_id !== queryId || first.result.status !== 'PASS') throw new Error('Saved history mismatch')
  await page.screenshot({ path: path.join(output, 'history-before-reload.png'), fullPage: true })
  const reload = await page.reload()
  const second = await reload.json()
  if (JSON.stringify(first) !== JSON.stringify(second)) throw new Error('Refresh changed saved history')
  if (requests.some(r => r.method !== 'GET')) throw new Error('Browser performed a write')
  await page.screenshot({ path: path.join(output, 'history-after-reload.png'), fullPage: true })
  Object.assign(result, { status: 'PASS', query_id: queryId, result_sha256: first.result_sha256, requests, browser_version: browser.version() })
} finally {
  await context.tracing.stop({ path: path.join(output, 'trace.zip') })
  await browser.close()
  writeFileSync(path.join(output, 'result.json'), JSON.stringify(result, null, 2))
}
