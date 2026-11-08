import { afterEach, expect, test, vi } from 'vitest'
import { sampleResult } from '../fixtures'
import { ApiError, exportGithub } from './client'

afterEach(() => vi.unstubAllGlobals())

test('exportGithub returns created issues and GitHub reason on a 4xx', async () => {
  const body = { issues: [{ story_id: 'US-1', url: 'u' }], error: 'Bad credentials' }
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status: 401 })))
  expect(await exportGithub(sampleResult, 'o/r', 't')).toEqual(body)
})

test('exportGithub throws ApiError for validation errors', async () => {
  vi.stubGlobal('fetch', vi.fn(async () =>
    new Response(JSON.stringify({ detail: 'Missing X-GitHub-Token header.' }), { status: 400 })))
  await expect(exportGithub(sampleResult, 'o/r', '')).rejects.toBeInstanceOf(ApiError)
})
