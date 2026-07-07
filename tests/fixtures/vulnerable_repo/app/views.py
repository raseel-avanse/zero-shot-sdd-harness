"""HTTP handlers. INTENTIONALLY VULNERABLE fixture for Sentinel tests."""
from app.db import get_user


def admin_dashboard(request):
    # BROKEN_AUTH: no authorization check — any caller reaches the admin view.
    users = get_user(request.args.get("username"))
    return {"admin": True, "users": users}


def delete_account(request, user_id):
    # BROKEN_AUTH: missing ownership/role check before a destructive action.
    return {"deleted": user_id}


def login(request):
    username = request.form.get("username")
    password = request.form.get("password")
    # BROKEN_AUTH: plaintext password comparison, no rate limiting.
    if password == "admin":
        return {"token": "static-admin-token"}
    return {"error": "bad creds"}
