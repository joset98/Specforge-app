import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError, getQuota, refine, startRun, type LlmAuth } from './api/client'
import { InputPanel, type RunRequest } from './components/InputPanel'
import { PipelineView } from './components/PipelineView'
import { ResultsTabs } from './components/ResultsTabs'
import { STAGE_LABELS } from './lib/labels'
import type { PipelineEvent, PipelineResult, Section, Stage, StageData } from './types'

type Action = () => AsyncGenerator<PipelineEvent>

export default function App() {
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [stages, setStages] = useState<Partial<Record<Stage, StageData>>>({})
  const [log, setLog] = useState<string[]>([])
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [auth, setAuth] = useState<LlmAuth>(null) // memory only, never persisted
  const [showKey, setShowKey] = useState(false)
  const [quota, setQuota] = useState<{ remaining: number; limit: number } | null>(null)
  const lastAction = useRef<Action | null>(null)
  const abort = useRef<AbortController | null>(null)

  const refreshQuota = useCallback(() => { getQuota().then(setQuota).catch(() => setQuota(null)) }, [])
  useEffect(refreshQuota, [refreshQuota])

  async function execute(action: Action) {
    lastAction.current = action
    abort.current?.abort()
    setRunning(true); setError(null); setStages({}); setLog([])
    let gotResult = false
    try {
      for await (const { event, data } of action()) {
        if (event === 'stage') {
          setStages((s) => ({ ...s, [data.agent]: data }))
          if (data.status === 'retry') {
            setLog((l) => [...l, `Validator: ${data.detail} → re-running ${STAGE_LABELS[data.agent]}`])
          }
        } else if (event === 'validation') {
          setLog((l) => [...l, data.passed
            ? `Validation passed (round ${data.rounds})`
            : `Validation found ${data.issues.length} issue(s) (round ${data.rounds})`])
        } else if (event === 'result') {
          gotResult = true
          setResult(data)
          setStages((s) => ({ ...s, validator: { agent: 'validator', status: 'done', detail: '' } }))
        } else if (event === 'error') {
          setError(data.message)
          return
        }
      }
      if (!gotResult) setError('The connection closed before the result arrived.')
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') return
      if (e instanceof ApiError && e.status === 429 && e.message === 'free_quota_exhausted') {
        setShowKey(true)
        setError('The free runs for today are used up. Add your own Claude or OpenAI key to keep going.')
      } else {
        setError(e instanceof ApiError ? e.message : 'Could not reach the server. Check your connection.')
      }
    } finally {
      setRunning(false)
      refreshQuota()
    }
  }

  function signal() {
    abort.current = new AbortController()
    return abort.current.signal
  }

  const onRun = (req: RunRequest) => execute(() => startRun(req, auth, signal()))
  const onRefine = (section: Section, feedback: string) => {
    if (result) execute(() => refine(result, section, feedback, auth, signal()))
  }
  const showPipeline = running || Object.keys(stages).length > 0

  return (
    <div className="app">
      <header className="masthead">
        <h1>Specforge</h1>
        <p>Turn a requirement into user stories, a data model, an API and tests, checked for consistency and ready for Jira, GitHub, OpenAPI and SQL.</p>
      </header>
      <main className="layout">
        <InputPanel
          running={running} quota={quota} auth={auth} onAuthChange={setAuth}
          showKey={showKey} onToggleKey={() => setShowKey((v) => !v)}
          onRun={onRun} onCancel={() => { abort.current?.abort(); setRunning(false) }}
          onImport={(r) => { setResult(r); setStages({}); setLog([]); setError(null) }}
          onError={setError}
        />
        <div className="workspace">
          {error && (
            <div className="error-banner" role="alert">
              <span>{error}</span>
              {lastAction.current && !running && (
                <button type="button" className="btn" onClick={() => lastAction.current && execute(lastAction.current)}>
                  Retry
                </button>
              )}
            </div>
          )}
          {showPipeline && <PipelineView stages={stages} log={log} running={running} />}
          {result ? (
            <ResultsTabs result={result} running={running} onRefine={onRefine} />
          ) : !showPipeline && (
            <section className="empty">
              <h2>What you get</h2>
              <ol>
                <li><strong>Product Owner</strong> writes user stories with Gherkin acceptance criteria.</li>
                <li><strong>Architect</strong> designs the tables and REST endpoints.</li>
                <li><strong>QA</strong> writes test cases for every endpoint.</li>
                <li><strong>Validator</strong> checks that everything links up and sends mistakes back to the agent that made them.</li>
              </ol>
              <p className="muted">Generated content is in Spanish. Pick an example on the left to see it run.</p>
            </section>
          )}
        </div>
      </main>
    </div>
  )
}
