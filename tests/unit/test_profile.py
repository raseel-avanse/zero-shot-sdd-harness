"""Profiling correctness — pure pandas, no LLM."""
import pandas as pd

from domain.profile import build_profile, build_sample


def test_row_count_and_dtypes():
    df = pd.DataFrame({"age": [1, 2, 3], "name": ["a", "b", "c"]})
    p = build_profile(df)
    assert p["row_count"] == 3
    cols = {c["name"]: c for c in p["columns"]}
    assert cols["age"]["dtype"].startswith("int")
    assert cols["age"]["non_null"] == 3
    assert cols["age"]["null_count"] == 0
    assert cols["name"]["dtype"] in ("object", "str")


def test_null_flag_names_column():
    df = pd.DataFrame({"age": [1, None, 3, None]})
    p = build_profile(df)
    cols = {c["name"]: c for c in p["columns"]}
    assert cols["age"]["null_count"] == 2
    assert any("age" in f and "null" in f for f in p["dq_flags"])


def test_constant_and_duplicate_flags():
    df = pd.DataFrame({"k": [1, 1, 1], "v": [9, 9, 9]})
    p = build_profile(df)
    joined = " ".join(p["dq_flags"])
    assert "constant" in joined
    assert "duplicate" in joined


def test_sample_values_are_json_safe():
    df = pd.DataFrame({"x": [1, 2, 3]})
    p = build_profile(df)
    sv = p["columns"][0]["sample_values"]
    assert all(isinstance(v, (int, float, str, type(None))) for v in sv)


def test_build_sample_mentions_shape():
    df = pd.DataFrame({"x": [1, 2], "y": [3, 4]})
    s = build_sample(df)
    assert "2 rows" in s
