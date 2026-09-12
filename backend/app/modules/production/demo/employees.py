import json
import os

from sqlalchemy import select

from app.modules.identity.models import RoleName, SecurityAuditEvent, User, UserRole
from app.modules.identity.repository import IdentityRepository
from app.modules.production.auth_models import ProductionCredential
from app.modules.production.auth_service import code_digest, issue_code
from app.modules.production.models import ProductionDemoEmployee

STATIONS = {
    "tech": "Технолог",
    "kit": "Комплектовщик",
    "cut": "Раскрой",
    "dtf": "DTF печать",
    "workshop": "Цех",
    "application": "Нанесение",
    "sewing": "Пошив",
    "press": "ВТО",
    "qc": "ОТК",
    "packing": "Упаковка",
    "shipping": "Отгрузка",
}


async def ensure_employees(database, credentials_file):
    """Do not rotate existing codes or take over pre-existing real accounts."""
    pending = credentials_file.with_suffix(".pending")
    source = pending if pending.exists() else credentials_file
    saved = json.loads(source.read_text()) if source.exists() else {}
    result = {}
    pepper = database.settings.require_secret("identity_otp_pepper", "IDENTITY_OTP_PEPPER")
    async with database.session() as session:
        repo = IdentityRepository()
        await repo.ensure_system_authorization(session)
        for station, label in STATIONS.items():
            email = f"production-demo-{station}@garment-buro.invalid"
            marker = await session.scalar(
                select(ProductionDemoEmployee).where(ProductionDemoEmployee.station == station)
            )
            if marker:
                user = await session.get(User, marker.user_id)
            else:
                if await session.scalar(select(User.id).where(User.email_normalized == email)):
                    raise ValueError(
                        "Demo email occupied by an unmarked account; refusing takeover"
                    )
                user = User(email=email, email_normalized=email, first_name=f"Демо · {label}")
                session.add(user)
                await session.flush()
                session.add(ProductionDemoEmployee(user_id=user.id, station=station))
                role = await repo.get_role(session, RoleName(f"production_{station}"))
                session.add(UserRole(user_id=user.id, role_id=role.id))
                session.add(
                    SecurityAuditEvent(
                        event_type="production.demo_employee_created",
                        subject_user_id=user.id,
                        details={"station": station},
                    )
                )
                await session.flush()
            credential = await session.scalar(
                select(ProductionCredential).where(
                    ProductionCredential.user_id == user.id, ProductionCredential.active.is_(True)
                )
            )
            if credential:
                code = saved.get(station, {}).get("code", "")
                if (
                    credential.station != station
                    or not code
                    or credential.code_digest != code_digest(code, pepper)
                ):
                    raise ValueError(
                        "Existing demo code missing from private file; no rotation performed"
                    )
            else:
                if marker:
                    raise ValueError("Demo employee was revoked; do not silently re-enable access")
                code = await issue_code(session, user_id=user.id, station=station, pepper=pepper)
            result[station] = {"user_id": user.id, "name": label, "code": code}
        credentials_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if pending.exists():
            # A committed previous run interrupted before rename is now fully validated.
            pending.replace(credentials_file)
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            json.dump(result, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        await session.commit()
        pending.replace(credentials_file)
    return result
