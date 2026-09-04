from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db import models as database_models  # noqa: F401
from app.db.base import Base


def test_alembic_has_one_linear_landing_platform_head() -> None:
    backend_dir = Path(__file__).resolve().parents[2]
    config = Config(str(backend_dir / "alembic.ini"))
    scripts = ScriptDirectory.from_config(config)

    assert scripts.get_heads() == ["20260904_0030"]
    revision = scripts.get_revision("20260904_0030")
    assert revision is not None
    assert revision.down_revision == "20260904_0029"


def test_metadata_has_deterministic_constraint_names() -> None:
    convention = Base.metadata.naming_convention

    assert convention["pk"] == "pk_%(table_name)s"
    assert convention["fk"] == ("fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s")


def test_catalog_and_media_tables_share_the_target_metadata() -> None:
    assert {
        "products",
        "product_variants",
        "media_objects",
        "product_media",
        "product_variant_media",
        "catalog_migration_runs",
    } <= set(Base.metadata.tables)


def test_identity_security_tables_share_the_target_metadata() -> None:
    assert {
        "users",
        "roles",
        "permissions",
        "user_roles",
        "role_permissions",
        "otp_challenges",
        "refresh_sessions",
        "security_audit_events",
        "identity_migration_runs",
    } <= set(Base.metadata.tables)


def test_partner_program_tables_share_the_target_metadata() -> None:
    assert {
        "partner_profiles",
        "partner_landings",
        "partner_visits",
        "partner_order_attributions",
        "partner_commissions",
        "partner_payout_requests",
    } <= set(Base.metadata.tables)


def test_notification_tables_share_the_target_metadata() -> None:
    assert {
        "notification_outbox",
        "notification_delivery_attempts",
    } <= set(Base.metadata.tables)


def test_identity_api_bridge_tables_share_the_target_metadata() -> None:
    assert "legacy_order_claims" in Base.metadata.tables


def test_catalog_write_audit_shares_the_target_metadata() -> None:
    assert {
        "catalog_audit_events",
        "catalog_documents",
        "catalog_document_revisions",
        "catalog_content_migration_runs",
    } <= set(Base.metadata.tables)


def test_persistent_cart_tables_share_the_target_metadata() -> None:
    assert {
        "carts",
        "cart_items",
        "cart_migration_runs",
    } <= set(Base.metadata.tables)


def test_order_creation_tables_share_the_target_metadata() -> None:
    assert {
        "orders",
        "order_items",
        "order_status_history",
        "order_creation_requests",
    } <= set(Base.metadata.tables)


def test_inventory_reservation_table_shares_the_target_metadata() -> None:
    assert "inventory_reservations" in Base.metadata.tables


def test_order_migration_tables_share_the_target_metadata() -> None:
    assert {
        "legacy_order_imports",
        "order_migration_runs",
    } <= set(Base.metadata.tables)


def test_order_guest_access_table_shares_the_target_metadata() -> None:
    assert "order_guest_access" in Base.metadata.tables


def test_payment_persistence_tables_share_the_target_metadata() -> None:
    assert {
        "payments",
        "payment_attempts",
        "payment_events",
        "payment_operations",
    } <= set(Base.metadata.tables)
    attempt_columns = Base.metadata.tables["payment_attempts"].c
    assert {
        "provider_request_sha256",
        "creation_started_at",
        "creation_last_attempt_at",
        "creation_attempts_count",
        "capture_mode",
        "expires_at",
    } <= set(attempt_columns.keys())


def test_payout_table_shares_the_target_metadata() -> None:
    assert "payouts" in Base.metadata.tables


def test_fulfillment_outbox_shares_the_target_metadata() -> None:
    assert {
        "fulfillment_jobs",
        "fulfillment_job_attempts",
    } <= set(Base.metadata.tables)
    columns = Base.metadata.tables["fulfillment_jobs"].c
    assert {
        "order_id",
        "source_payment_attempt_id",
        "kind",
        "status",
        "available_at",
    } <= set(columns.keys())


def test_cdek_shipment_foundation_shares_the_target_metadata() -> None:
    assert {
        "cdek_shipments",
        "cdek_shipment_attempts",
        "cdek_shipment_events",
    } <= set(Base.metadata.tables)
    item_columns = Base.metadata.tables["order_items"].c
    assert {
        "delivery_weight_kg_snapshot",
        "delivery_height_cm_snapshot",
        "delivery_width_cm_snapshot",
        "delivery_length_cm_snapshot",
    } <= set(item_columns.keys())
    shipment_columns = Base.metadata.tables["cdek_shipments"].c
    assert {
        "order_id",
        "source_fulfillment_job_id",
        "source_payment_attempt_id",
        "client_order_number",
        "request_sha256",
        "request_ciphertext",
        "provider_uuid",
        "provider_cdek_number",
    } <= set(shipment_columns.keys())


def test_crm_paid_order_intake_shares_the_target_metadata() -> None:
    assert {
        "crm_order_projects",
        "crm_production_units",
        "crm_project_events",
    } <= set(Base.metadata.tables)
    project_columns = Base.metadata.tables["crm_order_projects"].c
    assert {
        "order_id",
        "source_fulfillment_job_id",
        "source_payment_attempt_id",
        "order_version_snapshot",
        "items_count",
        "units_count",
        "total_price_snapshot",
        "payment_succeeded_at_snapshot",
    } <= set(project_columns.keys())


def test_crm_reference_data_shares_the_target_metadata() -> None:
    assert {
        "crm_fabrics",
        "crm_garment_models",
        "crm_garment_sizes",
        "crm_catalog_product_model_links",
        "crm_tech_cards",
        "crm_tech_card_revisions",
        "crm_tech_card_checkpoints",
        "crm_reference_events",
    } <= set(Base.metadata.tables)
    revision_columns = Base.metadata.tables["crm_tech_card_revisions"].c
    assert {
        "tech_card_id",
        "revision_number",
        "based_on_revision_id",
        "status",
        "published_by_user_id",
        "published_at",
    } <= set(revision_columns.keys())


def test_crm_production_workflow_shares_the_target_metadata() -> None:
    assert {
        "crm_production_plan_revisions",
        "crm_production_unit_events",
    } <= set(Base.metadata.tables)
    unit_columns = Base.metadata.tables["crm_production_units"].c
    assert {"version", "started_at", "closed_at"} <= set(unit_columns.keys())


def test_crm_material_ledger_shares_the_target_metadata() -> None:
    assert {"crm_material_balances", "crm_material_reservations", "crm_material_movements"} <= set(
        Base.metadata.tables
    )


def test_crm_private_file_attachments_share_the_target_metadata() -> None:
    assert {
        "crm_file_attachments",
        "crm_file_access_events",
    } <= set(Base.metadata.tables)


def test_crm_staff_command_tables_share_the_target_metadata() -> None:
    assert {
        "crm_assignment_events",
        "crm_staff_commands",
    } <= set(Base.metadata.tables)
