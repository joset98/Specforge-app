import csv
import io

from app.exporters.markdown import story_body
from app.schemas import PipelineResult

PRIORITY = {"alta": "High", "media": "Medium", "baja": "Low"}


def _safe(value: str) -> str:
    """Spreadsheet apps run cells starting with these as formulas."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


def to_jira_csv(r: PipelineResult) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w.writerow(["Summary", "Description", "Issue Type", "Priority", "Labels"])
    for s in r.stories:
        w.writerow([_safe(f"[{s.id}] {s.title}"), _safe(story_body(r, s)), "Story",
                    PRIORITY[s.priority], "ai-generated"])
    return buf.getvalue()
