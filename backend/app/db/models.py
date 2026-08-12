"""Import all refactored ORM models so Alembic sees one metadata graph."""

from app.modules.carts.models import Cart, CartItem, CartMigrationRun
from app.modules.catalog.models import (
    CatalogAuditEvent,
    CatalogContentMigrationRun,
    CatalogDocument,
    CatalogDocumentRevision,
    CatalogMigrationRun,
    Product,
    ProductVariant,
)
from app.modules.crm.command_models import CrmAssignmentEvent, CrmStaffCommand
from app.modules.crm.file_models import CrmFileAccessEvent, CrmFileAttachment
from app.modules.crm.material_models import (
    CrmMaterialBalance,
    CrmMaterialMovement,
    CrmMaterialReservation,
)
from app.modules.crm.models import CrmOrderProject, CrmProductionUnit, CrmProjectEvent
from app.modules.crm.production_models import (
    CrmProductionPlanRevision,
    CrmProductionUnitEvent,
)
from app.modules.crm.reference_models import (
    CrmCatalogProductModelLink,
    CrmFabric,
    CrmGarmentModel,
    CrmGarmentSize,
    CrmReferenceEvent,
    CrmTechCard,
    CrmTechCardCheckpoint,
    CrmTechCardRevision,
)
from app.modules.delivery.models import CdekShipment, CdekShipmentAttempt, CdekShipmentEvent
from app.modules.fulfillment.models import FulfillmentJob, FulfillmentJobAttempt
from app.modules.identity.models import (
    IdentityMigrationRun,
    OtpChallenge,
    Permission,
    RefreshSession,
    Role,
    RolePermission,
    SecurityAuditEvent,
    User,
    UserRole,
)
from app.modules.inventory.models import InventoryReservation
from app.modules.media.models import MediaObject, ProductMedia, ProductVariantMedia
from app.modules.notifications.models import NotificationDeliveryAttempt, NotificationOutbox
from app.modules.orders.models import (
    LegacyOrderClaim,
    LegacyOrderImport,
    Order,
    OrderCreationRequest,
    OrderGuestAccess,
    OrderItem,
    OrderMigrationRun,
    OrderStatusHistory,
)
from app.modules.payments.models import (
    Payment,
    PaymentAttempt,
    PaymentEvent,
    PaymentReconciliationJob,
)

__all__ = [
    "CrmOrderProject",
    "CrmProductionUnit",
    "CrmProjectEvent",
    "CrmFabric",
    "CrmGarmentModel",
    "CrmGarmentSize",
    "CrmCatalogProductModelLink",
    "CrmTechCard",
    "CrmTechCardRevision",
    "CrmTechCardCheckpoint",
    "CrmReferenceEvent",
    "CrmProductionPlanRevision",
    "CrmProductionUnitEvent",
    "CrmMaterialBalance",
    "CrmMaterialReservation",
    "CrmMaterialMovement",
    "CrmFileAttachment",
    "CrmFileAccessEvent",
    "CrmAssignmentEvent",
    "CrmStaffCommand",
    "MediaObject",
    "CdekShipment",
    "CdekShipmentAttempt",
    "CdekShipmentEvent",
    "FulfillmentJob",
    "FulfillmentJobAttempt",
    "NotificationDeliveryAttempt",
    "NotificationOutbox",
    "CatalogMigrationRun",
    "Cart",
    "CartItem",
    "CartMigrationRun",
    "CatalogAuditEvent",
    "CatalogContentMigrationRun",
    "CatalogDocument",
    "CatalogDocumentRevision",
    "IdentityMigrationRun",
    "InventoryReservation",
    "LegacyOrderClaim",
    "LegacyOrderImport",
    "Order",
    "OrderCreationRequest",
    "OrderGuestAccess",
    "OrderItem",
    "OrderMigrationRun",
    "OrderStatusHistory",
    "Payment",
    "PaymentAttempt",
    "PaymentEvent",
    "PaymentReconciliationJob",
    "Product",
    "ProductMedia",
    "ProductVariant",
    "ProductVariantMedia",
    "OtpChallenge",
    "Permission",
    "RefreshSession",
    "Role",
    "RolePermission",
    "SecurityAuditEvent",
    "User",
    "UserRole",
]
