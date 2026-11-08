import type { TestCase } from '../../types'

const TYPE_LABEL = { happy_path: 'Happy path', edge_case: 'Edge case', error: 'Error' }

export function TestsTab({ tests }: { tests: TestCase[] }) {
  return (
    <div className="stack">
      {tests.map((t) => (
        <article key={t.id} className="test-case">
          <header>
            <code className="id">{t.id}</code>
            <h3>{t.title}</h3>
            <span className={`badge type-${t.type}`}>{TYPE_LABEL[t.type]}</span>
          </header>
          <p className="refs">
            <code>{t.endpoint_id}</code> · <code>{t.story_id}</code>
          </p>
          <ol>{t.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
          <p className="expected"><strong>Expected:</strong> {t.expected}</p>
        </article>
      ))}
    </div>
  )
}
