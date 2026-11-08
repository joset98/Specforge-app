import csv
import io

from app.exporters.markdown import story_body
from app.schemas import PipelineResult

PRIORITY = {"alta": "High", "media": "Medium", "baja": "Low"}


def to_jira_csv(r: PipelineResult) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
    w.writerow(["Summary", "Description", "Issue Type", "Priority", "Labels"])
    for s in r.stories:
        w.writerow([f"[{s.id}] {s.title}", story_body(r, s), "Story", PRIORITY[s.priority],
                    "ai-generated"])
    return buf.getvalue()
