import type { Story } from '../../types'

const KEYWORD = /^(\s*)(Característica|Escenario|Esquema del escenario|Antecedentes|Dado|Cuando|Entonces|Y|Pero)\b/

function Gherkin({ source }: { source: string }) {
  return (
    <pre className="gherkin">
      {source.split('\n').map((line, i) => {
        const m = KEYWORD.exec(line)
        return (
          <span key={i} className="line">
            {m ? <>{m[1]}<b className={`kw kw-${m[2] === 'Característica' || m[2] === 'Escenario' ? 'block' : 'step'}`}>{m[2]}</b>{line.slice(m[0].length)}</> : line}
            {'\n'}
          </span>
        )
      })}
    </pre>
  )
}

export function StoriesTab({ stories }: { stories: Story[] }) {
  return (
    <div className="stack">
      {stories.map((s) => (
        <article key={s.id} className="story">
          <header>
            <code className="id">{s.id}</code>
            <h3>{s.title}</h3>
            <span className={`badge priority-${s.priority}`}>{s.priority}</span>
          </header>
          <p className="user-story">
            Como <strong>{s.as_a}</strong>, quiero <strong>{s.i_want}</strong>, para {s.so_that}.
          </p>
          <Gherkin source={s.gherkin} />
        </article>
      ))}
    </div>
  )
}
