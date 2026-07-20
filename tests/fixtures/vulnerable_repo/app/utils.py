"""Misc helpers. INTENTIONALLY VULNERABLE fixture for Sentinel tests."""
import yaml
import pickle


def load_config(raw):
    # INJECTION/DESERIALIZATION: yaml.load without SafeLoader on untrusted input.
    return yaml.load(raw)


def load_session(blob):
    # DESERIALIZATION: untrusted pickle load leads to arbitrary code execution.
    return pickle.loads(blob)
