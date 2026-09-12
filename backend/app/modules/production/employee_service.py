from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.modules.identity.exceptions import InvalidEmailError
from app.modules.identity.models import Role, SecurityAuditEvent, User, UserRole
from app.modules.identity.security import normalize_email
from app.modules.production.auth_models import ProductionCredential, ProductionEmployee
from app.modules.production.auth_service import issue_code, revoke_code
from app.modules.production.employee_schemas import EmployeeWrite


class EmployeeNotFoundError(LookupError):
    pass


class EmployeeConflictError(ValueError):
    pass


class ProductionEmployeeService:
    @staticmethod
    def role_name(station: str) -> str:
        return f"production_{station}"

    async def create(self, session, *, payload: EmployeeWrite, actor_id: int, pepper: str):
        email, normalized = self._email(payload.email)
        user = User(
            internal_identity=f"employee:{uuid.uuid4().hex}",
            email=email,
            email_normalized=normalized,
            first_name=payload.first_name,
            last_name=payload.last_name or None,
            phone=payload.phone or None,
            status=payload.status,
        )
        session.add(user)
        try:
            await session.flush()
        except IntegrityError as error:
            raise EmployeeConflictError("Сотрудник с такой почтой уже существует") from error
        employee = ProductionEmployee(
            user_id=user.id,
            primary_station=payload.primary_station,
            availability=payload.availability,
            created_by_user_id=actor_id,
        )
        session.add(employee)
        await self._replace_roles(
            session, user_id=user.id, stations=payload.stations, actor_id=actor_id
        )
        code = None
        if payload.status == "active" and payload.availability == "available":
            code = await issue_code(
                session, user_id=user.id, station=payload.primary_station, pepper=pepper
            )
        session.add(
            SecurityAuditEvent(
                event_type="production.employee_created",
                actor_user_id=actor_id,
                subject_user_id=user.id,
                details={
                    "stations": payload.stations,
                    "primary_station": payload.primary_station,
                },
            )
        )
        await session.commit()
        return await self.get(session, user.id), code

    async def update(
        self, session, *, user_id: int, payload: EmployeeWrite, actor_id: int, pepper: str
    ):
        employee = await session.scalar(
            select(ProductionEmployee)
            .where(ProductionEmployee.user_id == user_id)
            .with_for_update()
        )
        user = await session.scalar(select(User).where(User.id == user_id).with_for_update())
        if employee is None or user is None:
            raise EmployeeNotFoundError()
        email, normalized = self._email(payload.email)
        primary_changed = employee.primary_station != payload.primary_station
        user.first_name = payload.first_name
        user.last_name = payload.last_name or None
        user.email = email
        user.email_normalized = normalized
        user.phone = payload.phone or None
        user.status = payload.status
        employee.primary_station = payload.primary_station
        employee.availability = payload.availability
        await self._replace_roles(
            session, user_id=user.id, stations=payload.stations, actor_id=actor_id
        )
        active_credential = await session.scalar(
            select(ProductionCredential).where(
                ProductionCredential.user_id == user.id,
                ProductionCredential.active.is_(True),
            )
        )
        code = None
        if payload.status == "blocked" or payload.availability != "available":
            await revoke_code(session, user_id=user.id)
        elif primary_changed or active_credential is None:
            code = await issue_code(
                session, user_id=user.id, station=payload.primary_station, pepper=pepper
            )
        try:
            await session.flush()
        except IntegrityError as error:
            raise EmployeeConflictError("Сотрудник с такой почтой уже существует") from error
        session.add(
            SecurityAuditEvent(
                event_type="production.employee_updated",
                actor_user_id=actor_id,
                subject_user_id=user.id,
                details={
                    "stations": payload.stations,
                    "primary_station": payload.primary_station,
                    "status": payload.status,
                    "availability": payload.availability,
                    "code_rotated": code is not None,
                },
            )
        )
        await session.commit()
        return await self.get(session, user.id), code

    async def rotate_code(self, session, *, user_id: int, actor_id: int, pepper: str):
        employee = await session.scalar(
            select(ProductionEmployee).where(ProductionEmployee.user_id == user_id)
        )
        user = await session.get(User, user_id)
        if employee is None or user is None:
            raise EmployeeNotFoundError()
        if user.status != "active" or employee.availability != "available":
            raise EmployeeConflictError("Сначала активируйте сотрудника")
        code = await issue_code(
            session, user_id=user.id, station=employee.primary_station, pepper=pepper
        )
        session.add(
            SecurityAuditEvent(
                event_type="production.employee_code_rotated",
                actor_user_id=actor_id,
                subject_user_id=user.id,
                details={"primary_station": employee.primary_station},
            )
        )
        await session.commit()
        return await self.get(session, user.id), code

    async def get(self, session, user_id: int):
        row = (
            await session.execute(
                select(ProductionEmployee, User)
                .join(User, User.id == ProductionEmployee.user_id)
                .where(ProductionEmployee.user_id == user_id)
            )
        ).first()
        if row is None:
            raise EmployeeNotFoundError()
        roles = list(
            await session.scalars(
                select(Role.name)
                .join(UserRole, UserRole.role_id == Role.id)
                .where(
                    UserRole.user_id == user_id,
                    Role.name.like("production_%"),
                    Role.name != "production_admin",
                )
                .order_by(Role.name)
            )
        )
        credential = await session.scalar(
            select(ProductionCredential)
            .where(
                ProductionCredential.user_id == user_id,
                ProductionCredential.active.is_(True),
            )
            .order_by(ProductionCredential.id.desc())
        )
        employee, user = row
        return {
            "id": user.id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "name": " ".join(x for x in (user.first_name, user.last_name) if x),
            "email": user.email,
            "phone": user.phone,
            "status": user.status,
            "availability": employee.availability,
            "created_at": employee.created_at,
            "stations": [role.removeprefix("production_") for role in roles],
            "primary_station": employee.primary_station,
            "code_active": credential is not None,
            "code_updated_at": credential.updated_at if credential else None,
        }

    async def _replace_roles(self, session, *, user_id: int, stations: list[str], actor_id: int):
        names = [self.role_name(station) for station in stations]
        roles = list(await session.scalars(select(Role).where(Role.name.in_(names))))
        if len(roles) != len(names):
            raise EmployeeConflictError("Производственные роли не инициализированы")
        production_roles = select(Role.id).where(
            Role.name.like("production_%"), Role.name != "production_admin"
        )
        await session.execute(
            delete(UserRole).where(
                UserRole.user_id == user_id, UserRole.role_id.in_(production_roles)
            )
        )
        for role in roles:
            session.add(UserRole(user_id=user_id, role_id=role.id, assigned_by_user_id=actor_id))
        await session.flush()

    @staticmethod
    def _email(value: str | None) -> tuple[str | None, str | None]:
        if not value:
            return None, None
        try:
            return normalize_email(value)
        except InvalidEmailError as error:
            raise EmployeeConflictError("Некорректная почта сотрудника") from error
