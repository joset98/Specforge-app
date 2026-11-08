import { CircleAlert, CircleCheck } from 'lucide-react'
import type { ValidationReport } from '../../types'

const CHECKS = [
  ['STORY_WITHOUT_ENDPOINT', 'Every story is served by an endpoint'],
  ['ENDPOINT_UNKNOWN_STORY', 'Endpoints only reference existing stories'],
  ['ENDPOINT_UNKNOWN_TABLE', 'Request/response tables exist'],
  ['ENDPOINT_WITHOUT_TEST', 'Every endpoint has at least one test'],
  ['TEST_UNKNOWN_REF', 'Tests only reference existing endpoints and stories'],
  ['FK_BROKEN', 'Foreign keys point to existing columns'],
  ['TABLE_WITHOUT_PK', 'Every table has a primary key'],
  ['DUPLICATE_ID', 'Ids are unique'],
  ['GHERKIN_INVALID', 'Gherkin has Escenario / Dado / Cuando / Entonces'],
] as const

export function ValidationTab({ report }: { report: ValidationReport }) {
  const failing = new Set(report.issues.map((i) => i.code))
  return (
    <div className="stack">
      <p className={`validation-summary ${report.passed ? 'ok' : 'warn'}`}>
        {report.passed
          ? `All checks passed after ${report.rounds} correction round${report.rounds === 1 ? '' : 's'}.`
          : `${report.issues.length} issue${report.issues.length === 1 ? '' : 's'} left after ${report.rounds} correction rounds. The result is usable; review these before exporting.`}
      </p>
      <ul className="checks">
        {CHECKS.map(([code, label]) => (
          <li key={code} data-ok={!failing.has(code)}>
            {failing.has(code) ? <CircleAlert size={16} aria-label="Failing" /> : <CircleCheck size={16} aria-label="Passing" />}
            <span>{label}</span>
            <code>{code}</code>
          </li>
        ))}
      </ul>
      {report.issues.length > 0 && (
        <ul className="issues">
          {report.issues.map((i, n) => (
            <li key={n}><code>{i.code}</code> {i.message}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
