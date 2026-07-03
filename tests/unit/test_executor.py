"""Local pandas executor — captures results and tracebacks without raising."""
import pandas as pd

from graph.executor import execute_pandas


def test_executes_and_captures_result():
    df = pd.DataFrame({"x": [1, 2, 3, 4]})
    res = execute_pandas("result = df['x'].sum()", df)
    assert res.ok is True
    assert res.traceback is None
    assert res.result_repr == "10"


def test_bad_column_captures_traceback_no_raise():
    df = pd.DataFrame({"x": [1, 2]})
    res = execute_pandas("result = df['nope'].sum()", df)
    assert res.ok is False
    assert res.result_repr is None
    assert "KeyError" in res.traceback


def test_missing_result_variable_is_error():
    df = pd.DataFrame({"x": [1]})
    res = execute_pandas("df['x'].sum()", df)
    assert res.ok is False
    assert "result" in res.traceback


def test_does_not_mutate_original_df():
    df = pd.DataFrame({"x": [1, 2]})
    execute_pandas("df['x'] = 0\nresult = df['x'].sum()", df)
    # original untouched (executor copies)
    assert df["x"].tolist() == [1, 2]


def test_series_result_repr():
    df = pd.DataFrame({"g": ["a", "a", "b"], "v": [1, 2, 3]})
    res = execute_pandas("result = df.groupby('g')['v'].sum()", df)
    assert res.ok is True
    assert "a" in res.result_repr and "b" in res.result_repr
