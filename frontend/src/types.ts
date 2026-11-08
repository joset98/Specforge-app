// Mirrors backend/app/schemas.py
export type Section = 'product_owner' | 'architect' | 'qa'
export type Stage = Section | 'validator'
export type ColumnType =
  | 'uuid' | 'text' | 'integer' | 'bigint' | 'decimal' | 'boolean' | 'date' | 'timestamp' | 'json'

export interface RunInput { text: string; team_context: string }
export interface Story {
  id: string; title: string; as_a: string; i_want: string; so_that: string
  gherkin: string; priority: 'alta' | 'media' | 'baja'
}
export interface Column {
  name: string; type: ColumnType; primary_key: boolean; foreign_key: string | null; nullable: boolean
}
export interface Table { name: string; columns: Column[] }
export interface Endpoint {
  id: string; method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'; path: string
  description: string; story_ids: string[]
  request_table: string | null; response_table: string | null; response_is_list: boolean
}
export interface ArchitectOutput { tables: Table[]; endpoints: Endpoint[] }
export interface TestCase {
  id: string; title: string; endpoint_id: string; story_id: string
  steps: string[]; expected: string; type: 'happy_path' | 'edge_case' | 'error'
}
export interface Issue { code: string; owner: Section; message: string }
export interface ValidationReport { passed: boolean; issues: Issue[]; rounds: number }
export interface PipelineResult {
  input: RunInput; stories: Story[]; architecture: ArchitectOutput
  tests: TestCase[]; validation: ValidationReport
}

export interface StageData { agent: Stage; status: 'started' | 'done' | 'retry'; detail: string }
export type PipelineEvent =
  | { event: 'stage'; data: StageData }
  | { event: 'validation'; data: ValidationReport }
  | { event: 'result'; data: PipelineResult }
  | { event: 'error'; data: { code: string; message: string } }

export type ExportFormat = 'markdown' | 'json' | 'jira-csv' | 'openapi' | 'sql'
