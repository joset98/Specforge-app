import { useRef, useState } from 'react'
import type { PipelineResult, Section } from '../types'
import { ExportTab } from './ExportTab'
import { RefineBox } from './RefineBox'
import { ApiTab } from './tabs/ApiTab'
import { DataModelTab } from './tabs/DataModelTab'
import { StoriesTab } from './tabs/StoriesTab'
import { TestsTab } from './tabs/TestsTab'
import { ValidationTab } from './tabs/ValidationTab'

type Tab = 'stories' | 'data' | 'api' | 'tests' | 'validation' | 'export'

interface Props {
  result: PipelineResult
  running: boolean
  onRefine: (section: Section, feedback: string) => void
}

export function ResultsTabs({ result, running, onRefine }: Props) {
  const [tab, setTab] = useState<Tab>('stories')
  const tabRefs = useRef<Partial<Record<Tab, HTMLButtonElement | null>>>({})
  const { stories, architecture, tests, validation } = result
  const tabs: { id: Tab; label: string; count?: number; warn?: boolean }[] = [
    { id: 'stories', label: 'Stories', count: stories.length },
    { id: 'data', label: 'Data model', count: architecture.tables.length },
    { id: 'api', label: 'API', count: architecture.endpoints.length },
    { id: 'tests', label: 'Tests', count: tests.length },
    { id: 'validation', label: 'Validation', warn: !validation.passed },
    { id: 'export', label: 'Export' },
  ]

  function onKey(e: React.KeyboardEvent, i: number) {
    const step = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0
    if (!step) return
    const next = tabs[(i + step + tabs.length) % tabs.length].id
    setTab(next)
    tabRefs.current[next]?.focus()
  }

  const refine = (section: Section, placeholder: string) => (
    <RefineBox section={section} disabled={running} placeholder={placeholder} onRefine={onRefine} />
  )

  return (
    <section className="results" aria-label="Results">
      <div role="tablist" aria-label="Result sections" className="tablist">
        {tabs.map((t, i) => (
          <button
            key={t.id} role="tab" id={`tab-${t.id}`} aria-controls={`panel-${t.id}`}
            aria-selected={tab === t.id} tabIndex={tab === t.id ? 0 : -1}
            ref={(el) => { tabRefs.current[t.id] = el }}
            onClick={() => setTab(t.id)} onKeyDown={(e) => onKey(e, i)}
          >
            {t.label}
            {t.count !== undefined && <span className="count">{t.count}</span>}
            {t.warn && <span className="warn-dot" aria-label="has issues" />}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="tabpanel" tabIndex={0}>
        {tab === 'stories' && <>{refine('product_owner', 'E.g. split login into two stories, add password recovery')}<StoriesTab stories={stories} /></>}
        {tab === 'data' && <>{refine('architect', 'E.g. use soft delete, add an audit table')}<DataModelTab architecture={architecture} /></>}
        {tab === 'api' && <>{refine('architect', 'E.g. version the API under /v1, add pagination to lists')}<ApiTab endpoints={architecture.endpoints} /></>}
        {tab === 'tests' && <>{refine('qa', 'E.g. more permission and validation error cases')}<TestsTab tests={tests} /></>}
        {tab === 'validation' && <ValidationTab report={validation} />}
        {tab === 'export' && <ExportTab result={result} />}
      </div>
    </section>
  )
}
