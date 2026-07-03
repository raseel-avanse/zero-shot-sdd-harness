"""API contract tests — no LLM key required (graph not invoked)."""
import io


def test_health(api_client):
    r = api_client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["status"] == "healthy"


def test_upload_csv_returns_profile(api_client):
    csv = b"name,age\nalice,30\nbob,\ncarol,25\n"
    r = api_client.post(
        "/api/datasets",
        files={"file": ("people.csv", io.BytesIO(csv), "text/csv")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    data = body["data"]
    assert "dataset_id" in data
    profile = data["profile"]
    assert profile["row_count"] == 3
    cols = {c["name"]: c for c in profile["columns"]}
    assert cols["age"]["null_count"] == 1
    # a dq flag should name the null column
    assert any("age" in f and "null" in f for f in profile["dq_flags"])


def test_upload_non_csv_rejected(api_client):
    r = api_client.post(
        "/api/datasets",
        files={"file": ("data.json", io.BytesIO(b"{}"), "application/json")},
    )
    assert r.status_code == 400
    body = r.json()
    assert body["ok"] is False
    assert body["error"]["code"] == "UNSUPPORTED_TYPE"


def test_upload_bad_csv_parse_failed(api_client):
    # Empty file → pandas EmptyDataError
    r = api_client.post(
        "/api/datasets",
        files={"file": ("x.csv", io.BytesIO(b""), "text/csv")},
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "PARSE_FAILED"


def test_ask_empty_question_rejected(api_client):
    # First upload so the dataset exists
    csv = b"a,b\n1,2\n"
    up = api_client.post(
        "/api/datasets", files={"file": ("x.csv", io.BytesIO(csv), "text/csv")}
    )
    dataset_id = up.json()["data"]["dataset_id"]
    r = api_client.post(f"/api/datasets/{dataset_id}/ask", json={"question": "  "})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "EMPTY_QUESTION"


def test_ask_unknown_dataset_404(api_client):
    r = api_client.post("/api/datasets/does-not-exist/ask", json={"question": "hi"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "DATASET_NOT_FOUND"
