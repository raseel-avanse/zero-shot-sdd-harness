"""resume_run flips a paused run back to running and re-launches the graph."""
from unittest.mock import MagicMock, patch

from sqlalchemy.orm import Session

from graph import runner
from db.models import RunRow


def test_resume_run_relaunches_with_answer(_isolated_db):
    with Session(_isolated_db) as s:
        run = RunRow(query_type="name", query_text="good phone", status="needs_input",
                     clarifying_question="Budget?")
        s.add(run)
        s.commit()
        run_id = run.id

    fake_exec = MagicMock()
    with patch.object(runner, "_executor", fake_exec):
        runner.resume_run(run_id, "Under 20k")

    # Row flipped back to running, question cleared.
    with Session(_isolated_db) as s:
        run = s.get(RunRow, run_id)
        assert run.status == "running"
        assert run.progress_step == "queued"
        assert run.clarifying_question is None

    # _execute submitted with the original query + the clarify answer.
    fake_exec.submit.assert_called_once()
    args = fake_exec.submit.call_args.args
    assert args[0] is runner._execute
    assert args[1] == run_id           # run_id
    assert args[2] == "name"           # query_type
    assert args[3] == "good phone"     # query_text
    assert args[4] == "Under 20k"      # clarify_answer


def test_resume_run_unknown_id_is_noop(_isolated_db):
    fake_exec = MagicMock()
    with patch.object(runner, "_executor", fake_exec):
        runner.resume_run("does-not-exist", "x")
    fake_exec.submit.assert_not_called()
