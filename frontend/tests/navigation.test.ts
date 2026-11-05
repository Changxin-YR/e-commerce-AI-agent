import { afterEach, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import type { VueWrapper } from '@vue/test-utils'
import WorkspaceShell from '../src/components/WorkspaceShell.vue'
import { currentView } from '../src/navigation'
let wrapper: VueWrapper | undefined
afterEach(() => { wrapper?.unmount(); wrapper = undefined })
it('opens AI by default while preserving existing query deep links', () => {
  history.replaceState(null, '', '/')
  expect(currentView()).toBe('analysis')
  history.replaceState(null, '', '/?query=existing_query')
  expect(currentView()).toBe('overview')
  history.replaceState(null, '', '/?view=reports&report=existing_report')
  expect(currentView()).toBe('reports')
})
it('exposes mobile navigation state, closes with Escape and reports the chosen page', async () => {
  wrapper = mount(WorkspaceShell, { props: { view: 'analysis' } })
  const trigger = wrapper.get('[aria-controls="workspace-sidebar"]')
  expect(trigger.attributes('aria-expanded')).toBe('false')
  await trigger.trigger('click')
  expect(trigger.attributes('aria-expanded')).toBe('true')
  await wrapper.trigger('keydown', { key: 'Escape' })
  expect(trigger.attributes('aria-expanded')).toBe('false')
  await wrapper.get('[aria-label="经营概览"]').trigger('click')
  expect(wrapper.emitted('navigate')).toEqual([['overview']])
  await wrapper.setProps({ view: 'overview' })
  expect(document.title).toBe('经营概览 · 电商 AI 工作台')
  expect(wrapper.get('[aria-label="经营概览"]').attributes('aria-current')).toBe('page')
})
