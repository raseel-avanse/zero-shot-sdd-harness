"""Pure-pandas dataframe profiling — no LLM tokens consumed.

Produces the profile shape pinned in spec/api.md and
spec/capabilities/upload-and-profile.md.
"""
from __future__ import annotations

import pandas as pd


def _json_safe(value):
    """Coerce a numpy/pandas scalar into a JSON-serialisable Python value."""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (ValueError, TypeError):
            return str(value)
    return value


def build_profile(df: pd.DataFrame) -> dict:
    row_count = int(len(df))
    columns = []
    dq_flags: list[str] = []

    for name in df.columns:
        series = df[name]
        non_null = int(series.notna().sum())
        null_count = int(series.isna().sum())
        sample_values = [
            _json_safe(v) for v in series.dropna().head(3).tolist()
        ]
        columns.append(
            {
                "name": str(name),
                "dtype": str(series.dtype),
                "non_null": non_null,
                "null_count": null_count,
                "sample_values": sample_values,
            }
        )

        # DQ flag: nulls
        if null_count > 0 and row_count > 0:
            pct = round(null_count / row_count * 100)
            dq_flags.append(f"column '{name}' has {null_count} nulls ({pct}%)")

        # DQ flag: constant column
        if non_null > 0 and series.nunique(dropna=True) == 1:
            dq_flags.append(f"column '{name}' is constant (single value)")

        # DQ flag: object column that may be a date
        is_string = series.dtype == object or str(series.dtype).startswith("str")
        if is_string and non_null > 0:
            lowered = str(name).lower()
            if "date" in lowered or "time" in lowered:
                dq_flags.append(
                    f"column '{name}' parsed as string, may be a date"
                )

    # DQ flag: obvious duplicate rows
    if row_count > 0:
        dup_rows = int(df.duplicated().sum())
        if dup_rows > 0:
            dq_flags.append(f"{dup_rows} duplicate rows detected")

    return {"row_count": row_count, "columns": columns, "dq_flags": dq_flags}


def build_sample(df: pd.DataFrame, head_n: int = 5) -> str:
    """Small head + describe string for LLM prompts (keeps tokens low)."""
    parts = [f"Shape: {df.shape[0]} rows x {df.shape[1]} columns"]
    parts.append("Head:")
    parts.append(df.head(head_n).to_string(max_cols=30))
    try:
        parts.append("Describe:")
        parts.append(df.describe(include="all").to_string(max_cols=30))
    except Exception:
        pass
    return "\n".join(parts)
