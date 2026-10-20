"""Private reads stay bounded, owner scoped and free of loaded ORM collections."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import delete, event

from app.modules.identity.models import RoleName, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.orders.models import Order
from app.modules.partners.models import (
    PartnerCommission,
    PartnerLanding,
    PartnerOrderAttribution,
    PartnerPayoutRequest,
    PartnerProfile,
    PartnerVisit,
)
from app.modules.partners.read_schemas import AdminPartnerQuery, PartnerPayoutQuery
from app.modules.partners.read_service import PartnerReadService
from app.modules.partners.repository import PartnerRepository
from tests.contract.test_partner_owner_landings import owners as owners


def test_admin_profile_directory_pages_search_policy_and_cursor_binding(owners):
    client, _, tokens, users, _ = owners
    prefix = uuid4().hex

    async def seed():
        async with client.app.state.database.session() as session:
            role = await IdentityRepository().get_role(session, RoleName.ADMIN)
            session.add(UserRole(user_id=users[0], role_id=role.id))
            people = [
                User(
                    email=f"{prefix}-{i}@example.test",
                    email_normalized=f"{prefix}-{i}@example.test",
                )
                for i in range(130)
            ]
            session.add_all(people)
            await session.flush()
            profiles = [
                PartnerProfile(
                    user_id=person.id,
                    code=f"{prefix}-{i:03}",
                    display_name=f"Партнёр {i:03}" + (" %_\\" if i == 129 else ""),
                    commission_bps=1000,
                    status="suspended" if i % 3 == 0 else "active",
                )
                for i, person in enumerate(people)
            ]
            session.add_all(profiles)
            await session.commit()
            return [person.id for person in people], [profile.id for profile in profiles]

    person_ids, profile_ids = client.portal.call(seed)

    async def prove_projection():
        statements = []

        def capture(conn, cursor, statement, parameters, context, many):
            if statement.lstrip().upper().startswith("SELECT"):
                statements.append(statement)

        engine = client.app.state.database.engine
        event.listen(engine.sync_engine, "before_cursor_execute", capture)
        try:
            async with client.app.state.database.session() as session:
                result = await PartnerReadService.profiles(session, AdminPartnerQuery(query=prefix))
                assert len(result.items) == 24 and len(statements) == 1
                assert "LIMIT" in statements[0] and len(session.identity_map) == 0
                assert "partner_requisites" not in statements[0]
        finally:
            event.remove(engine.sync_engine, "before_cursor_execute", capture)

    client.portal.call(prove_projection)
    path = "/api/admin/partners"
    try:
        assert client.get(path).status_code == 401
        assert client.get(path, headers=tokens[1]).status_code == 403
        first = client.get(path, headers=tokens[0], params={"query": prefix})
        assert first.status_code == 200, first.text
        assert first.headers["cache-control"] == "no-store"
        page, found = first.json(), []
        cursor = page["next_cursor"]
        while True:
            assert len(page["items"]) <= 24
            assert all(
                set(row)
                == {
                    "id",
                    "user_id",
                    "display_name",
                    "code",
                    "status",
                    "commission_bps",
                    "created_at",
                }
                for row in page["items"]
            )
            found.extend(row["id"] for row in page["items"])
            if not page["next_cursor"]:
                break
            response = client.get(
                path, headers=tokens[0], params={"query": prefix, "cursor": page["next_cursor"]}
            )
            assert response.status_code == 200, response.text
            page = response.json()
        assert found == list(reversed(profile_ids))
        for changes in ({"query": "other"}, {"status": "active"}, {"selectable": True}):
            result = client.get(
                path, headers=tokens[0], params={"query": prefix, "cursor": cursor, **changes}
            )
            assert result.status_code == 422 and result.json()["detail"]["code"] == "invalid_cursor"
        continuation = client.get(
            path, headers=tokens[0], params={"query": prefix, "cursor": cursor, "limit": 5}
        )
        assert len(continuation.json()["items"]) == 5
        selectable, after = [], None
        while True:
            page = client.get(
                path,
                headers=tokens[0],
                params={
                    "query": prefix,
                    "selectable": True,
                    **({"cursor": after} if after else {}),
                },
            ).json()
            selectable.extend(page["items"])
            after = page["next_cursor"]
            if not after:
                break
        assert len(selectable) == 86 and all(row["status"] == "active" for row in selectable)
        literal = client.get(path, headers=tokens[0], params={"query": "%_\\"}).json()
        assert [row["id"] for row in literal["items"]] == [profile_ids[-1]]
        if client.app.state.database.engine.dialect.name == "postgresql":
            result = client.get(path, headers=tokens[0], params={"query": "пАрТнЁр 129"})
            assert [row["id"] for row in result.json()["items"]] == [profile_ids[-1]]
        for params in (
            {"limit": 101},
            {"limit": 0},
            {"cursor": "bad"},
            {"status": "unknown"},
            {"unbounded": True},
        ):
            assert client.get(path, headers=tokens[0], params=params).status_code == 422
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(
                    delete(PartnerProfile).where(PartnerProfile.id.in_(profile_ids))
                )
                await session.execute(delete(User).where(User.id.in_(person_ids)))
                await session.commit()

        client.portal.call(cleanup)


def test_owner_payout_pages_beyond100_and_single_statement_totals(owners):
    client, _, tokens, users, profiles = owners
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async def seed():
        async with client.app.state.database.session() as session:
            payouts = [
                PartnerPayoutRequest(
                    partner_id=profiles[0],
                    amount=Decimal("0.01"),
                    status="rejected",
                    created_at=now - timedelta(minutes=i // 5),
                )
                for i in range(130)
            ]
            payouts += [
                PartnerPayoutRequest(
                    partner_id=profiles[index],
                    amount=Decimal(amount),
                    status=status,
                    created_at=now,
                )
                for index, amount, status in [
                    (0, "10.01", "requested"),
                    (0, "20.02", "approved"),
                    (0, "30.03", "paid"),
                    (0, "999", "canceled"),
                    (1, "999", "requested"),
                ]
            ]
            session.add_all(payouts)
            landing = PartnerLanding(
                partner_id=profiles[0],
                slug=uuid4().hex,
                title="Ledger",
                headline="Ledger",
                description="Ledger",
                cta_label="Open",
                cta_href="/",
                content={},
            )
            session.add(landing)
            await session.flush()
            for i in range(3):
                session.add(
                    PartnerVisit(
                        landing_id=landing.id,
                        visitor_digest=str(i) * 64,
                        visited_on=now.date(),
                        created_at=now,
                    )
                )
            orders = []
            for _index, (amount, status, mature) in enumerate(
                [
                    ("100.01", "pending", True),
                    ("10.02", "pending", False),
                    ("999", "canceled", True),
                ]
            ):
                order = Order(
                    email="test@example.test",
                    email_normalized="test@example.test",
                    phone="+79990000000",
                    first_name="Test",
                    delivery_city="Test",
                    delivery_method="courier",
                    delivery_address="Test",
                    payment_method="card",
                    items_subtotal=1000,
                    delivery_price=0,
                    total_price=1000,
                    currency="RUB",
                    request_fingerprint_sha256=uuid4().hex * 2,
                )
                session.add(order)
                await session.flush()
                orders.append(order.id)
                attribution = PartnerOrderAttribution(
                    order_id=order.id,
                    partner_id=profiles[0],
                    landing_id=landing.id,
                    commission_bps_snapshot=1000,
                    order_amount_snapshot=1000,
                    commission_base_snapshot=1000,
                    currency="RUB",
                    attributed_at=now,
                )
                session.add(attribution)
                await session.flush()
                session.add(
                    PartnerCommission(
                        attribution_id=attribution.id,
                        partner_id=profiles[0],
                        order_id=order.id,
                        amount=Decimal(amount),
                        currency="RUB",
                        status=status,
                        available_at=now - timedelta(days=1) if mature else now + timedelta(days=1),
                    )
                )
            await session.commit()
            return [row.id for row in payouts], orders, landing.id

    payout_ids, order_ids, landing_id = client.portal.call(seed)
    path = "/api/partner/payouts"
    try:
        assert client.get(path).status_code == 401
        first = client.get(path, headers=tokens[0])
        assert first.status_code == 200, first.text
        assert first.headers["cache-control"] == "no-store"
        page, found, cursor = first.json(), [], first.json()["next_cursor"]
        while True:
            assert len(page["items"]) <= 24
            found.extend(row["id"] for row in page["items"])
            if not page["next_cursor"]:
                break
            result = client.get(path, headers=tokens[0], params={"cursor": page["next_cursor"]})
            assert result.status_code == 200, result.text
            page = result.json()
        assert len(found) == 134 and len(set(found)) == 134 and payout_ids[-1] not in found
        assert client.get(path, headers=tokens[1], params={"cursor": cursor}).status_code == 422
        assert (
            len(
                client.get(path, headers=tokens[0], params={"cursor": cursor, "limit": 5}).json()[
                    "items"
                ]
            )
            == 5
        )
        for params in ({"cursor": "bad"}, {"limit": 101}, {"partner_id": profiles[1]}):
            assert client.get(path, headers=tokens[0], params=params).status_code == 422

        async def prove():
            statements = []

            def capture(conn, cursor, statement, parameters, context, many):
                if statement.lstrip().upper().startswith("SELECT"):
                    statements.append(statement)

            engine = client.app.state.database.engine
            event.listen(engine.sync_engine, "before_cursor_execute", capture)
            try:
                async with client.app.state.database.session() as session:
                    totals = await PartnerRepository().dashboard_totals(
                        session, partner_id=profiles[0], now=now
                    )
                    assert totals == {
                        "has_requisites": False,
                        "visits": 3,
                        "orders": 3,
                        "earned": Decimal("110.03"),
                        "available": Decimal("39.95"),
                        "paid": Decimal("30.03"),
                    }
                    assert len(statements) == 1 and len(session.identity_map) == 0
                    statements.clear()
                    result = await PartnerReadService.payouts(
                        session, profiles[0], PartnerPayoutQuery()
                    )
                    assert len(result.items) == 24 and len(statements) == 1
                    assert "LIMIT" in statements[0] and len(session.identity_map) == 0

            finally:
                event.remove(engine.sync_engine, "before_cursor_execute", capture)

        client.portal.call(prove)
        # Retired unused list APIs must not remain an unbounded alternate path.
        assert client.get("/api/partner/landings", headers=tokens[0]).status_code == 404
        assert client.get("/api/partner/commissions", headers=tokens[0]).status_code == 404
    finally:

        async def cleanup():
            async with client.app.state.database.session() as session:
                await session.execute(
                    delete(PartnerCommission).where(PartnerCommission.order_id.in_(order_ids))
                )
                await session.execute(
                    delete(PartnerOrderAttribution).where(
                        PartnerOrderAttribution.order_id.in_(order_ids)
                    )
                )
                await session.execute(delete(Order).where(Order.id.in_(order_ids)))
                await session.execute(
                    delete(PartnerPayoutRequest).where(PartnerPayoutRequest.id.in_(payout_ids))
                )
                await session.execute(
                    delete(PartnerVisit).where(PartnerVisit.landing_id == landing_id)
                )
                await session.execute(delete(PartnerLanding).where(PartnerLanding.id == landing_id))
                await session.commit()

        client.portal.call(cleanup)
