import { FileText, FileUp, KeyRound, Play, Upload, X } from 'lucide-react'
import { useRef, useState } from 'react'
import type { LlmAuth } from '../api/client'
import { EXAMPLES } from '../examples'
import type { PipelineResult } from '../types'
import { KeyPanel } from './KeyPanel'

export interface RunRequest { text?: string; file?: File; teamContext?: string }

interface Props {
  running: boolean
  quota: { remaining: number; limit: number } | null
  auth: LlmAuth
  onAuthChange: (auth: LlmAuth) => void
  showKey: boolean
  onToggleKey: () => void
  onRun: (req: RunRequest) => void
  onCancel: () => void
  onImport: (result: PipelineResult) => void
  onError: (message: string) => void
}

function looksLikeResult(x: unknown): x is PipelineResult {
  const r = x as PipelineResult
  return !!r && !!r.input && Array.isArray(r.stories) && Array.isArray(r.tests) &&
    !!r.architecture && Array.isArray(r.architecture.tables) && Array.isArray(r.architecture.endpoints)
}

export function InputPanel(p: Props) {
  const [text, setText] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [teamContext, setTeamContext] = useState('')
  const [dragging, setDragging] = useState(false)
  const fileInput = useRef<HTMLInputElement>(null)
  const importInput = useRef<HTMLInputElement>(null)

  const canRun = !p.running && (file !== null || text.trim().length > 0)
  const usingOwnKey = !!p.auth?.key

  function pickFile(f: File | undefined) {
    if (!f) return
    if (!/\.(pdf|docx|txt|md)$/i.test(f.name)) return p.onError('Use a PDF, DOCX, TXT or MD file.')
    if (f.size > 5 * 1024 * 1024) return p.onError('That file is larger than 5 MB.')
    setFile(f)
  }

  async function importJson(f: File | undefined) {
    if (!f) return
    try {
      const data: unknown = JSON.parse(await f.text())
      if (!looksLikeResult(data)) throw new Error('shape')
      p.onImport(data)
    } catch {
      p.onError('That file is not a Specforge JSON export.')
    }
  }

  function run(req: RunRequest) {
    p.onRun({ ...req, teamContext: teamContext.trim() || undefined })
  }

  return (
    <aside className="input-panel">
      <form onSubmit={(e) => { e.preventDefault(); if (canRun) run(file ? { file } : { text }) }}>
        <label className="field">
          <span>Requirement</span>
          <textarea
            rows={8} value={text} disabled={!!file}
            placeholder="Describe the software you need, at any level of detail."
            onChange={(e) => setText(e.target.value)}
          />
        </label>

        {file ? (
          <div className="file-chip">
            <FileText size={16} aria-hidden />
            <span>{file.name}</span>
            <button type="button" className="icon-btn" aria-label="Remove file" onClick={() => setFile(null)}>
              <X size={16} />
            </button>
          </div>
        ) : (
          <div
            className={`dropzone${dragging ? ' dragging' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); pickFile(e.dataTransfer.files[0]) }}
          >
            <Upload size={16} aria-hidden />
            <span>Drop a PDF or DOCX, or</span>
            <button type="button" className="link-btn" onClick={() => fileInput.current?.click()}>
              browse
            </button>
            <input ref={fileInput} type="file" hidden accept=".pdf,.docx,.txt,.md"
                   onChange={(e) => { pickFile(e.target.files?.[0]); e.target.value = '' }} />
          </div>
        )}

        <details className="team-context">
          <summary>Team context <span className="muted">optional</span></summary>
          <textarea
            rows={3} maxLength={2000} value={teamContext} aria-label="Team context"
            placeholder="Stack, conventions, constraints. E.g. PostgreSQL, NestJS, OAuth login"
            onChange={(e) => setTeamContext(e.target.value)}
          />
        </details>

        <div className="actions">
          {p.running ? (
            <button type="button" className="btn" onClick={p.onCancel}>Stop</button>
          ) : (
            <button type="submit" className="btn primary" disabled={!canRun}>
              <Play size={16} aria-hidden /> Generate
            </button>
          )}
          <span className="quota">
            {usingOwnKey
              ? 'Using your key'
              : p.quota ? `${p.quota.remaining} of ${p.quota.limit} free runs left today` : ''}
          </span>
        </div>
      </form>

      <div className="examples">
        <span className="label">Try an example</span>
        <div className="chips">
          {EXAMPLES.map((ex) => (
            <button key={ex.label} type="button" className="chip" disabled={p.running}
                    onClick={() => { setFile(null); setText(ex.text); run({ text: ex.text }) }}>
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <div className="secondary-actions">
        <button type="button" className="link-btn" aria-expanded={p.showKey} onClick={p.onToggleKey}>
          <KeyRound size={14} aria-hidden /> Use your own key
        </button>
        <button type="button" className="link-btn" onClick={() => importInput.current?.click()}>
          <FileUp size={14} aria-hidden /> Import JSON
        </button>
        <input ref={importInput} type="file" hidden accept=".json,application/json"
               onChange={(e) => { importJson(e.target.files?.[0]); e.target.value = '' }} />
      </div>
      {p.showKey && <KeyPanel auth={p.auth} onChange={p.onAuthChange} />}
    </aside>
  )
}
