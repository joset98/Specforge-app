import type { PipelineResult } from './types'

// Same shape as backend/tests/conftest.py sample_result (trimmed).
export const sampleResult: PipelineResult = {
  input: { text: 'App de reservas para veterinaria', team_context: 'PostgreSQL' },
  stories: [
    { id: 'US-1', title: 'Registrar mascota', as_a: 'dueño', i_want: 'registrar mi mascota',
      so_that: 'pueda reservar citas', priority: 'alta',
      gherkin: 'Característica: Reservas\n  Escenario: reservar\n    Dado un dueño\n    Cuando reserva\n    Entonces queda confirmada' },
  ],
  architecture: {
    tables: [
      { name: 'owners', columns: [
        { name: 'id', type: 'uuid', primary_key: true, foreign_key: null, nullable: false },
        { name: 'name', type: 'text', primary_key: false, foreign_key: null, nullable: false },
      ] },
      { name: 'pets', columns: [
        { name: 'id', type: 'uuid', primary_key: true, foreign_key: null, nullable: false },
        { name: 'owner_id', type: 'uuid', primary_key: false, foreign_key: 'owners.id', nullable: false },
      ] },
    ],
    endpoints: [
      { id: 'EP-1', method: 'POST', path: '/owners/{ownerId}/pets', description: 'Registra una mascota',
        story_ids: ['US-1'], request_table: 'pets', response_table: 'pets', response_is_list: false },
    ],
  },
  tests: [
    { id: 'TC-1', title: 'Registro válido', endpoint_id: 'EP-1', story_id: 'US-1',
      steps: ['Enviar POST'], expected: '201', type: 'happy_path' },
  ],
  validation: { passed: true, issues: [], rounds: 0 },
}
