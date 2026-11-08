import type { ArchitectOutput } from '../types'

/** Keep in sync with backend/app/exporters/markdown.py (er_diagram). */
export function toErDiagram(arch: ArchitectOutput): string {
  const lines = ['erDiagram']
  for (const t of arch.tables) {
    lines.push(`    ${t.name} {`)
    for (const c of t.columns) {
      const keys = [c.primary_key && 'PK', c.foreign_key && 'FK'].filter(Boolean).join(', ')
      lines.push(`        ${c.type} ${c.name}${keys ? ' ' + keys : ''}`)
    }
    lines.push('    }')
  }
  for (const t of arch.tables) {
    for (const c of t.columns) {
      if (c.foreign_key) lines.push(`    ${c.foreign_key.split('.')[0]} ||--o{ ${t.name} : "${c.name}"`)
    }
  }
  return lines.join('\n')
}
