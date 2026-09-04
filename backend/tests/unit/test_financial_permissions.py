from app.modules.identity.models import SYSTEM_ROLE_PERMISSIONS, PermissionCode, RoleName


def test_financial_permissions_follow_least_privilege() -> None:
    manager_permissions = set(SYSTEM_ROLE_PERMISSIONS[RoleName.MANAGER])
    admin_permissions = set(SYSTEM_ROLE_PERMISSIONS[RoleName.ADMIN])

    assert PermissionCode.PAYMENTS_MANAGE in manager_permissions
    assert PermissionCode.PAYOUTS_MANAGE not in manager_permissions
    assert {PermissionCode.PAYMENTS_MANAGE, PermissionCode.PAYOUTS_MANAGE} <= admin_permissions
