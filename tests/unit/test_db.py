"""DB layer tests — no LLM key required."""
from sqlalchemy.orm import Session
from db.models import RunRow


def test_run_row_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(dataset_id="ds1", question="how many rows?")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        fetched = s.get(RunRow, run_id)
        assert fetched is not None
        assert isinstance(fetched.id, int)
        assert fetched.dataset_id == "ds1"
        assert fetched.question == "how many rows?"
        assert fetched.status == "pending"
        assert fetched.answer is None
        assert fetched.attempts == 0
        assert fetched.used_fallback is False


def test_run_row_json_columns(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(
            dataset_id="ds1",
            question="q",
            chart_spec={"type": "bar", "series": []},
            assumptions=["a", "b"],
        )
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        fetched = s.get(RunRow, run_id)
        assert fetched.chart_spec == {"type": "bar", "series": []}
        assert fetched.assumptions == ["a", "b"]


def test_run_row_status_update(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(dataset_id="ds1", question="q")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        run.status = "completed"
        run.answer = "42"
        run.token_total = 100
        s.commit()

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.status == "completed"
        assert run.answer == "42"
        assert run.token_total == 100


def test_multiple_runs_independent(_isolated_db):
    with Session(_isolated_db) as s:
        for i in range(3):
            s.add(RunRow(dataset_id="ds1", question=f"q{i}"))
        s.commit()
        ids = [r.id for r in s.query(RunRow).all()]

    assert len(ids) == 3
    assert len(set(ids)) == 3
