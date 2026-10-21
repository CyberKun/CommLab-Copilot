"""Vercel serverless entry point for the FastAPI backend.

Vercel's Python runtime looks for an `app` variable that is a WSGI/ASGI
application.  FastAPI is ASGI, which Vercel supports natively via the
@vercel/python builder.
"""

import os
import sys

# Ensure the backend package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

# Use /tmp for writable storage on Vercel's read-only filesystem
os.environ.setdefault("ARTIFACT_ROOT", "/tmp/artifacts")

from commlab.http import create_app  # noqa: E402

app = create_app()
