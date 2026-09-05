from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from anyio import to_thread
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.legacy_admin import router as retired_legacy_admin_router
from app.api.system import router as system_router
from app.core.config import Settings, get_settings
from app.db.session import DatabaseManager
from app.integrations.minio import MinioStorage
from app.modules.carts.cutover import verify_cart_cutover
from app.modules.carts.router import router as cart_router
from app.modules.catalog.content import verify_catalog_content_cutover
from app.modules.catalog.content_router import router as catalog_content_router
from app.modules.catalog.cutover import verify_catalog_cutover
from app.modules.catalog.router import router as catalog_router
from app.modules.catalog.router import variant_write_router
from app.modules.catalog.router import write_router as catalog_write_router
from app.modules.checkout.router import router as checkout_router
from app.modules.checkout.service import CheckoutService
from app.modules.crm.command_service import CrmStaffCommandService
from app.modules.crm.file_router import router as crm_file_router
from app.modules.crm.file_service import CrmFileService
from app.modules.crm.material_service import CrmMaterialService
from app.modules.crm.read_service import CrmReadService
from app.modules.crm.router import router as crm_router
from app.modules.crm.router import write_router as crm_write_router
from app.modules.delivery.directory import PickupDirectory
from app.modules.delivery.directory_router import router as pickup_directory_router
from app.modules.delivery.provider import AiohttpCdekTransport, CdekProviderClient
from app.modules.delivery.quote_router import router as cdek_quote_router
from app.modules.delivery.quote_service import CdekQuoteService
from app.modules.identity.cutover import verify_identity_cutover
from app.modules.identity.factory import build_identity_service
from app.modules.identity.router import router as identity_router
from app.modules.identity.service import IdentityService
from app.modules.media.router import router as media_router
from app.modules.media.router import write_router as media_write_router
from app.modules.notifications.factory import build_notification_outbox_service
from app.modules.notifications.service import NotificationOutboxService
from app.modules.orders.cutover import verify_order_read_cutover
from app.modules.orders.legacy import LegacyOrderReader
from app.modules.orders.router import guest_router as order_guest_router
from app.modules.orders.router import router as order_router
from app.modules.orders.service import (
    OrderGuestAccessService,
    OrderLifecycleService,
    OrderOwnershipBridgeService,
    TargetOrderReadService,
)
from app.modules.partners.router import admin_router as partner_admin_router
from app.modules.partners.router import partner_router
from app.modules.partners.router import public_router as partner_public_router
from app.modules.partners.service import PartnerProgramService
from app.modules.payments.creation import PaymentCreationService
from app.modules.payments.operation_router import router as payment_operation_router
from app.modules.payments.operation_service import PaymentOperationService
from app.modules.payments.provider import AiohttpYooKassaTransport, YooKassaProviderClient
from app.modules.payments.retry import PaymentRetryService
from app.modules.payments.retry_router import router as payment_retry_router
from app.modules.payments.router import router as payment_webhook_router
from app.modules.payments.service import PaymentService
from app.modules.payouts.provider import (
    AiohttpYooKassaPayoutTransport,
    YooKassaPayoutProviderClient,
)
from app.modules.payouts.router import router as payout_router
from app.modules.payouts.service import PayoutService
from app.modules.qr_codes.router import router as qr_code_router
from app.modules.qr_codes.service import QrCodeService


