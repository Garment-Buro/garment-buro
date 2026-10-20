"""Bounded tech-card summaries/source and commands with long immutable history."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import delete, event, select, update

from app.modules.crm.reference_models import (
    CrmGarmentModel,
    CrmReferenceEvent,
    CrmTechCard,
    CrmTechCardCheckpoint,
    CrmTechCardRevision,
)
from app.modules.crm.reference_schemas import CrmTechCardRevisionWrite
from app.modules.crm.reference_service import CrmReferenceService, CrmReferenceVersionConflictError
from app.modules.crm.tech_directory_schemas import TechCardDirectoryQuery, TechCardModelQuery
from app.modules.crm.tech_directory_service import TechDirectoryService
from tests.contract.test_reference_directory import ROOT, all_pages, sort_text
from tests.contract.test_reference_directory import references as references

NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


@pytest.fixture
def tech_records(references):
    client, prefix, models, _, _, users, _ = references

    async def seed():
        async with client.app.state.database.session() as session:
            free = [
                CrmGarmentModel(
                    code=f"{prefix.upper()}-FREE-{i:03}", name=f"{prefix} Свободная {i % 7}"
                )
                for i in range(130)
            ]
            session.add_all(free)
            cards = []
            for index, model_id in enumerate(models):
                card = CrmTechCard(
                    code=f"{prefix.upper()}-CARD-{index:03}",
                    garment_model_id=model_id,
                    latest_revision_number=130 if index == 129 else 1,
                    is_active=index % 3 != 0,
                )
                for number in range(1, card.latest_revision_number + 1):
                    status = (
                        (
                            "archived"
                            if number < 129
                            else "published"
                            if number == 129
                            else "discarded"
                        )
                        if index == 129
                        else ["draft", "published", "archived", "discarded"][index % 4]
                    )
                    published = status in {"published", "archived"}
                    revision = CrmTechCardRevision(
                        revision_number=number,
                        status=status,
                        name_snapshot=f"{prefix} ВЕРСИЯ_%\\"
                        if index == 129 and number == 130
                        else f"{prefix} Версия {number}",
                        description_snapshot="Сохранённая инструкция",
                        created_at=NOW,
                        published_at=NOW if published else None,
                        published_by_user_id=users[0] if published else None,
                    )
                    for position in range(
                        1, (200 if number == 129 else 17 if number == 130 else 3) + 1
                    ):
                        revision.checkpoints.append(
                            CrmTechCardCheckpoint(
                                position=position,
                                stage_code="sewing",
                                role_code="qc",
                                name=f"Операция {position}",
                                description="Не потерять код участка",
                                standard_minutes=Decimal("12.34"),
                                labor_cost=Decimal("3.25"),
                                currency="RUB",
                            )
                        )
                    card.revisions.append(revision)
                cards.append(card)
            session.add_all(cards)
            await session.commit()
            return [card.id for card in cards], [model.id for model in free]

    cards, free_models = client.portal.call(seed)
    try:
        yield references, cards, free_models
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                owned_cards = select(CrmTechCard.id).where(
                    CrmTechCard.garment_model_id.in_([*models, *free_models])
                )
                owned_revisions = select(CrmTechCardRevision.id).where(
                    CrmTechCardRevision.tech_card_id.in_(owned_cards)
                )
                await session.execute(
                    delete(CrmReferenceEvent).where(
                        (
                            (CrmReferenceEvent.entity_type == "tech_card")
                            & CrmReferenceEvent.entity_id.in_(owned_cards)
                        )
                        | (
                            (CrmReferenceEvent.entity_type == "tech_card_revision")
                            & CrmReferenceEvent.entity_id.in_(owned_revisions)
                        )
                    )
                )
                await session.execute(
                    update(CrmTechCardRevision)
                    .where(CrmTechCardRevision.tech_card_id.in_(owned_cards))
                    .values(based_on_revision_id=None)
                )
                await session.execute(
                    delete(CrmTechCardCheckpoint).where(
                        CrmTechCardCheckpoint.tech_card_revision_id.in_(owned_revisions)
                    )
                )
                await session.execute(
                    delete(CrmTechCardRevision).where(
                        CrmTechCardRevision.tech_card_id.in_(owned_cards)
                    )
                )
                await session.execute(delete(CrmTechCard).where(CrmTechCard.id.in_(owned_cards)))
                await session.execute(
                    delete(CrmGarmentModel).where(CrmGarmentModel.id.in_(free_models))
                )
                await session.commit()

        client.portal.call(cleanup)


def test_tech_pages_use_latest_summary_and_scoped_stable_cursors(tech_records):
    (client, prefix, _, _, _, _, _), cards, _ = tech_records
    records = all_pages(client, "tech-cards", {"query": prefix})
    assert {row["id"] for row in records} == set(cards)
    assert all("revisions" not in row and "checkpoints" not in row for row in records)
    long = next(row for row in records if row["id"] == cards[-1])
    assert long["latest_revision_number"] == 130 and long["checkpoint_count"] == 17
    assert long["latest_revision_status"] == "discarded" and long["draft_revision_number"] is None
    for sort in ["model:asc", "code:asc", "revision:asc", "revision:desc"]:
        rows = all_pages(client, "tech-cards", {"query": prefix, "sort": sort})
        field = {"model:asc": "garment_model_name", "code:asc": "code"}.get(
            sort, "latest_revision_number"
        )
        assert rows == sorted(
            records,
            key=lambda row: (
                sort_text(row[field], client) if isinstance(row[field], str) else row[field],
                row["id"],
            ),
            reverse=sort.endswith(":desc"),
        )
    filtered = all_pages(
        client, "tech-cards", {"query": prefix, "active": False, "revision_status": "draft"}
    )
    assert filtered and all(
        not row["is_active"]
        and row["latest_revision_status"] == "draft"
        and row["draft_revision_number"] == 1
        for row in filtered
    )
    response = client.get(f"{ROOT}/directory/tech-cards", params={"query": "версия_%\\"})
    assert response.status_code == 200
    assert len(response.json()["items"]) == (
        1 if client.app.state.database.engine.dialect.name == "postgresql" else 0
    )
    first = client.get(f"{ROOT}/directory/tech-cards", params={"query": prefix, "limit": 1}).json()
    for params in [
        {"query": prefix, "active": True},
        {"query": prefix, "revision_status": "draft"},
        {"query": prefix, "sort": "revision:desc"},
    ]:
        bad = client.get(
            f"{ROOT}/directory/tech-cards", params={**params, "cursor": first["next_cursor"]}
        )
        assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_cursor"
    for params in [{"cursor": "bad"}, {"sort": "unknown"}, {"limit": 101}, {"unexpected": "value"}]:
        assert client.get(f"{ROOT}/directory/tech-cards", params=params).status_code == 422


def test_models_without_a_card_are_paged_and_creation_rechecks_ownership(tech_records):
    (client, prefix, models, _, _, _, _), _, free_models = tech_records
    rows = all_pages(client, "tech-card-models", {"query": prefix})
    assert {row["id"] for row in rows} == set(free_models)
    assert not set(models) & {row["id"] for row in rows}, "Inactive cards still occupy their model"
    body = {
        "code": f"{prefix.upper()}-NEW",
        "revision": {
            "name": "Новая карта",
            "checkpoints": [
                {
                    "position": 1,
                    "stage_code": "cut",
                    "role_code": "cut",
                    "name": "Крой",
                    "standard_minutes": "12.34",
                    "labor_cost": "3.25",
                }
            ],
        },
    }
    selected = client.get(
        f"{ROOT}/directory/selected", params={"kind": "tech-card-models", "ids": free_models[-1]}
    )
    assert selected.status_code == 200 and selected.json()[0]["id"] == free_models[-1]
    created = client.post(f"{ROOT}/models/{free_models[-1]}/tech-cards", json=body)
    assert created.status_code == 201, created.text
    assert client.post(f"{ROOT}/models/{free_models[-1]}/tech-cards", json=body).status_code == 409
    assert free_models[-1] not in {
        row["id"] for row in all_pages(client, "tech-card-models", {"query": prefix})
    }
    assert (
        client.get(f"{ROOT}/tech-cards/{created.json()['id']}/revision-source").status_code == 409
    )


def test_source_is_one_non_discarded_revision_and_pages_do_not_hydrate_history(tech_records):
    (client, prefix, _, _, _, _, tokens), cards, _ = tech_records
    response = client.get(f"{ROOT}/tech-cards/{cards[-1]}/revision-source")
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    row = response.json()
    assert row["latest_revision_number"] == 130 and row["source"]["revision_number"] == 129
    assert (
        len(row["source"]["checkpoints"]) == 200
        and row["source"]["checkpoints"][0]["role_code"] == "qc"
    )
    assert client.get(f"{ROOT}/tech-cards/{cards[0]}/revision-source").status_code == 409
    assert client.get(f"{ROOT}/tech-cards/{cards[3]}/revision-source").json()["source"] is None
    assert client.get(f"{ROOT}/tech-cards/2147483647/revision-source").status_code == 404
    cookie = client.cookies.get("gb_production_session")
    client.cookies.clear()
    for url in [
        "directory/tech-cards",
        "directory/tech-card-models",
        f"tech-cards/{cards[-1]}/revision-source",
    ]:
        assert client.get(f"{ROOT}/{url}").status_code == 401
        assert client.get(f"{ROOT}/{url}", headers=tokens[0]).status_code == 401
    client.cookies.set("gb_production_session", cookie)

    async def prove():
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        engine = client.app.state.database.engine
        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            for kind, query in [
                ("tech-cards", TechCardDirectoryQuery(query=prefix)),
                ("tech-card-models", TechCardModelQuery(query=prefix)),
            ]:
                statements.clear()
                async with client.app.state.database.session() as session:
                    page = await TechDirectoryService().page(session, kind, query)
                    assert (
                        len(page.items) == 24 and len(statements) == 1 and not session.identity_map
                    )
            statements.clear()
            async with client.app.state.database.session() as session:
                source = await TechDirectoryService().editor(session, cards[-1])
                assert (
                    len(source.source.checkpoints) == 200
                    and len(statements) == 2
                    and not session.identity_map
                )
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)

    client.portal.call(prove)


def test_commands_load_only_target_revisions_and_recheck_a_stale_identity_map(tech_records):
    (client, _, _, _, _, users, _), cards, _ = tech_records

    async def prove():
        db = client.app.state.database
        service = CrmReferenceService()
        payload = CrmTechCardRevisionWrite(
            name="Новая версия",
            checkpoints=[
                {
                    "position": 1,
                    "stage_code": "sewing",
                    "role_code": "qc",
                    "name": "Точный шаг",
                    "standard_minutes": "12.34",
                    "labor_cost": "3.25",
                }
            ],
        )
        async with db.session() as stale:
            old = await stale.get(CrmTechCard, cards[-1])
            assert old.latest_revision_number == 130
            async with db.session() as session:
                revision = await service.create_tech_card_revision(
                    session,
                    tech_card_id=cards[-1],
                    expected_latest_revision=130,
                    payload=payload,
                    actor_user_id=users[0],
                )
                assert revision.revision_number == 131 and revision.based_on_revision_id is not None
                assert len(session.identity_map) < 10, (
                    "Creating a revision must not hydrate the 130 old versions or their operations"
                )
                await session.commit()
            with pytest.raises(CrmReferenceVersionConflictError):
                await service.create_tech_card_revision(
                    stale,
                    tech_card_id=cards[-1],
                    expected_latest_revision=130,
                    payload=payload,
                    actor_user_id=users[0],
                )
            await stale.rollback()
        async with db.session() as session:
            published = await service.publish_tech_card_revision(
                session, tech_card_id=cards[-1], revision_number=131, actor_user_id=users[0]
            )
            assert published.status == "published" and len(published.checkpoints) == 1
            assert published.checkpoints[0].role_code == "qc" and published.checkpoints[
                0
            ].standard_minutes == Decimal("12.34")
            assert len(session.identity_map) < 10, (
                "Publication must not load the 200 operations of the previous version"
            )
            await session.commit()
        async with db.session() as session:
            draft = await service.create_tech_card_revision(
                session,
                tech_card_id=cards[-1],
                expected_latest_revision=131,
                payload=payload,
                actor_user_id=users[0],
            )
            assert draft.revision_number == 132
            discarded = await service.discard_tech_card_draft(
                session, tech_card_id=cards[-1], revision_number=132, actor_user_id=users[0]
            )
            assert discarded.status == "discarded" and len(session.identity_map) < 10
            await session.commit()
        async with db.session() as session:
            source = await TechDirectoryService().editor(session, cards[-1])
            assert source.latest_revision_number == 132 and source.source.revision_number == 131
            archived = await session.scalar(
                select(CrmTechCardRevision).where(
                    CrmTechCardRevision.tech_card_id == cards[-1],
                    CrmTechCardRevision.revision_number == 129,
                )
            )
            assert archived.status == "archived"

    client.portal.call(prove)
