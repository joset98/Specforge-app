import pytest

from app.validator import validate


def run(r):
    return validate(r.stories, r.architecture, r.tests)


def codes(issues):
    return [(i.code, i.owner) for i in issues]


def test_sample_result_has_no_issues(sample_result):
    assert run(sample_result) == []


def test_story_without_endpoint(sample_result):
    r = sample_result.model_copy(deep=True)
    r.architecture.endpoints[0].story_ids = ["US-2"]
    assert codes(run(r)) == [("STORY_WITHOUT_ENDPOINT", "architect")]
    assert "US-1" in run(r)[0].message


def test_endpoint_unknown_story(sample_result):
    r = sample_result.model_copy(deep=True)
    r.architecture.endpoints[0].story_ids = ["US-1", "US-9"]
    assert codes(run(r)) == [("ENDPOINT_UNKNOWN_STORY", "architect")]


@pytest.mark.parametrize("field", ["request_table", "response_table"])
def test_endpoint_unknown_table(sample_result, field):
    r = sample_result.model_copy(deep=True)
    setattr(r.architecture.endpoints[0], field, "ghosts")
    assert codes(run(r)) == [("ENDPOINT_UNKNOWN_TABLE", "architect")]


def test_endpoint_without_test(sample_result):
    r = sample_result.model_copy(deep=True)
    r.tests = r.tests[:2]
    assert codes(run(r)) == [("ENDPOINT_WITHOUT_TEST", "qa")]


@pytest.mark.parametrize("field,value", [("endpoint_id", "EP-9"), ("story_id", "US-9")])
def test_test_unknown_ref(sample_result, field, value):
    r = sample_result.model_copy(deep=True)
    r.tests.append(r.tests[0].model_copy(update={"id": "TC-9", field: value}))
    assert codes(run(r)) == [("TEST_UNKNOWN_REF", "qa")]


@pytest.mark.parametrize("fk", ["ghosts.id", "owners.nope", "owners"])
def test_fk_broken(sample_result, fk):
    r = sample_result.model_copy(deep=True)
    r.architecture.tables[1].columns[1].foreign_key = fk
    assert codes(run(r)) == [("FK_BROKEN", "architect")]


def test_table_without_pk(sample_result):
    r = sample_result.model_copy(deep=True)
    r.architecture.tables[0].columns[0].primary_key = False
    assert codes(run(r)) == [("TABLE_WITHOUT_PK", "architect")]


@pytest.mark.parametrize("which,owner", [
    ("stories", "product_owner"), ("endpoints", "architect"), ("tests", "qa"),
])
def test_duplicate_id(sample_result, which, owner):
    r = sample_result.model_copy(deep=True)
    if which == "stories":
        r.stories[1].id = "US-1"
        r.architecture.endpoints[1].story_ids = ["US-1"]
        r.architecture.endpoints[2].story_ids = ["US-1"]
        for t in r.tests:
            t.story_id = "US-1"
    elif which == "endpoints":
        r.architecture.endpoints[2].id = "EP-2"
        r.tests[2].endpoint_id = "EP-2"
    else:
        r.tests[2].id = "TC-2"
    assert codes(run(r)) == [("DUPLICATE_ID", owner)]


@pytest.mark.parametrize("keyword", ["Escenario", "Dado", "Cuando", "Entonces"])
def test_gherkin_invalid(sample_result, keyword):
    r = sample_result.model_copy(deep=True)
    r.stories[0].gherkin = r.stories[0].gherkin.replace(keyword, "X")
    assert codes(run(r)) == [("GHERKIN_INVALID", "product_owner")]


def test_duplicate_route(sample_result):
    r = sample_result.model_copy(deep=True)
    r.architecture.endpoints[2].path = "/owners/{ownerId}/pets"
    assert codes(run(r)) == [("DUPLICATE_ROUTE", "architect")]
