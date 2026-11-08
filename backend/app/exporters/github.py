import httpx

from app.exporters.markdown import story_body
from app.schemas import PipelineResult


async def create_issues(r: PipelineResult, repo: str, token: str,
                        client: httpx.AsyncClient) -> tuple[list[dict], str | None, int]:
    """One issue per story, sequentially; stop at the first failure and report what was created."""
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    created: list[dict] = []
    for s in r.stories:
        try:
            res = await client.post(f"https://api.github.com/repos/{repo}/issues", headers=headers,
                                    json={"title": f"[{s.id}] {s.title}",
                                          "body": story_body(r, s), "labels": ["ai-generated"]})
        except httpx.HTTPError:
            return created, "Could not reach GitHub.", 502
        if not res.is_success:
            try:
                message = res.json().get("message", "")
            except ValueError:
                message = ""
            # Pass GitHub's 4xx through (bad token, no access, unknown repo); 5xx becomes 502.
            status = res.status_code if 400 <= res.status_code < 500 else 502
            return created, message or f"GitHub returned {res.status_code}.", status
        created.append({"story_id": s.id, "url": res.json()["html_url"]})
    return created, None, 200
