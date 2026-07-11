"""POST /runs/{id}/answer resume flow + query-type validation — no LLM key needed."""
from unittest.mock import patch


def _make_run(engine, status="needs_input", **extra):
    from sqlalchemy.orm import Session
    from db.models import RunRow
    with Session(engine) as s:
        run = RunRow(query_type="name", query_text="good phone", status=status,
                     clarifying_question="What is your budget?", **extra)
        s.add(run)
        s.commit()
        return run.id


# --- query-type validation on POST /runs ------------------------------------

def test_post_runs_accepts_url(api_client):
    with patch("api.runs.start_run", return_value="rid") as m:
        r = api_client.post("/runs", json={"query_type": "url",
                                           "query_text": "https://www.amazon.in/dp/B09XS7JWHH"})
    assert r.status_code == 200
    assert m.call_args.args[0] == "url"


def test_post_runs_accepts_category(api_client):
    with patch("api.runs.start_run", return_value="rid") as m:
        r = api_client.post("/runs", json={"query_type": "category",
                                           "query_text": "gaming laptops under 80k"})
    assert r.status_code == 200
    assert m.call_args.args[0] == "category"


def test_post_runs_url_without_scheme_is_400(api_client):
    r = api_client.post("/runs", json={"query_type": "url", "query_text": "just some words"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "VALIDATION"


def test_post_runs_unknown_query_type_is_400(api_client):
    r = api_client.post("/runs", json={"query_type": "voice", "query_text": "hi"})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "VALIDATION"


# --- POST /runs/{id}/answer -------------------------------------------------

def test_answer_resumes_paused_run(api_client, _isolated_db):
    run_id = _make_run(_isolated_db, status="needs_input")
    with patch("api.runs.resume_run") as mock_resume:
        r = api_client.post(f"/runs/{run_id}/answer",
                            json={"answer": "Under 20k, for photography"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["run_id"] == run_id
    assert data["status"] == "running"
    mock_resume.assert_called_once_with(run_id, "Under 20k, for photography")


def test_answer_unknown_run_is_404(api_client):
    with patch("api.runs.resume_run"):
        r = api_client.post("/runs/nope/answer", json={"answer": "x"})
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_answer_when_not_needs_input_is_409(api_client, _isolated_db):
    run_id = _make_run(_isolated_db, status="running")
    with patch("api.runs.resume_run") as mock_resume:
        r = api_client.post(f"/runs/{run_id}/answer", json={"answer": "x"})
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "CONFLICT"
    mock_resume.assert_not_called()


def test_answer_empty_is_400(api_client, _isolated_db):
    run_id = _make_run(_isolated_db, status="needs_input")
    r = api_client.post(f"/runs/{run_id}/answer", json={"answer": "   "})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "VALIDATION"


def test_get_run_needs_input_exposes_question(api_client, _isolated_db):
    run_id = _make_run(_isolated_db, status="needs_input")
    r = api_client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "needs_input"
    assert data["clarifying_question"] == "What is your budget?"
    assert data["deals"] == []
