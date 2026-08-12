from __future__ import annotations

import asyncio
import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import AppEnvironment, Settings
from app.db.base import Base
from app.db.session import DatabaseManager
from app.modules.catalog.models import Product
from app.modules.crm.command_models import CrmAssignmentEvent, CrmStaffCommand
from app.modules.crm.command_service import CrmStaffCommandService
from app.modules.crm.material_models import CrmMaterialBalance, CrmMaterialMovement
from app.modules.crm.material_service import CrmMaterialService
from app.modules.crm.models import CrmOrderProject, CrmProductionUnit, CrmProjectEvent
from app.modules.crm.production_models import CrmProductionPlanRevision
from app.modules.crm.read_service import CrmReadService
from app.modules.crm.reference_models import (
    CrmCatalogProductModelLink,
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentSize,
    CrmTechCard,
    CrmTechCardRevision,
)
from app.modules.crm.repository import CrmProductionUnitSnapshot, CrmProjectRepository
from app.modules.crm.router import router as crm_router
from app.modules.crm.router import write_router as crm_write_router
from app.modules.fulfillment.models import FulfillmentJob
from app.modules.identity.exceptions import PermissionDeniedError
from app.modules.identity.models import PermissionCode, RoleName, User
from app.modules.identity.repository import IdentityRepository
from app.modules.orders.models import Order, OrderItem
from app.modules.payments.models import Payment, PaymentAttempt

NOW = datetime(2026, 8, 13, 2, 0, tzinfo=timezone.utc)


class StaffIdentityGate:
    def __init__(self, user: User) -> None:
        self.user = user
        self.allowed = False
        self.permissions: list[PermissionCode] = []

    async def resolve_access_token(self, *args, **kwargs) -> User:
        return self.user

    async def require_permission(
        self,
        _session,
        *,
        user_id: int,
        permission: PermissionCode,
    ) -> None:
        assert user_id == self.user.id
        self.permissions.append(permission)
        if not self.allowed:
            raise PermissionDeniedError("CRM access denied")


def _settings(path: Path) -> Settings:
    return Settings(
        _env_file=None,
        app_env=AppEnvironment.TEST,
        database_enabled=True,
        database_url=f"sqlite+aiosqlite:///{path}",
    )