def create_app(
    *,
    settings: Settings | None = None,
    legacy_app: FastAPI | None = None,
    database: DatabaseManager | None = None,
    storage: MinioStorage | None = None,
    identity_service: IdentityService | None = None,
    notification_outbox_service: NotificationOutboxService | None = None,
    order_bridge_service: OrderOwnershipBridgeService | None = None,
    target_order_read_service: TargetOrderReadService | None = None,
    order_guest_access_service: OrderGuestAccessService | None = None,
    payment_service: PaymentService | None = None,
    checkout_service: CheckoutService | None = None,
    payment_retry_service: PaymentRetryService | None = None,
    payment_operation_service: PaymentOperationService | None = None,
    payout_service: PayoutService | None = None,
    crm_read_service: CrmReadService | None = None,
    crm_command_service: CrmStaffCommandService | None = None,
    crm_material_service: CrmMaterialService | None = None,
    crm_file_service: CrmFileService | None = None,
    cdek_quote_service: CdekQuoteService | None = None,
    partner_program_service: PartnerProgramService | None = None,
    qr_code_service: QrCodeService | None = None,
) -> FastAPI:
    runtime_settings = settings or get_settings()
    database_manager = database or DatabaseManager(runtime_settings)
    storage_manager = storage or MinioStorage(runtime_settings)
    identity_manager = identity_service
    notification_manager = notification_outbox_service
    order_bridge_manager = order_bridge_service
    target_order_read_manager = target_order_read_service
    order_guest_access_manager = order_guest_access_service
    payment_manager = payment_service
    checkout_manager = checkout_service
    payment_retry_manager = payment_retry_service
    payment_operation_manager = payment_operation_service
    payout_manager = payout_service
    crm_read_manager = crm_read_service
    crm_command_manager = crm_command_service
    crm_material_manager = crm_material_service
    crm_file_manager = crm_file_service
    cdek_quote_manager = cdek_quote_service
    partner_program_manager = partner_program_service
    qr_code_manager = qr_code_service or QrCodeService(runtime_settings)
    payment_transport: AiohttpYooKassaTransport | None = None
    payout_transport: AiohttpYooKassaPayoutTransport | None = None
    cdek_quote_transport: AiohttpCdekTransport | None = None

    if runtime_settings.partner_program_enabled:
        partner_program_manager = partner_program_manager or PartnerProgramService(runtime_settings)
    if (
        runtime_settings.payment_webhook_v2_enabled
        or runtime_settings.checkout_v2_enabled
        or runtime_settings.payment_management_enabled
    ):
        payment_manager = payment_manager or PaymentService(runtime_settings)
    if runtime_settings.checkout_v2_enabled or runtime_settings.payment_management_enabled:
        payment_transport = AiohttpYooKassaTransport(runtime_settings)
    if runtime_settings.checkout_v2_enabled and checkout_manager is None:
        if payment_manager is None:
            raise RuntimeError("Payment service was not initialized")
        if payment_transport is None:
            raise RuntimeError("YooKassa payment transport was not initialized")
        provider = YooKassaProviderClient(payment_transport)
        payment_creation = PaymentCreationService(
            runtime_settings,
            provider,
            payment_service=payment_manager,
            order_lifecycle=OrderLifecycleService(
                runtime_settings,
                partner_program_service=partner_program_manager,
            ),
        )
        checkout_manager = CheckoutService(
            runtime_settings,
            payment_creation,
            payment_service=payment_manager,
            partner_program_service=partner_program_manager,
        )
    if runtime_settings.checkout_v2_enabled and payment_retry_manager is None:
        if checkout_manager is None:
            raise RuntimeError("Checkout service was not initialized")
        payment_retry_manager = PaymentRetryService(
            runtime_settings,
            checkout_manager.payment_creation_service,
            payment_service=checkout_manager.payment_service,
        )
    if runtime_settings.payment_management_enabled and payment_operation_manager is None:
        if payment_manager is None or payment_transport is None:
            raise RuntimeError("Payment management dependencies were not initialized")
        payment_operation_manager = PaymentOperationService(
            runtime_settings,
            YooKassaProviderClient(payment_transport),
            payment_service=payment_manager,
            order_lifecycle=OrderLifecycleService(
                runtime_settings,
                partner_program_service=partner_program_manager,
            ),
        )
    if runtime_settings.yookassa_payouts_enabled and payout_manager is None:
        payout_transport = AiohttpYooKassaPayoutTransport(runtime_settings)
        payout_manager = PayoutService(
            runtime_settings,
            YooKassaPayoutProviderClient(payout_transport),
        )
    if runtime_settings.identity_api_enabled:
        identity_manager = identity_manager or build_identity_service(runtime_settings)
        notification_manager = notification_manager or build_notification_outbox_service(
            runtime_settings
        )
        if runtime_settings.order_reads_enabled:
            target_order_read_manager = target_order_read_manager or TargetOrderReadService(
                identity_manager.otp_security
            )
            order_guest_access_manager = order_guest_access_manager or OrderGuestAccessService(
                runtime_settings
            )
        else:
            order_bridge_manager = order_bridge_manager or OrderOwnershipBridgeService(
                LegacyOrderReader(runtime_settings.legacy_database_url),
                identity_manager.otp_security,
            )
    if runtime_settings.crm_api_enabled:
        crm_read_manager = crm_read_manager or CrmReadService()
    if runtime_settings.crm_writes_enabled:
        crm_command_manager = crm_command_manager or CrmStaffCommandService()
        crm_material_manager = crm_material_manager or CrmMaterialService()
    if runtime_settings.crm_files_enabled:
        crm_file_manager = crm_file_manager or CrmFileService(storage_manager)
    if runtime_settings.cdek_quote_enabled and cdek_quote_manager is None:
        cdek_quote_transport = AiohttpCdekTransport(runtime_settings)
        cdek_quote_manager = CdekQuoteService(
            runtime_settings,
            CdekProviderClient(cdek_quote_transport),
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await database_manager.startup()
        directory_task = None
        if (
            database_manager.enabled
            and runtime_settings.cdek_client_id
            and runtime_settings.cdek_client_secret
        ):
            directory_task = asyncio.create_task(
                PickupDirectory(database_manager, runtime_settings).run()
            )
        try:
            if runtime_settings.catalog_reads_enabled:
                await verify_catalog_cutover(
                    database_manager,
                    runtime_settings.catalog_migration_fingerprint or "",
                    allow_mutations=runtime_settings.catalog_writes_enabled,
                )
            if runtime_settings.identity_api_enabled:
                await verify_identity_cutover(
                    database_manager,
                    runtime_settings.identity_migration_fingerprint or "",
                )
                if runtime_settings.order_reads_enabled:
                    if target_order_read_manager is None:
                        raise RuntimeError("Target order read service was not initialized")
                    if order_guest_access_manager is None:
                        raise RuntimeError("Order guest access service was not initialized")
                    await verify_order_read_cutover(
                        database_manager,
                        runtime_settings.order_migration_fingerprint or "",
                    )
                else:
                    if order_bridge_manager is None:
                        raise RuntimeError("Identity order bridge was not initialized")
                    await to_thread.run_sync(order_bridge_manager.reader.validate)
            if runtime_settings.catalog_writes_enabled:
                await verify_catalog_content_cutover(
                    database_manager,
                    runtime_settings.catalog_content_migration_fingerprint or "",
                )
            if runtime_settings.carts_v2_enabled:
                await verify_cart_cutover(
                    database_manager,
                    runtime_settings.carts_migration_fingerprint or "",
                )
            await storage_manager.startup()
            try:
                try:
                    if payment_transport is not None:
                        await payment_transport.startup()
                    if payout_transport is not None:
                        await payout_transport.startup()
                    if cdek_quote_transport is not None:
                        await cdek_quote_transport.startup()
                    if legacy_app is None:
                        yield
                    else:
                        async with legacy_app.router.lifespan_context(legacy_app):
                            yield
                finally:
                    if payment_transport is not None:
                        await payment_transport.shutdown()
                    if payout_transport is not None:
                        await payout_transport.shutdown()
                    if cdek_quote_transport is not None:
                        await cdek_quote_transport.shutdown()
            finally:
                await storage_manager.shutdown()
        finally:
            if directory_task is not None:
                directory_task.cancel()
                with suppress(asyncio.CancelledError):
                    await directory_task
            await database_manager.shutdown()

    application = FastAPI(
        title=runtime_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = runtime_settings
    application.state.database = database_manager
    application.state.storage = storage_manager
    application.state.identity_service = identity_manager
    application.state.notification_outbox_service = notification_manager
    application.state.order_bridge_service = (
        target_order_read_manager if runtime_settings.order_reads_enabled else order_bridge_manager
    )
    application.state.target_order_read_service = target_order_read_manager
    application.state.order_guest_access_service = order_guest_access_manager
    application.state.payment_service = payment_manager
    application.state.checkout_service = checkout_manager
    application.state.payment_retry_service = payment_retry_manager
    application.state.payment_operation_service = payment_operation_manager
    application.state.payout_service = payout_manager
    application.state.crm_read_service = crm_read_manager
    application.state.crm_command_service = crm_command_manager
    application.state.crm_material_service = crm_material_manager
    application.state.crm_file_service = crm_file_manager
    application.state.cdek_quote_service = cdek_quote_manager
    application.state.partner_program_service = partner_program_manager
    application.state.qr_code_service = qr_code_manager

    application.add_middleware(
        CORSMiddleware,
        allow_origins=runtime_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(system_router)
    application.include_router(pickup_directory_router)
    application.include_router(qr_code_router)
    if runtime_settings.catalog_reads_enabled:
        application.include_router(catalog_router)
        application.include_router(media_router)
    if runtime_settings.catalog_writes_enabled:
        application.include_router(catalog_write_router)
        application.include_router(variant_write_router)
        application.include_router(media_write_router)
        application.include_router(catalog_content_router)
        application.include_router(retired_legacy_admin_router)
    if runtime_settings.carts_v2_enabled:
        application.include_router(cart_router)
    if runtime_settings.identity_api_enabled:
        application.include_router(identity_router)
    if runtime_settings.order_reads_enabled:
        application.include_router(order_router)
        application.include_router(order_guest_router)
    if runtime_settings.checkout_v2_enabled:
        application.include_router(checkout_router)
        application.include_router(payment_retry_router)
    if runtime_settings.payment_webhook_v2_enabled:
        application.include_router(payment_webhook_router)
    if runtime_settings.payment_management_enabled:
        application.include_router(payment_operation_router)
    if runtime_settings.yookassa_payouts_enabled:
        application.include_router(payout_router)
    if runtime_settings.crm_api_enabled:
        application.include_router(crm_router)
    if runtime_settings.crm_writes_enabled:
        application.include_router(crm_write_router)
    if runtime_settings.crm_files_enabled:
        application.include_router(crm_file_router)
    if runtime_settings.cdek_quote_enabled:
        application.include_router(cdek_quote_router)
    if runtime_settings.partner_program_enabled:
        application.include_router(partner_public_router)
        application.include_router(partner_router)
        application.include_router(partner_admin_router)

    if legacy_app is not None:
        legacy_app.state.checkout_database = database_manager
        application.mount("/", legacy_app, name="legacy")

    return application
