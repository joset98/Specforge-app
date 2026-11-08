import type { LlmAuth } from '../api/client'

interface Props {
  auth: LlmAuth
  onChange: (auth: LlmAuth) => void
}

export function KeyPanel({ auth, onChange }: Props) {
  const provider = auth?.provider ?? 'claude'
  return (
    <div className="key-panel">
      <p className="hint">
        Your key is sent only with your own requests and is never stored. Reloading the page forgets it.
      </p>
      <div className="row">
        <label className="field narrow">
          <span>Provider</span>
          <select
            value={provider}
            onChange={(e) =>
              onChange({ provider: e.target.value as 'claude' | 'openai', key: auth?.key ?? '' })}
          >
            <option value="claude">Claude</option>
            <option value="openai">OpenAI</option>
          </select>
        </label>
        <label className="field">
          <span>API key</span>
          <input
            type="password" autoComplete="off" spellCheck={false}
            placeholder={provider === 'claude' ? 'sk-ant-…' : 'sk-…'}
            value={auth?.key ?? ''}
            onChange={(e) => onChange(e.target.value ? { provider, key: e.target.value } : null)}
          />
        </label>
      </div>
    </div>
  )
}
