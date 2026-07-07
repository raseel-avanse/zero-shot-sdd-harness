"""Data-access layer. INTENTIONALLY VULNERABLE fixture for Sentinel tests."""
import os
import sqlite3
import subprocess


def get_user(username):
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    # INJECTION: raw SQL built with string formatting on untrusted input.
    query = "SELECT * FROM users WHERE username = '%s'" % username
    cur.execute(query)
    return cur.fetchone()


def search(term):
    conn = sqlite3.connect("app.db")
    cur = conn.cursor()
    # INJECTION: f-string interpolation directly into SQL.
    cur.execute(f"SELECT * FROM items WHERE name LIKE '%{term}%'")
    return cur.fetchall()


def backup(path):
    # INJECTION (command): user-controlled path passed to a shell command.
    os.system("tar czf backup.tgz " + path)
    subprocess.call("rm -rf /tmp/" + path, shell=True)