async def _seed(database: DatabaseManager) -> tuple[User, User]:
    project_repository = CrmProjectRepository()
    async with database.session() as session:
        actor = User(
            email="staff@example.test",
            email_normalized="staff@example.test",
            status="active",
            email_verified_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        customer = User(
            email="customer@example.test",
            email_normalized="customer@example.test",
            status="active",
            email_verified_at=NOW,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add_all([actor, customer])
        await session.flush()
        identity_repository = IdentityRepository()
        await identity_repository.ensure_system_authorization(session)
        manager_role = await identity_repository.get_role(session, RoleName.MANAGER)
        assert manager_role is not None
        await identity_repository.assign_role(
            session,
            user_id=actor.id,
            role_id=manager_role.id,
        )

        for number in range(1, 4):
            digest = hashlib.sha256(f"crm-read-{number}".encode()).hexdigest()
            quantity = 2 if number == 1 else 1
            total = Decimal("100.00") * quantity
            product = Product(
                id=100 + number,
                title=f"Garment {number}",
                slug=f"garment-{number}",
                price=Decimal("100.00"),
                sizes=["M"],
                colors=["black"],
                is_active=True,
                product_type="normal",
                weight_kg=Decimal("0.500"),
                height_cm=Decimal("10.00"),
                width_cm=Decimal("20.00"),
                length_cm=Decimal("30.00"),
                stock_quantity=10,
                reserved_quantity=0,
            )
            order = Order(
                email=f"private-{number}@example.test",
                email_normalized=f"private-{number}@example.test",
                phone=f"+7900000000{number}",
                first_name=f"Private {number}",
                delivery_city="Private City",
                delivery_method="courier",
                delivery_address=f"Private address {number}",
                payment_method="bank_card",
                items_subtotal=total,
                delivery_price=Decimal("0.00"),
                total_price=total,
                currency="RUB",
                status="processing",
                payment_status="paid",
                version=2,
                request_fingerprint_sha256=digest,
                created_at=NOW,
                updated_at=NOW,
                items=[
                    OrderItem(
                        client_item_id=f"line-{number}",
                        product_id_snapshot=product.id,
                        variant_id_snapshot=200 + number,
                        sku_snapshot=f"SKU-{number}",
                        title_snapshot=f"Garment {number}",
                        unit_price=Decimal("100.00"),
                        quantity=quantity,
                        line_total=total,
                        image_url_snapshot="",
                        size_snapshot="M",
                        color_snapshot="black",
                        customization_snapshot={"private_measurement": f"secret-{number}"},
                        sort_order=0,
                    )
                ],
            )
            session.add_all([product, order])
            await session.flush()
            payment = Payment(
                order_id=order.id,
                status="succeeded",
                amount=order.total_price,
                currency="RUB",
                succeeded_at=NOW,
                created_at=NOW,
                updated_at=NOW,
            )
            session.add(payment)
            await session.flush()
            attempt = PaymentAttempt(
                payment_id=payment.id,
                attempt_number=1,
                client_key_digest_sha256=digest,
                provider_idempotence_key=(f"00000000-0000-4000-8000-{number:012d}"),
                request_fingerprint_sha256=digest,
                payment_method="bank_card",
                status="succeeded",
                provider_payment_id=f"private-provider-{number}",
                provider_created_at=NOW,
                captured_at=NOW,
                resolved_at=NOW,
                created_at=NOW,
                updated_at=NOW,
            )
            session.add(attempt)
            await session.flush()
            job = FulfillmentJob(
                order_id=order.id,
                source_payment_attempt_id=attempt.id,
                kind="crm_order_project",
                status="completed",
                attempts_count=1,
                max_attempts=5,
                available_at=NOW,
                completed_at=NOW,
                result_reference=f"crm-project:{number}",
                created_at=NOW,
                updated_at=NOW,
            )
            session.add(job)
            await session.flush()
            project = await project_repository.acquire_from_paid_order(
                session,
                order_id=order.id,
                source_fulfillment_job_id=job.id,
                source_payment_attempt_id=attempt.id,
                order_version_snapshot=order.version,
                total_price_snapshot=order.total_price,
                currency=order.currency,
                payment_succeeded_at_snapshot=NOW,
                units=tuple(
                    CrmProductionUnitSnapshot(
                        order_item_id=order.items[0].id,
                        product_id_snapshot=product.id,
                        variant_id_snapshot=200 + number,
                        unit_number=unit_number,
                    )
                    for unit_number in range(1, quantity + 1)
                ),
                now=NOW,
            )
            if number == 1:
                project.assigned_to_user_id = actor.id

        fabric = CrmFabric(
            code="LINEN_BLACK",
            name="Linen",
            material_type="linen",
            color_name="Black",
            color_hex="#000000",
            density_gsm=Decimal("180.00"),
            width_cm=Decimal("150.00"),
            cost_per_meter=Decimal("900.00"),
            currency="RUB",
            is_active=True,
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
        model = CrmGarmentModel(
            code="DRESS_01",
            name="Dress",
            base_height_cm=Decimal("100.00"),
            base_length_cm=Decimal("120.00"),
            base_width_cm=Decimal("50.00"),
            base_weight_g=Decimal("500.00"),
            is_active=True,
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add_all([fabric, model])
        await session.flush()
        session.add(
            CrmMaterialBalance(
                fabric_id=fabric.id,
                on_hand_meters=Decimal("25.000"),
                reserved_meters=Decimal("5.000"),
                version=2,
                updated_at=NOW,
            )
        )
        size = CrmGarmentSize(
            garment_model_id=model.id,
            code="M",
            sort_order=1,
            base_price=Decimal("100.00"),
            currency="RUB",
            is_active=True,
            version=1,
            created_at=NOW,
            updated_at=NOW,
        )
        link = CrmCatalogProductModelLink(
            garment_model_id=model.id,
            catalog_product_id=101,
            created_by_user_id=actor.id,
            created_at=NOW,
        )
        card = CrmTechCard(
            garment_model_id=model.id,
            code="TC_DRESS_01",
            latest_revision_number=1,
            is_active=True,
            created_at=NOW,
            updated_at=NOW,
        )
        session.add_all([size, link, card])
        await session.flush()
        revision = CrmTechCardRevision(
            tech_card_id=card.id,
            revision_number=1,
            status="published",
            name_snapshot="Dress production v1",
            created_by_user_id=actor.id,
            published_by_user_id=actor.id,
            created_at=NOW,
            published_at=NOW,
        )
        session.add(revision)
        await session.flush()
        first_unit_id = await session.scalar(
            select(CrmProductionUnit.id).order_by(CrmProductionUnit.id)
        )
        assert first_unit_id is not None
        session.add(
            CrmProductionPlanRevision(
                production_unit_id=first_unit_id,
                revision_number=1,
                garment_model_id=model.id,
                garment_size_id=size.id,
                tech_card_revision_id=revision.id,
                status="active",
                evidence_sha256=hashlib.sha256(b"read-plan").hexdigest(),
                planned_by_user_id=actor.id,
                planned_at=NOW,
            )
        )
        await session.commit()
        return actor, customer


def test_crm_staff_api_requires_permission_and_returns_bounded_pii_minimized_reads(
    tmp_path: Path,
) -> None:
    async def scenario() -> None:
        settings = _settings(tmp_path / "crm-staff-api.db")
        database = DatabaseManager(settings)
        await database.startup()
        try:
            async with database.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
            actor, customer = await _seed(database)
            identity = StaffIdentityGate(actor)
            application = FastAPI()
            application.state.settings = settings
            application.state.database = database
            application.state.identity_service = identity
            application.state.crm_read_service = CrmReadService()
            application.state.crm_command_service = CrmStaffCommandService()
            application.state.crm_material_service = CrmMaterialService()
            application.include_router(crm_router)
            application.include_router(crm_write_router)

            async with AsyncClient(
                transport=ASGITransport(app=application),
                base_url="http://test",
            ) as client:
                unauthorized = await client.get("/api/crm/projects")
                assert unauthorized.status_code == 401

                denied = await client.get(
                    "/api/crm/projects",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert denied.status_code == 403
                assert denied.json() == {"detail": "Forbidden"}

                denied_write = await client.put(
                    "/api/crm/projects/2/assignment",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "denied-project-assign-0001",
                    },
                    json={
                        "expected_version": 1,
                        "assigned_to_user_id": actor.id,
                        "reason_code": "manager_assigned",
                    },
                )
                assert denied_write.status_code == 403

                identity.allowed = True
                first_page = await client.get(
                    "/api/crm/projects?limit=2",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert first_page.status_code == 200
                assert first_page.headers["cache-control"] == "no-store"
                assert [item["id"] for item in first_page.json()["items"]] == [3, 2]
                assert first_page.json()["next_cursor"] == 2
                assert first_page.json()["limit"] == 2
                assert set(first_page.json()["items"][0]) == {
                    "id",
                    "order_id",
                    "status",
                    "version",
                    "items_count",
                    "units_count",
                    "assigned_to_user_id",
                    "paid_at",
                    "started_at",
                    "closed_at",
                    "created_at",
                    "updated_at",
                }

                second_page = await client.get(
                    "/api/crm/projects?limit=2&cursor=2",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert [item["id"] for item in second_page.json()["items"]] == [1]
                assert second_page.json()["next_cursor"] is None

                assigned = await client.get(
                    f"/api/crm/projects?assigned_to_user_id={actor.id}",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert [item["id"] for item in assigned.json()["items"]] == [1]

                detail = await client.get(
                    "/api/crm/projects/1?unit_limit=1",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert detail.status_code == 200
                assert detail.json()["units"]["limit"] == 1
                assert detail.json()["units"]["next_cursor"] is not None
                unit = detail.json()["units"]["items"][0]
                assert unit["title"] == "Garment 1"
                assert unit["size"] == "M"
                assert unit["active_plan"]["revision_number"] == 1
                next_unit = await client.get(
                    "/api/crm/projects/1"
                    f"?unit_limit=1&unit_cursor={detail.json()['units']['next_cursor']}",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert len(next_unit.json()["units"]["items"]) == 1
                assert next_unit.json()["units"]["next_cursor"] is None
                rendered = detail.text.casefold()
                for private_value in (
                    "private-1@example.test",
                    "+79000000001",
                    "private address 1",
                    "private-provider-1",
                    "private_measurement",
                    "secret-1",
                ):
                    assert private_value.casefold() not in rendered

                missing = await client.get(
                    "/api/crm/projects/9999",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert missing.status_code == 404

                fabrics = await client.get(
                    "/api/crm/reference/fabrics?is_active=true",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert fabrics.status_code == 200
                assert fabrics.json()["items"][0]["code"] == "LINEN_BLACK"
                assert fabrics.json()["items"][0]["balance"]["available_meters"] == "20.000"

                models = await client.get(
                    "/api/crm/reference/garment-models?is_active=true",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert models.status_code == 200
                model = models.json()["items"][0]
                assert model["catalog_product_ids"] == [101]
                assert [size["code"] for size in model["sizes"]] == ["M"]
                assert model["published_tech_card"]["revision_number"] == 1

                oversized = await client.get(
                    "/api/crm/projects?limit=101",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert oversized.status_code == 422

                invalid_project = await client.get(
                    "/api/crm/projects/0",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert invalid_project.status_code == 422

                missing_key = await client.put(
                    "/api/crm/projects/2/assignment",
                    headers={"Authorization": "Bearer staff-token"},
                    json={
                        "expected_version": 1,
                        "assigned_to_user_id": actor.id,
                        "reason_code": "manager_assigned",
                    },
                )
                assert missing_key.status_code == 422

                project_assignment_payload = {
                    "expected_version": 1,
                    "assigned_to_user_id": actor.id,
                    "reason_code": "manager_assigned",
                }
                project_assignment_headers = {
                    "Authorization": "Bearer staff-token",
                    "Idempotency-Key": "project-assign-command-0001",
                }
                assigned_project = await client.put(
                    "/api/crm/projects/2/assignment",
                    headers=project_assignment_headers,
                    json=project_assignment_payload,
                )
                assert assigned_project.status_code == 200
                assert assigned_project.headers["cache-control"] == "no-store"
                assert assigned_project.json() == {
                    "command_id": 1,
                    "command_type": "project.assign",
                    "target_id": 2,
                    "result_version": 2,
                }
                replayed_project = await client.put(
                    "/api/crm/projects/2/assignment",
                    headers=project_assignment_headers,
                    json=project_assignment_payload,
                )
                assert replayed_project.json() == assigned_project.json()

                changed_key_payload = {
                    **project_assignment_payload,
                    "assigned_to_user_id": None,
                }
                changed_key = await client.put(
                    "/api/crm/projects/2/assignment",
                    headers=project_assignment_headers,
                    json=changed_key_payload,
                )
                assert changed_key.status_code == 409

                stale_assignment = await client.put(
                    "/api/crm/projects/2/assignment",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "project-assign-command-stale",
                    },
                    json=project_assignment_payload,
                )
                assert stale_assignment.status_code == 409

                ineligible = await client.put(
                    "/api/crm/projects/3/assignment",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "project-assign-ineligible",
                    },
                    json={
                        "expected_version": 1,
                        "assigned_to_user_id": customer.id,
                        "reason_code": "manager_assigned",
                    },
                )
                assert ineligible.status_code == 409

                project_started = await client.patch(
                    "/api/crm/projects/2/status",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "project-transition-0001",
                    },
                    json={
                        "expected_version": 2,
                        "to_status": "in_progress",
                        "reason_code": "production_started",
                    },
                )
                assert project_started.status_code == 200
                assert project_started.json()["result_version"] == 3
                late_replay = await client.put(
                    "/api/crm/projects/2/assignment",
                    headers=project_assignment_headers,
                    json=project_assignment_payload,
                )
                assert late_replay.json() == assigned_project.json()

                unsafe_terminal_project = await client.patch(
                    "/api/crm/projects/2/status",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "project-terminal-blocked-0001",
                    },
                    json={
                        "expected_version": 3,
                        "to_status": "completed",
                        "reason_code": "production_completed",
                    },
                )
                assert unsafe_terminal_project.status_code == 409

                project_unassigned = await client.put(
                    "/api/crm/projects/2/assignment",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "project-unassign-command-0001",
                    },
                    json={
                        "expected_version": 3,
                        "assigned_to_user_id": None,
                        "reason_code": "manager_unassigned",
                    },
                )
                assert project_unassigned.status_code == 200
                assert project_unassigned.json()["result_version"] == 4

                unit_assigned = await client.put(
                    "/api/crm/units/1/assignment",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "unit-assign-command-0001",
                    },
                    json={
                        "expected_version": 1,
                        "assigned_to_user_id": actor.id,
                        "reason_code": "seamstress_assigned",
                    },
                )
                assert unit_assigned.status_code == 200
                assert unit_assigned.json()["result_version"] == 2

                unit_started = await client.patch(
                    "/api/crm/units/1/status",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "unit-transition-start-0001",
                    },
                    json={
                        "expected_version": 2,
                        "to_status": "in_progress",
                        "reason_code": "work_started",
                    },
                )
                assert unit_started.status_code == 200
                assert unit_started.json()["result_version"] == 3
                replayed_unit_assignment = await client.put(
                    "/api/crm/units/1/assignment",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "unit-assign-command-0001",
                    },
                    json={
                        "expected_version": 1,
                        "assigned_to_user_id": actor.id,
                        "reason_code": "seamstress_assigned",
                    },
                )
                assert replayed_unit_assignment.json() == unit_assigned.json()

                unit_planned = await client.post(
                    "/api/crm/units/2/plans",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "unit-plan-command-0001",
                    },
                    json={
                        "expected_version": 1,
                        "garment_size_id": 1,
                        "tech_card_revision_id": 1,
                    },
                )
                assert unit_planned.status_code == 200
                assert unit_planned.json()["command_type"] == "unit.plan"
                assert unit_planned.json()["result_version"] == 2

                unlinked_product_plan = await client.post(
                    "/api/crm/units/3/plans",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "unit-plan-unlinked-product",
                    },
                    json={
                        "expected_version": 1,
                        "garment_size_id": 1,
                        "tech_card_revision_id": 1,
                    },
                )
                assert unlinked_product_plan.status_code == 409

                material_receipt_headers = {
                    "Authorization": "Bearer staff-token",
                    "Idempotency-Key": "material-receipt-command-0001",
                }
                material_receipt_payload = {
                    "quantity_meters": "5.000",
                    "reason_code": "supplier_receipt",
                }
                material_receipt = await client.post(
                    "/api/crm/materials/fabrics/1/receipts",
                    headers=material_receipt_headers,
                    json=material_receipt_payload,
                )
                assert material_receipt.status_code == 200
                assert material_receipt.headers["cache-control"] == "no-store"
                assert material_receipt.json()["movement_type"] == "receipt"
                assert material_receipt.json()["balance_on_hand_after"] == "30.000"
                assert material_receipt.json()["balance_reserved_after"] == "5.000"
                assert material_receipt.json()["balance_available_after"] == "25.000"

                changed_material_receipt = await client.post(
                    "/api/crm/materials/fabrics/1/receipts",
                    headers=material_receipt_headers,
                    json={**material_receipt_payload, "quantity_meters": "6.000"},
                )
                assert changed_material_receipt.status_code == 409

                reserved_material = await client.post(
                    "/api/crm/materials/reservations",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "material-reserve-command-0001",
                    },
                    json={
                        "plan_revision_id": 2,
                        "fabric_id": 1,
                        "quantity_meters": "3.000",
                    },
                )
                assert reserved_material.status_code == 200
                assert reserved_material.json()["movement_type"] == "reserve"
                reservation_id = reserved_material.json()["reservation_id"]
                assert reservation_id is not None
                assert reserved_material.json()["balance_reserved_after"] == "8.000"

                consumed_material = await client.post(
                    f"/api/crm/materials/reservations/{reservation_id}/consume",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "material-consume-command-0001",
                    },
                    json={
                        "quantity_meters": "2.000",
                        "reason_code": "production_consumed",
                    },
                )
                assert consumed_material.status_code == 200
                assert consumed_material.json()["balance_on_hand_after"] == "28.000"
                assert consumed_material.json()["balance_reserved_after"] == "6.000"

                released_material = await client.post(
                    f"/api/crm/materials/reservations/{reservation_id}/release",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "material-release-command-0001",
                    },
                    json={
                        "quantity_meters": "1.000",
                        "reason_code": "production_released",
                    },
                )
                assert released_material.status_code == 200
                assert released_material.json()["balance_reserved_after"] == "5.000"

                adjusted_material = await client.post(
                    "/api/crm/materials/fabrics/1/adjustments",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "material-adjust-command-0001",
                    },
                    json={
                        "quantity_meters": "1.000",
                        "direction": "in",
                        "reason_code": "inventory_adjustment",
                    },
                )
                assert adjusted_material.status_code == 200
                assert adjusted_material.json()["movement_type"] == "adjustment_in"
                assert adjusted_material.json()["balance_on_hand_after"] == "29.000"

                replayed_material_receipt = await client.post(
                    "/api/crm/materials/fabrics/1/receipts",
                    headers=material_receipt_headers,
                    json=material_receipt_payload,
                )
                assert replayed_material_receipt.json() == material_receipt.json()

                invalid_material_key = await client.post(
                    "/api/crm/materials/fabrics/1/receipts",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "short",
                    },
                    json=material_receipt_payload,
                )
                assert invalid_material_key.status_code == 400

                missing_material_target = await client.post(
                    "/api/crm/materials/fabrics/9999/receipts",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "material-missing-target-0001",
                    },
                    json=material_receipt_payload,
                )
                assert missing_material_target.status_code == 404

                excessive_material_precision = await client.post(
                    "/api/crm/materials/fabrics/1/receipts",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "material-invalid-precision-0001",
                    },
                    json={**material_receipt_payload, "quantity_meters": "1.0001"},
                )
                assert excessive_material_precision.status_code == 422

                unit_cancelled = await client.patch(
                    "/api/crm/units/2/status",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "unit-transition-cancel-0001",
                    },
                    json={
                        "expected_version": 2,
                        "to_status": "cancelled",
                        "reason_code": "customer_cancelled_unit",
                    },
                )
                assert unit_cancelled.status_code == 200
                assert unit_cancelled.json()["result_version"] == 3

                cancelled_unit_reservation = await client.post(
                    "/api/crm/materials/reservations",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "material-reserve-cancelled-unit-0001",
                    },
                    json={
                        "plan_revision_id": 2,
                        "fabric_id": 1,
                        "quantity_meters": "1.000",
                    },
                )
                assert cancelled_unit_reservation.status_code == 409

                replayed_plan = await client.post(
                    "/api/crm/units/2/plans",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "unit-plan-command-0001",
                    },
                    json={
                        "expected_version": 1,
                        "garment_size_id": 1,
                        "tech_card_revision_id": 1,
                    },
                )
                assert replayed_plan.json() == unit_planned.json()

                closed_reassignment = await client.put(
                    "/api/crm/units/2/assignment",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "unit-assign-closed-0001",
                    },
                    json={
                        "expected_version": 3,
                        "assigned_to_user_id": actor.id,
                        "reason_code": "late_assignment",
                    },
                )
                assert closed_reassignment.status_code == 409

                project_two_unit_cancelled = await client.patch(
                    "/api/crm/units/3/status",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "unit-transition-project-two-cancel-0001",
                    },
                    json={
                        "expected_version": 1,
                        "to_status": "cancelled",
                        "reason_code": "customer_cancelled_unit",
                    },
                )
                assert project_two_unit_cancelled.status_code == 200
                assert project_two_unit_cancelled.json()["result_version"] == 2

                mixed_project_closure = await client.patch(
                    "/api/crm/projects/1/status",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "project-mixed-terminal-blocked-0001",
                    },
                    json={
                        "expected_version": 1,
                        "to_status": "cancelled",
                        "reason_code": "mixed_units_blocked",
                    },
                )
                assert mixed_project_closure.status_code == 409

                project_cancelled = await client.patch(
                    "/api/crm/projects/2/status",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "project-terminal-cancel-0001",
                    },
                    json={
                        "expected_version": 4,
                        "to_status": "cancelled",
                        "reason_code": "all_units_cancelled",
                    },
                )
                assert project_cancelled.status_code == 200
                assert project_cancelled.json()["result_version"] == 5
                replayed_project_cancel = await client.patch(
                    "/api/crm/projects/2/status",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "project-terminal-cancel-0001",
                    },
                    json={
                        "expected_version": 4,
                        "to_status": "cancelled",
                        "reason_code": "all_units_cancelled",
                    },
                )
                assert replayed_project_cancel.json() == project_cancelled.json()

                closed_project_reassignment = await client.put(
                    "/api/crm/projects/2/assignment",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "project-assign-closed-0001",
                    },
                    json={
                        "expected_version": 5,
                        "assigned_to_user_id": actor.id,
                        "reason_code": "late_assignment",
                    },
                )
                assert closed_project_reassignment.status_code == 409

                invalid_key = await client.patch(
                    "/api/crm/projects/2/status",
                    headers={
                        "Authorization": "Bearer staff-token",
                        "Idempotency-Key": "short",
                    },
                    json={
                        "expected_version": 3,
                        "to_status": "on_hold",
                        "reason_code": "material_missing",
                    },
                )
                assert invalid_key.status_code == 400

                async with database.session() as session:
                    project = await session.get(CrmOrderProject, 1)
                    assert project is not None
                    project.units_count = 3
                    await session.commit()
                inconsistent = await client.get(
                    "/api/crm/projects/1",
                    headers={"Authorization": "Bearer staff-token"},
                )
                assert inconsistent.status_code == 409
                assert inconsistent.json() == {"detail": "CRM evidence is inconsistent"}

            async with database.session() as session:
                commands = list(
                    await session.scalars(select(CrmStaffCommand).order_by(CrmStaffCommand.id))
                )
                assignments = list(
                    await session.scalars(
                        select(CrmAssignmentEvent).order_by(CrmAssignmentEvent.id)
                    )
                )
                material_movements = list(
                    await session.scalars(
                        select(CrmMaterialMovement).order_by(CrmMaterialMovement.id)
                    )
                )
                project_two_events = list(
                    await session.scalars(
                        select(CrmProjectEvent)
                        .where(CrmProjectEvent.project_id == 2)
                        .order_by(CrmProjectEvent.version)
                    )
                )
                assert len(commands) == 9
                assert {command.status for command in commands} == {"completed"}
                assert {command.actor_user_id for command in commands} == {actor.id}
                assert all(len(command.idempotency_key_sha256) == 64 for command in commands)
                assert all(len(command.command_sha256) == 64 for command in commands)
                persisted = repr([command.__dict__ for command in commands])
                assert "project-assign-command-0001" not in persisted
                assert "unit-transition-start-0001" not in persisted
                assert len(assignments) == 3
                assert [event.entity_version for event in assignments] == [2, 4, 2]
                assert {event.actor_user_id for event in assignments} == {actor.id}
                assert assignments[1].to_assigned_to_user_id is None
                assert [event.version for event in project_two_events] == [1, 3, 5]
                assert [event.to_status for event in project_two_events] == [
                    "queued",
                    "in_progress",
                    "cancelled",
                ]
                assert project_two_events[-1].actor_user_id == actor.id
                assert [movement.movement_type for movement in material_movements] == [
                    "receipt",
                    "reserve",
                    "consume",
                    "release",
                    "adjustment_in",
                ]
                assert {movement.actor_user_id for movement in material_movements} == {actor.id}
                persisted_material = repr([movement.__dict__ for movement in material_movements])
                assert "material-receipt-command-0001" not in persisted_material

                session.add(
                    CrmAssignmentEvent(
                        production_project_id=1,
                        event_key="project:1:assignment:version:99",
                        entity_version=99,
                        from_assigned_to_user_id=None,
                        to_assigned_to_user_id=None,
                        reason_code="invalid_unchanged_assignment",
                        actor_user_id=actor.id,
                        occurred_at=NOW,
                    )
                )
                with pytest.raises(IntegrityError):
                    await session.commit()
                await session.rollback()

            assert identity.permissions
            assert set(identity.permissions) == {PermissionCode.CRM_ACCESS}
        finally:
            await database.shutdown()

    asyncio.run(scenario())
