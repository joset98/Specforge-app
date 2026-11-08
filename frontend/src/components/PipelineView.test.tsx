import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'
import { PipelineView } from './PipelineView'

test('shows a retrying agent and its detail', () => {
  render(
    <PipelineView
      stages={{
        product_owner: { agent: 'product_owner', status: 'done', detail: '' },
        architect: { agent: 'architect', status: 'retry', detail: '2 problemas: FK_BROKEN' },
      }}
      log={['Validator: 2 problemas: FK_BROKEN → re-running Architect']}
      running
    />,
  )
  const architect = screen.getByRole('listitem', { name: /architect/i })
  expect(architect).toHaveAttribute('data-status', 'retry')
  expect(architect).toHaveTextContent('Retrying')
  expect(screen.getByText(/re-running Architect/)).toBeInTheDocument()
  expect(screen.getByRole('listitem', { name: /product owner/i })).toHaveAttribute('data-status', 'done')
  expect(screen.getByRole('listitem', { name: /qa/i })).toHaveAttribute('data-status', 'idle')
})
