import importlib

from fastapi import FastAPI


def test_asgi_target_importable():
    # The import target used by `python -m src` (src/__main__.py) must resolve
    # and expose a FastAPI `app` with no PYTHONPATH workaround.
    module = importlib.import_module("src.api")
    assert isinstance(module.app, FastAPI)
