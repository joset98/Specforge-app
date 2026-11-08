import pytest
from pydantic import ValidationError

from app.schemas import Column, Endpoint, PipelineResult, RefineRequest, Story, TestCase


def test_ids_are_normalized():
    s = Story(id=" us-1 ", title="t", as_a="a", i_want="b", so_that="c",
              gherkin="Escenario: x\nDado a\nCuando b\nEntonces c", priority="alta")
    assert s.id == "US-1"
    ep = Endpoint(id="ep-1", method="GET", path="/x", description="d", story_ids=["us-1 "])
    assert ep.story_ids == ["US-1"]
    tc = TestCase(id="tc-1", title="t", endpoint_id="ep-1", story_id="us-1",
                  steps=["s"], expected="e", type="happy_path")
    assert (tc.endpoint_id, tc.story_id) == ("EP-1", "US-1")


def test_column_type_is_closed_set():
    with pytest.raises(ValidationError):
        Column(name="x", type="varchar(255)")


def test_sample_result_roundtrips(sample_result):
    assert PipelineResult.model_validate_json(sample_result.model_dump_json()) == sample_result


def test_refine_rejects_unknown_section(sample_result):
    with pytest.raises(ValidationError):
        RefineRequest(result=sample_result, section="hacker", feedback="x")


@pytest.mark.parametrize("repo", ["../..", "owner/..", "./x", "a/b/c"])
def test_github_repo_rejects_dot_names(sample_result, repo):
    from app.schemas import GithubExportRequest

    with pytest.raises(ValidationError):
        GithubExportRequest(result=sample_result, repo=repo)


def test_github_repo_accepts_dotted_names(sample_result):
    from app.schemas import GithubExportRequest

    assert GithubExportRequest(result=sample_result, repo="my.org/repo.js").repo == "my.org/repo.js"
