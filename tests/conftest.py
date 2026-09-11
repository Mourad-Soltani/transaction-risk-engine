"""Shared pytest fixtures.

Author: Mourad.Soltani
"""

import pytest

from backend.app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c
