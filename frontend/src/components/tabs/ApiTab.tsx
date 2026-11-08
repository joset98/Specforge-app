import type { Endpoint } from '../../types'

export function ApiTab({ endpoints }: { endpoints: Endpoint[] }) {
  return (
    <div className="table-scroll">
      <table className="data">
        <thead>
          <tr><th>Id</th><th>Method</th><th>Path</th><th>Description</th><th>Body → Response</th><th>Stories</th></tr>
        </thead>
        <tbody>
          {endpoints.map((e) => (
            <tr key={e.id}>
              <td><code className="id">{e.id}</code></td>
              <td><span className={`method m-${e.method.toLowerCase()}`}>{e.method}</span></td>
              <td><code>{e.path}</code></td>
              <td>{e.description}</td>
              <td className="muted">
                {e.request_table ?? '–'} → {e.response_table ? `${e.response_table}${e.response_is_list ? '[]' : ''}` : '–'}
              </td>
              <td><code>{e.story_ids.join(', ')}</code></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
