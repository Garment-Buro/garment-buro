"""Bank edits compare the confirmed version before touching encrypted data."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import update

from app.modules.partners.models import PartnerProfile
from app.modules.partners.schemas import PartnerRequisitesRequest
from app.modules.partners.service import PartnerRequisitesVersionConflictError
from tests.contract.test_partner_owner_landings import owners as owners
from tests.contract.test_partner_owner_landings import postgres_owners as postgres_owners

PATH = "/api/partner/requisites"
BANK = {
    "entity_type": "self_employed",
    "recipient_name": "Тестовый получатель",
    "tax_id": "123456789012",
    "kpp": None,
    "bank_name": "Тестовый банк",
    "bic": "044525225",
    "correspondent_account": "30101810400000000225",
    "settlement_account": "40802810900000000001",
}


def write(client, token, version, name="Тестовый получатель"):
    return client.put(
        PATH, headers=token, json={**BANK, "recipient_name": name, "expected_version": version}
    )


def test_confirmed_versions_and_conflicts_do_not_change_encrypted_data(owners):
    client, _, tokens, _, profiles = owners
    assert client.get(PATH, headers=tokens[0]).json() is None
    absent = write(client, tokens[0], 1)
    assert absent.status_code == 409
    assert absent.json() == {"detail": {"code": "requisites_version_conflict"}}
    assert write(client, tokens[0], 0).json()["version"] == 1

    async def stored():
        async with client.app.state.database.session() as session:
            row = await client.app.state.partner_program_service.repository.get_partner_requisites(
                session, partner_id=profiles[0]
            )
            return (
                row.version,
                row.ciphertext,
                row.nonce,
                row.tag,
                row.payload_sha256,
                row.updated_at,
            )

    before = client.portal.call(stored)
    for version in [0, 2]:
        stale = write(client, tokens[0], version, "Старая правка")
        assert stale.status_code == 409 and stale.headers["cache-control"] == "no-store"
        assert stale.json() == {"detail": {"code": "requisites_version_conflict"}}
        assert client.portal.call(stored) == before
    current = write(client, tokens[0], 1, "Актуальная правка")
    assert current.status_code == 200, current.text
    assert current.json()["version"] == 2 and "expected_version" not in current.json()
    assert client.get(PATH, headers=tokens[0]).json() == current.json()
    assert client.get(PATH, headers=tokens[1]).json() is None
    assert (
        client.put(
            PATH, headers=tokens[0], json={**BANK, "expected_version": 2, "partner_id": profiles[1]}
        ).status_code
        == 422
    )

    async def inspect_document():
        service = client.app.state.partner_program_service
        async with client.app.state.database.session() as session:
            row = await service.repository.get_partner_requisites(session, partner_id=profiles[0])
            clear = service._decrypt_requisites(row)
            assert set(clear) == set(BANK) and clear["recipient_name"] == "Актуальная правка"
            assert row.payload_sha256 == service.requisites_codec.digest(clear)

    client.portal.call(inspect_document)


def test_missing_or_inexact_version_is_rejected_and_auth_stays_owner_scoped(owners):
    client, _, tokens, users, profiles = owners
    assert client.put(PATH, json={**BANK, "expected_version": 0}).status_code == 401
    for version in [None, True, -1, 1.5, "0", 2147483648]:
        assert write(client, tokens[0], version).status_code == 422
    assert client.put(PATH, headers=tokens[0], json=BANK).status_code == 422
    assert client.get(PATH, headers=tokens[0]).json() is None

    async def status(value):
        async with client.app.state.database.session() as session:
            await session.execute(
                update(PartnerProfile).where(PartnerProfile.id == profiles[0]).values(status=value)
            )
            await session.commit()

    client.portal.call(status, "invited")
    assert write(client, tokens[0], 0).status_code == 200
    client.portal.call(status, "suspended")
    assert write(client, tokens[0], 1).status_code == 404


@pytest.mark.parametrize("existing", [False, True])
def test_parallel_creates_and_updates_commit_exactly_one_bank_document(postgres_owners, existing):
    client, _, tokens, _, _ = postgres_owners
    version = 0
    if existing:
        assert write(client, tokens[0], 0).status_code == 200
        version = 1
    barrier = Barrier(2)

    def attempt(name):
        barrier.wait(timeout=10)
        return write(client, tokens[0], version, name)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["Первая правка", "Вторая правка"]))
    assert sorted(row.status_code for row in results) == [200, 409]
    winner = next(row.json() for row in results if row.status_code == 200)
    assert winner["version"] == version + 1
    assert client.get(PATH, headers=tokens[0]).json() == winner


def test_waiting_writer_refreshes_bank_version_already_in_its_identity_map(postgres_owners):
    client, _, tokens, users, profiles = postgres_owners
    assert write(client, tokens[0], 0).status_code == 200

    async def scenario():
        service = client.app.state.partner_program_service
        async with client.app.state.database.session() as stale:
            row = await service.repository.get_partner_requisites(stale, partner_id=profiles[0])
            assert row.version == 1
            async with client.app.state.database.session() as other:
                await service.save_requisites(
                    other,
                    user_id=users[0],
                    expected_version=1,
                    payload=PartnerRequisitesRequest(**{**BANK, "recipient_name": "Свежая правка"}),
                )
                await other.commit()
            with pytest.raises(PartnerRequisitesVersionConflictError):
                await service.save_requisites(
                    stale,
                    user_id=users[0],
                    expected_version=1,
                    payload=PartnerRequisitesRequest(
                        **{**BANK, "recipient_name": "Устаревшая правка"}
                    ),
                )
            await stale.rollback()

    client.portal.call(scenario)
    result = client.get(PATH, headers=tokens[0]).json()
    assert result["version"] == 2 and result["recipient_name"] == "Свежая правка"
