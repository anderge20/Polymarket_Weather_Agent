"""Shared pytest fixtures for the Phase 2A data-layer tests.

These tests were AUTHORED WITHOUT PYTHON EXECUTION. Run them on a machine with
Python + the pipeline requirements installed (see PHASE_2A_DATA_MODEL.md):

    pip install -r requirements-pipeline.txt
    pytest -q

Nothing in this suite is "validated" until you run it against DuckDB.
"""
from __future__ import annotations

import os
import sys

# Make `import weather_agent...` work when running pytest from the repo root,
# without installing the package (src/ layout).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
# also make test-local helper modules (e.g. gamma_fixtures) importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest  # noqa: E402

from weather_agent import database  # noqa: E402


@pytest.fixture
def con():
    """A fresh, fully-initialised in-memory DuckDB connection per test."""
    c = database.init_db(database.connect(":memory:"))
    try:
        yield c
    finally:
        c.close()
