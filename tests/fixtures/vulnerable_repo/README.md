# Vulnerable Sample App (test fixture)

This is an INTENTIONALLY INSECURE application used only by Sentinel's
integration tests. Do not deploy. It plants issues across four classes:

- injection (SQL string-formatting + shell command on user input) — `app/db.py`
- secrets/misconfig (hardcoded keys/password + DEBUG=True) — `app/config.py`
- broken auth (missing authz checks) — `app/views.py`
- vulnerable deps (CVE-pinned versions) — `requirements.txt`
