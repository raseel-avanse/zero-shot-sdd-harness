"""DB layer tests — no LLM key required."""
from sqlalchemy.orm import Session
from db.models import RunRow, DealRow


def test_run_row_roundtrip(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(query_type="name", query_text="Sony WH-1000XM5")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        fetched = s.get(RunRow, run_id)
        assert fetched is not None
        assert fetched.query_text == "Sony WH-1000XM5"
        assert fetched.query_type == "name"
        assert fetched.status == "pending"
        assert fetched.prompt_tokens == 0
        assert fetched.cost_inr is None


def test_run_progress_and_cost_update(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(query_text="test")
        s.add(run)
        s.commit()
        run_id = run.id

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        run.status = "completed"
        run.progress_step = "done"
        run.prompt_tokens = 5000
        run.completion_tokens = 800
        run.cost_inr = 8.7
        s.commit()

    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.status == "completed"
        assert run.progress_step == "done"
        assert run.cost_inr == 8.7


def test_deal_rows_linked_to_run(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(query_text="headphones")
        s.add(run)
        s.commit()
        run_id = run.id
        for i in range(1, 4):
            s.add(
                DealRow(
                    run_id=run_id,
                    rank=i,
                    site=f"Site{i}",
                    price_inr=1000.0 * i,
                    reason="good value",
                )
            )
        s.commit()

    with Session(_isolated_db) as s:
        deals = (
            s.query(DealRow)
            .filter(DealRow.run_id == run_id)
            .order_by(DealRow.rank)
            .all()
        )
        assert len(deals) == 3
        assert [d.rank for d in deals] == [1, 2, 3]
        assert deals[0].site == "Site1"
