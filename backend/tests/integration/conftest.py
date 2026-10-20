import os

import pytest
from sqlalchemy import make_url

from app.db.session import normalize_async_database_url


@pytest.fixture
def postgres_url():
    url = normalize_async_database_url(os.environ["SCHEMA_TEST_POSTGRES_URL"])
    assert (make_url(url).database or "").startswith("test_"), "Use a disposable test_* database"
    assert make_url(url).get_backend_name() == "postgresql"
    return url
