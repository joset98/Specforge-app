import type { ExportFormat, PipelineEvent, PipelineResult, Section } from '../types'
import { parseSSE } from './sse'

export const API_URL: string = import.meta.env.VITE_API_URL ?? ''

export type LlmAuth = { provider: 'claude' | 'openai'; key: string } | null

export class ApiError extends Error {
  status: number
  constructor(status: number, detail: string) {
    super(detail)
    this.status = status
  }
}

function authHeaders(auth: LlmAuth): Record<string, string> {
  return auth?.key ? { 'X-LLM-Provider': auth.provider, 'X-LLM-Key': auth.key } : {}
}

async function check(res: Response): Promise<Response> {
  if (res.ok) return res
  let detail = res.statusText
  try {
    const body = await res.json()
    detail = typeof body.detail === 'string' ? body.detail : (body.error ?? JSON.stringify(body.detail))
  } catch { /* non-JSON error body */ }
  throw new ApiError(res.status, detail)
}

async function* stream(path: string, init: RequestInit): AsyncGenerator<PipelineEvent> {
  const res = await check(await fetch(API_URL + path, init))
  if (!res.body) throw new ApiError(500, 'Empty response')
  yield* parseSSE(res.body)
}

export function startRun(
  input: { text?: string; file?: File; teamContext?: string },
  auth: LlmAuth,
  signal?: AbortSignal,
): AsyncGenerator<PipelineEvent> {
  const form = new FormData()
  if (input.file) form.append('file', input.file)
  else form.append('text', input.text ?? '')
  if (input.teamContext) form.append('team_context', input.teamContext)
  return stream('/api/runs', { method: 'POST', body: form, headers: authHeaders(auth), signal })
}

export function refine(
  result: PipelineResult, section: Section, feedback: string, auth: LlmAuth, signal?: AbortSignal,
): AsyncGenerator<PipelineEvent> {
  return stream('/api/refine', {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', ...authHeaders(auth) },
    body: JSON.stringify({ result, section, feedback }),
  })
}

export async function getQuota(): Promise<{ remaining: number; limit: number }> {
  return (await check(await fetch(`${API_URL}/api/quota`))).json()
}

const EXT: Record<ExportFormat, string> = {
  markdown: 'md', json: 'json', 'jira-csv': 'csv', openapi: 'yaml', sql: 'sql',
}

export async function downloadExport(result: PipelineResult, format: ExportFormat): Promise<void> {
  const res = await check(await fetch(`${API_URL}/api/export/${format}`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(result),
  }))
  const url = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = url
  a.download = `requirements.${EXT[format]}`
  a.click()
  URL.revokeObjectURL(url)
}

export async function exportGithub(
  result: PipelineResult, repo: string, token: string,
): Promise<{ issues: { story_id: string; url: string }[]; error?: string }> {
  const res = await fetch(`${API_URL}/api/export/github`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-GitHub-Token': token },
    body: JSON.stringify({ result, repo }),
  })
  if (res.status === 502) return res.json() // partial failure still lists created issues
  return (await check(res)).json()
}
