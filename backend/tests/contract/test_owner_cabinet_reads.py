"""Owner list summaries and a bank existence flag never load private editor payloads."""

from uuid import uuid4

from sqlalchemy import delete, event

from app.modules.partners.models import PartnerLanding, PartnerLandingProduct, PartnerRequisites
from app.modules.partners.requisites_crypto import PartnerRequisitesDecryptionError
from tests.contract.test_partner_owner_landings import owners as owners


def test_owner_list_is_one_compact_projection_and_detail_stays_complete(owners):
    client, products, tokens, _, profiles = owners

    async def seed():
        async with client.app.state.database.session() as session:
            records = [
                PartnerLanding(
                    partner_id=profiles[0],
                    slug=uuid4().hex,
                    title=f"Сообщество {i:03}",
                    headline="Headline",
                    description="Keep description",
                    cta_label="Open",
                    cta_href="/",
                    content={
                        "story_body": "x" * 2000,
                        "faq": [{"question": f"Q{j}", "answer": "a" * 1000} for j in range(8)],
                    },
                )
                for i in range(130)
            ]
            session.add_all(records)
            await session.flush()
            session.add_all(
                [
                    PartnerLandingProduct(landing_id=row.id, product_id=product_id, position=index)
                    for row in records
                    for index, product_id in enumerate(products[:2][::-1])
                ]
            )
            await session.commit()
            return [row.id for row in records]

    ids = client.portal.call(seed)
    try:
        path = "/api/partner/own-landings"
        first = client.get(path, headers=tokens[0])
        assert first.status_code == 200, first.text
        assert first.headers["cache-control"] == "no-store" and len(first.content) < 12000
        page, found = first.json(), []
        cursor = page["next_cursor"]
        while True:
            assert len(page["items"]) <= 24
            for row in page["items"]:
                assert set(row) == {
                    "id",
                    "version",
                    "slug",
                    "title",
                    "image_url",
                    "status",
                    "product_count",
                }
                assert row["product_count"] == 2
                found.append(row["id"])
            if not page["next_cursor"]:
                break
            response = client.get(path, headers=tokens[0], params={"cursor": page["next_cursor"]})
            assert response.status_code == 200, response.text
            page = response.json()
        assert found == list(reversed(ids))
        assert client.get(path, headers=tokens[1]).json()["items"] == []
        foreign = client.get(path, headers=tokens[1], params={"cursor": cursor})
        assert foreign.status_code == 422 and foreign.json()["detail"]["code"] == "invalid_cursor"
        for params in ({"limit": 25}, {"cursor": ""}, {"partner_id": profiles[1]}):
            assert client.get(path, headers=tokens[0], params=params).status_code == 422
        detail = client.get(f"{path}/{ids[-1]}", headers=tokens[0]).json()
        assert detail["content"]["story_body"] == "x" * 2000
        assert len(detail["content"]["faq"]) == 8
        assert detail["description"] == "Keep description"
        assert detail["product_ids"] == products[:2][::-1]

        async def prove_projection():
            statements = []

            def capture(conn, cursor, statement, parameters, context, many):
                if statement.lstrip().upper().startswith("SELECT"):
                    statements.append(statement)

            engine = client.app.state.database.engine
            event.listen(engine.sync_engine, "before_cursor_execute", capture)
            try:
                async with client.app.state.database.session() as session:
                    rows = await client.app.state.partner_program_service.repository.list_owned_landing_page(
                        session, partner_id=profiles[0], limit=24, after_id=None
                    )
                    assert len(rows) == 25 and len(statements) == 1 and not session.identity_map
                    assert (
                        "partner_landings.content" not in statements[0]
                        and "partner_landings.description" not in statements[0]
                    )
            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", capture)

        client.portal.call(prove_projection)
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(delete(PartnerLanding).where(PartnerLanding.id.in_(ids)))
                await session.commit()

        client.portal.call(cleanup)


def test_dashboard_exposes_only_bank_existence_even_if_decryption_is_unavailable(
    owners, monkeypatch
):
    client, _, tokens, _, profiles = owners
    path = "/api/partner/dashboard"
    assert client.get(path, headers=tokens[0]).json()["has_requisites"] is False
    payload = {
        "entity_type": "self_employed",
        "recipient_name": "Тестовый получатель",
        "tax_id": "123456789012",
        "bank_name": "Тестовый банк",
        "bic": "044525225",
        "correspondent_account": "30101810400000000225",
        "settlement_account": "40802810900000000001",
    }
    response = client.put(
        "/api/partner/requisites", headers=tokens[0], json={**payload, "expected_version": 0}
    )
    assert response.status_code == 200, response.text
    decryptions = []

    def broken(*args, **kwargs):
        decryptions.append(True)
        raise PartnerRequisitesDecryptionError("test unavailable")

    monkeypatch.setattr(
        client.app.state.partner_program_service.requisites_codec, "decrypt", broken
    )
    try:
        dashboard = client.get(path, headers=tokens[0])
        assert dashboard.status_code == 200, dashboard.text
        assert (
            dashboard.headers["cache-control"] == "no-store"
            and dashboard.json()["has_requisites"] is True
        )
        assert not set(payload).intersection(dashboard.json())
        assert decryptions == []
        assert client.get(path, headers=tokens[1]).json()["has_requisites"] is False
        assert client.get("/api/partner/requisites", headers=tokens[0]).status_code == 503
        assert len(decryptions) == 1
        assert client.get("/api/partner/own-landings", headers=tokens[0]).status_code == 200
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(
                    delete(PartnerRequisites).where(PartnerRequisites.partner_id == profiles[0])
                )
                await session.commit()

        client.portal.call(cleanup)
