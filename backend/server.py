"""Supervisor entrypoint — exposes the FastAPI ``app`` from ``main``.

Emergent's supervisor runs ``uvicorn server:app``; the actual application
factory still lives in ``main.py`` so local dev (``uvicorn main:app``) and
Railway deploy keep working unchanged.
"""
from main import app  # noqa: F401  (re-exported for uvicorn)
