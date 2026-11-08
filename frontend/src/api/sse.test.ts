import { expect, test } from 'vitest'
import { parseSSE } from './sse'

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder()
  return new ReadableStream({
    start(c) { chunks.forEach((ch) => c.enqueue(enc.encode(ch))); c.close() },
  })
}

test('yields events split across chunks, including inside the JSON', async () => {
  const raw = 'event: stage\ndata: {"agent":"qa","status":"started","detail":"ñ"}\n\n' +
    'event: error\ndata: {"code":"auth","message":"x"}\n\n'
  const events = []
  for await (const e of parseSSE(streamOf([raw.slice(0, 20), raw.slice(20, 50), raw.slice(50)]))) {
    events.push(e)
  }
  expect(events).toEqual([
    { event: 'stage', data: { agent: 'qa', status: 'started', detail: 'ñ' } },
    { event: 'error', data: { code: 'auth', message: 'x' } },
  ])
})

test('handles CRLF line endings and multiple events in one chunk', async () => {
  const raw = 'event: a\r\ndata: {"n":1}\r\n\r\nevent: b\r\ndata: {"n":2}\r\n\r\n'
  const events = []
  for await (const e of parseSSE(streamOf([raw]))) events.push(e)
  expect(events.map((e) => e.event)).toEqual(['a', 'b'])
})
