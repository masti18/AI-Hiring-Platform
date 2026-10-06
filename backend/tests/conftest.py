"""Test fixtures — reset async engine between tests to avoid loop affinity issues."""

import pytest

from app.core.database import engine


@pytest.fixture(autouse=True)
async def _dispose_engine_between_tests():
    yield
    await engine.dispose()
