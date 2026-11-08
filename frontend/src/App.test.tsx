import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import App from './App'
import { sampleResult } from './fixtures'

vi.mock('./api/client', async (orig) => ({
  ...(await orig<typeof import('./api/client')>()),
  getQuota: vi.fn(async () => ({ remaining: 3, limit: 3 })),
  startRun: vi.fn(async function* () {
    yield { event: 'error', data: { code: 'upstream', message: 'Provider down' } }
  }),
}))

test('after importing JSON, a later error does not offer to retry the old run', async () => {
  const { container } = render(<App />)
  fireEvent.click(screen.getByRole('button', { name: 'Vet clinic bookings' }))
  expect(await screen.findByText('Provider down')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()

  const importInput = container.querySelector('input[accept=".json,application/json"]') as HTMLInputElement
  const good = new File([JSON.stringify(sampleResult)], 'r.json', { type: 'application/json' })
  fireEvent.change(importInput, { target: { files: [good] } })
  expect(await screen.findByRole('tab', { name: /Stories/ })).toBeInTheDocument()

  const bad = new File(['{}'], 'bad.json', { type: 'application/json' })
  fireEvent.change(importInput, { target: { files: [bad] } })
  expect(await screen.findByText('That file is not a Specforge JSON export.')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
})
