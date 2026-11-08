import { Wand2 } from 'lucide-react'
import { useState } from 'react'
import type { Section } from '../types'

interface Props {
  section: Section
  disabled: boolean
  placeholder: string
  onRefine: (section: Section, feedback: string) => void
}

export function RefineBox({ section, disabled, placeholder, onRefine }: Props) {
  const [feedback, setFeedback] = useState('')
  return (
    <form
      className="refine"
      onSubmit={(e) => {
        e.preventDefault()
        if (feedback.trim()) {
          onRefine(section, feedback.trim())
          setFeedback('')
        }
      }}
    >
      <label className="field">
        <span>Refine this section</span>
        <textarea rows={2} maxLength={2000} value={feedback} placeholder={placeholder}
                  onChange={(e) => setFeedback(e.target.value)} />
      </label>
      <button type="submit" className="btn" disabled={disabled || !feedback.trim()}>
        <Wand2 size={16} aria-hidden /> Refine
      </button>
    </form>
  )
}
