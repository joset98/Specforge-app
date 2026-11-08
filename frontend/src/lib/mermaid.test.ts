import { expect, test } from 'vitest'
import { sampleResult } from '../fixtures'
import { toErDiagram } from './mermaid'

test('builds the same ER diagram as the backend exporter', () => {
  const d = toErDiagram(sampleResult.architecture)
  expect(d.startsWith('erDiagram')).toBe(true)
  expect(d).toContain('owners ||--o{ pets : "owner_id"')
  expect(d).toContain('uuid owner_id FK')
  expect(d).toContain('uuid id PK')
})
