"""API contract tests — no LLM key required, graph is not invoked."""
from unittest.mock import patch


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    assert r.json()["data"]["status"] == "ok"


def test_post_runs_returns_running_and_run_id(api_client):
    with patch("api.runs.start_run", return_value="run-123") as mock_start:
        r = api_client.post(
            "/runs", json={"query_type": "name", "query_text": "Sony WH-1000XM5"}
        )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["run_id"] == "run-123"
    assert data["status"] == "running"
    mock_start.assert_called_once()


def test_post_runs_defaults_query_type_to_name(api_client):
    with patch("api.runs.start_run", return_value="rid") as mock_start:
        r = api_client.post("/runs", json={"query_text": "wireless earbuds"})
    assert r.status_code == 200
    # query_type defaults to "name"
    assert mock_start.call_args.args[0] == "name"


def test_post_runs_empty_query_text_is_400_validation(api_client):
    r = api_client.post("/runs", json={"query_text": "   "})
    assert r.status_code == 400
    assert r.json()["detail"]["code"] == "VALIDATION"


def test_post_runs_missing_query_text_is_422(api_client):
    r = api_client.post("/runs", json={})
    assert r.status_code == 422


def test_get_run_not_found_is_404(api_client):
    r = api_client.get("/runs/does-not-exist")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "NOT_FOUND"


def test_get_run_contract_shape(api_client, _isolated_db):
    """GET response exposes the full stable contract incl. P2 fields as null."""
    from sqlalchemy.orm import Session
    from db.models import RunRow, DealRow

    with Session(_isolated_db) as s:
        run = RunRow(
            query_text="Sony WH-1000XM5",
            status="completed",
            progress_step="done",
            prompt_tokens=5000,
            completion_tokens=800,
            cost_inr=8.7,
        )
        s.add(run)
        s.commit()
        run_id = run.id
        s.add(
            DealRow(
                run_id=run_id,
                rank=1,
                site="Amazon.in",
                price_inr=24990.0,
                reason="Lowest verified price",
            )
        )
        s.commit()

    r = api_client.get(f"/runs/{run_id}")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["status"] == "completed"
    assert data["progress_step"] == "done"
    assert data["cost_inr"] == 8.7
    assert data["prompt_tokens"] == 5000
    # P2 fields present and null for a stable frontend contract
    assert data["clarifying_question"] is None
    assert len(data["deals"]) == 1
    deal = data["deals"][0]
    assert deal["site"] == "Amazon.in"
    assert deal["price_inr"] == 24990.0
    assert deal["quality_label"] is None
    assert deal["quality_reason"] is None
