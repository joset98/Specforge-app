import { CircleDot, Download } from 'lucide-react'
import { useState } from 'react'
import { ApiError, downloadExport, exportGithub } from '../api/client'
import type { ExportFormat, PipelineResult } from '../types'

const FORMATS: { format: ExportFormat; label: string; detail: string }[] = [
  { format: 'markdown', label: 'Markdown', detail: 'Everything in one document; the ER diagram renders on GitHub' },
  { format: 'jira-csv', label: 'Jira CSV', detail: 'One story per row, ready for Jira’s CSV import' },
  { format: 'openapi', label: 'OpenAPI 3.1', detail: 'Paths, parameters and schemas from the data model' },
  { format: 'sql', label: 'PostgreSQL', detail: 'CREATE TABLE script ordered by foreign keys' },
  { format: 'json', label: 'JSON', detail: 'Raw result; import it later to keep refining' },
]

export function ExportTab({ result }: { result: PipelineResult }) {
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [repo, setRepo] = useState('')
  const [token, setToken] = useState('')
  const [issues, setIssues] = useState<{ story_id: string; url: string }[]>([])

  async function download(format: ExportFormat) {
    setBusy(format); setError(null)
    try { await downloadExport(result, format) } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Download failed. Check your connection.')
    } finally { setBusy(null) }
  }

  async function github(e: React.FormEvent) {
    e.preventDefault()
    setBusy('github'); setError(null); setIssues([])
    try {
      const res = await exportGithub(result, repo.trim(), token.trim())
      setIssues(res.issues)
      if (res.error) setError(`GitHub: ${res.error}${res.issues.length ? ` (created ${res.issues.length} before failing)` : ''}`)
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not reach the server.')
    } finally { setBusy(null) }
  }

  return (
    <div className="stack">
      <ul className="export-list">
        {FORMATS.map((f) => (
          <li key={f.format}>
            <div>
              <strong>{f.label}</strong>
              <span className="muted">{f.detail}</span>
            </div>
            <button type="button" className="btn" disabled={busy !== null} onClick={() => download(f.format)}>
              <Download size={16} aria-hidden /> {busy === f.format ? 'Preparing…' : 'Download'}
            </button>
          </li>
        ))}
      </ul>

      <form className="github-form" onSubmit={github}>
        <h3><CircleDot size={18} aria-hidden /> Create GitHub issues</h3>
        <p className="hint">One issue per story, labelled ai-generated. The token is used for this request only and never stored. It needs Issues: write access.</p>
        <div className="row">
          <label className="field">
            <span>Repository</span>
            <input value={repo} placeholder="owner/name" pattern="[\w.\-]+/[\w.\-]+" required
                   onChange={(e) => setRepo(e.target.value)} />
          </label>
          <label className="field">
            <span>Token</span>
            <input type="password" autoComplete="off" value={token} placeholder="github_pat_…" required
                   onChange={(e) => setToken(e.target.value)} />
          </label>
        </div>
        <button type="submit" className="btn" disabled={busy !== null}>
          {busy === 'github' ? 'Creating issues…' : `Create ${result.stories.length} issues`}
        </button>
      </form>

      {error && <p className="error" role="alert">{error}</p>}
      {issues.length > 0 && (
        <ul className="issue-links">
          {issues.map((i) => (
            <li key={i.url}><code>{i.story_id}</code> <a href={i.url} target="_blank" rel="noreferrer">{i.url}</a></li>
          ))}
        </ul>
      )}
    </div>
  )
}
