import { Check, Loader2, RotateCcw } from 'lucide-react'
import { STAGE_LABELS } from '../lib/labels'
import type { Stage, StageData } from '../types'

const STATUS_LABEL = { idle: 'Waiting', started: 'Working', retry: 'Retrying', done: 'Done' }

interface Props {
  stages: Partial<Record<Stage, StageData>>
  log: string[]
  running: boolean
}

export function PipelineView({ stages, log, running }: Props) {
  const order: Stage[] = ['product_owner', 'architect', 'qa', 'validator']
  return (
    <section className="pipeline" aria-label="Agent pipeline">
      <ol className="pipeline-steps">
        {order.map((stage) => {
          const status = stages[stage]?.status ?? 'idle'
          const active = running && (status === 'started' || status === 'retry')
          return (
            <li key={stage} aria-label={STAGE_LABELS[stage]} data-status={status}
                data-active={active || undefined} className="pipeline-step">
              <span className="pipeline-dot" aria-hidden>
                {status === 'done' && <Check size={14} strokeWidth={2.5} />}
                {active && status === 'started' && <Loader2 size={14} className="spin" />}
                {active && status === 'retry' && <RotateCcw size={14} />}
              </span>
              <span className="pipeline-name">{STAGE_LABELS[stage]}</span>
              <span className="pipeline-status">{STATUS_LABEL[status]}</span>
            </li>
          )
        })}
      </ol>
      {log.length > 0 && (
        <ul className="pipeline-log" aria-live="polite">
          {log.map((line, i) => <li key={i}>{line}</li>)}
        </ul>
      )}
    </section>
  )
}
