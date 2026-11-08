import { useEffect, useId, useRef, useState } from 'react'
import { toErDiagram } from '../../lib/mermaid'
import type { ArchitectOutput } from '../../types'

function prefersDark() {
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? false
}

export function DataModelTab({ architecture }: { architecture: ArchitectOutput }) {
  const ref = useRef<HTMLDivElement>(null)
  const id = 'er' + useId().replace(/[^a-zA-Z0-9]/g, '')
  const [failed, setFailed] = useState(false)
  const source = toErDiagram(architecture)

  useEffect(() => {
    let cancelled = false
    // mermaid is large: load it only when the diagram is shown.
    import('mermaid').then(async ({ default: mermaid }) => {
      mermaid.initialize({ startOnLoad: false, theme: prefersDark() ? 'dark' : 'neutral',
                           securityLevel: 'strict', fontFamily: 'inherit' })
      try {
        const { svg } = await mermaid.render(id, source)
        if (!cancelled && ref.current) { ref.current.innerHTML = svg; setFailed(false) }
      } catch {
        if (!cancelled) setFailed(true)
      }
    })
    return () => { cancelled = true }
  }, [id, source])

  return (
    <div className="stack">
      <div className="diagram" ref={ref} role="img" aria-label="Entity relationship diagram" />
      {failed && <pre className="code">{source}</pre>}
      <div className="tables">
        {architecture.tables.map((t) => (
          <table key={t.name} className="data">
            <caption>{t.name}</caption>
            <thead><tr><th>Column</th><th>Type</th><th>Keys</th><th>Null</th></tr></thead>
            <tbody>
              {t.columns.map((c) => (
                <tr key={c.name}>
                  <td><code>{c.name}</code></td>
                  <td>{c.type}</td>
                  <td>{[c.primary_key && 'PK', c.foreign_key && `FK → ${c.foreign_key}`].filter(Boolean).join(' · ')}</td>
                  <td>{c.nullable && !c.primary_key ? 'yes' : 'no'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ))}
      </div>
    </div>
  )
}
