"""Upgrade both existing branches and verify preserved accounts over real HTTP."""

import os

import pytest

from tests.auth_upgrade_probe import STARTS, run_scenario

pytestmark = pytest.mark.skipif(
    not os.getenv("SCHEMA_TEST_POSTGRES_URL"), reason="Requires disposable PostgreSQL"
)


@pytest.mark.parametrize("start", STARTS)
def test_existing_auth_and_release_histories_upgrade_without_losing_login(postgres_url, start):
    result = run_scenario(postgres_url, start)
    assert result["schemaMatchesModels"] and result["oldOtpAccessRefreshAndPasswordHttpPassed"]
