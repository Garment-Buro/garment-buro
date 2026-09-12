from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.modules.crm.models import CrmProductionUnit, CrmProductionUnitStatus, CrmProjectStatus
from app.modules.crm.production_service import CrmProductionService
from app.modules.crm.service import CrmProjectService
from app.modules.delivery.models import CdekShipment
from app.modules.orders.models import Order, OrderItem, OrderStatusHistory
from app.modules.orders.service import OrderLifecycleService
from app.modules.orders.workflow_repository import workflow_for_order
from app.modules.production.demo_access import require_demo_project
from app.modules.production.evidence import (
    ProductionConflict,
    ProductionNotFound,
    digest,
    order_evidence,
    validate_files,
    verify_specification,
)
from app.modules.production.models import (
    ProductionBag,
    ProductionEvent,
    ProductionSpecification,
    ProductionSpecificationFile,
    ProductionWorkItem,
)
from app.modules.production.repository import ProductionRepository
from app.modules.production.schemas import CommandReceipt, ProductionCommand
from app.modules.production.security import require_station, stations_for_user
from app.modules.production.unit_flow import apply_unit_flow


class ProductionService:
    def __init__(self, settings):
        self.settings = settings
        self.repository = ProductionRepository()
        self.units = CrmProductionService()
        self.projects = CrmProjectService()

    async def execute(
        self,
        session,
        *,
        project_id: int,
        actor_id: int,
        key: str,
        command: ProductionCommand,
        active_station: str | None = None,
    ):
        stations = await stations_for_user(session, actor_id)
        if active_station is not None:
            require_station(stations, active_station)
            stations = [active_station]
        await require_demo_project(session, actor_id, project_id)
        fingerprint = digest(
            {"actor": actor_id, "project": project_id, "command": command.model_dump(mode="json")}
        )
        project = await self.repository.project(session, project_id)
        if project is None:
            raise ProductionNotFound("Производственный заказ не найден")
        # Payment/order -> project -> unit: one lock order for every terminal command.
        order = await session.scalar(
            select(Order).where(Order.id == project.order_id).with_for_update()
        )
        project = await self.repository.project(session, project_id, lock=True)
        if order is not None and order.is_demo != project.is_demo:
            raise ProductionConflict("Учебный признак проекта не совпадает с исходным заказом")
        replay = await self.repository.event(session, key)
        if replay:
            if replay.command_digest != fingerprint:
                raise ProductionConflict("Ключ команды уже использован с другими параметрами")
            return CommandReceipt(project_id=project_id, version=replay.version, event_id=replay.id)
        allowed_order_states = {"processing"}
        if command.action == "dispatch":
            # Carrier polling may win the race with the shipping terminal acknowledgement.
            allowed_order_states |= {"shipped", "completed"}
        if (
            order is None
            or (not order.is_demo and order.payment_status != "paid")
            or order.status not in allowed_order_states
        ):
            raise ProductionConflict("Работа доступна только по оплаченному заказу в обработке")
        if project.status in {"cancelled", "on_hold"}:
            raise ProductionConflict("Производственный заказ остановлен")
        bag = await self.repository.bag(session, project_id)
        actual_version = bag.version if bag else 0
        if command.expected_version != actual_version:
            raise ProductionConflict("Заказ изменён другим сотрудником. Обновите экран")
        units = list(
            await session.scalars(
                select(CrmProductionUnit)
                .where(CrmProductionUnit.project_id == project_id)
                .order_by(CrmProductionUnit.id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        if len(units) != project.units_count or not units:
            raise ProductionConflict("Количество вещей не совпадает с оплаченным заказом")
        order_items = list(
            await session.scalars(select(OrderItem).where(OrderItem.order_id == order.id))
        )
        if Counter(x.order_item_id for x in units) != {x.id: x.quantity for x in order_items}:
            raise ProductionConflict(
                "Состав производственных вещей отличается от всех позиций заказа"
            )
        if bag is None:
            require_station(stations, "tech")
            if command.action != "plan" or any(x.status != "queued" for x in units):
                raise ProductionConflict(
                    "Сначала технолог должен подготовить заказ. Начатые CRM-проекты требуют отдельного переноса"
                )
            bag = ProductionBag(project_id=project_id, state="inbox", version=1)
            session.add(bag)
            await session.flush()
            session.add_all(ProductionWorkItem(bag_id=bag.id, unit_id=x.id) for x in units)
            await session.flush()
        work = await self.repository.work(session, bag.id)
        if {x.unit_id for x in work} != {x.id for x in units}:
            raise ProductionConflict("Состав мешка не совпадает с заказом")
        specs = await self.repository.specifications(session, work)
        unit = next((x for x in units if x.id == command.unit_id), None)
        item = next((x for x in work if x.unit_id == command.unit_id), None)
        now = datetime.now(timezone.utc)
        unit_actions = {
            "plan",
            "confirm_documents",
            "check_component",
            "dtf_ready",
            "insert_dtf",
            "complete_stage",
            "report_issue",
            "resolve_issue",
            "rework",
            "issue_unit_label",
            "send_unit",
            "complete_workshop",
            "set_dtf_deadline",
        }
        if command.action in unit_actions and (unit is None or item is None):
            raise ProductionConflict("Выберите вещь из этого мешка")
        if command.action == "plan":
            require_station(stations, "tech")
            if bag.state != "inbox" or command.specification is None:
                raise ProductionConflict("Спецификация меняется только до выпуска в работу")
            await self._plan(session, unit, item, command.specification, actor_id, now)
        else:
            # Preparing one item must not require every other item to be planned.
            evidence_rows = [item] if command.action in unit_actions else work
            if command.action in {"report_issue", "resolve_issue"}:
                evidence_rows = []  # A data-integrity problem must itself be reportable.
            for row in evidence_rows:
                spec = specs.get(row.specification_id)
                if spec is None:
                    raise ProductionConflict("Сначала заполните спецификации всех вещей")
                source_unit = next(x for x in units if x.id == row.unit_id)
                source = await session.get(OrderItem, source_unit.order_item_id)
                if source is None:
                    raise ProductionConflict("Отсутствует позиция исходного заказа")
                await verify_specification(session, source_unit, spec, source)
            await self._apply(
                session,
                bag,
                work,
                specs,
                units,
                unit,
                item,
                project,
                order,
                command,
                stations,
                actor_id,
            )
        bag.version = actual_version + 1
        event = ProductionEvent(
            bag_id=bag.id,
            version=bag.version,
            unit_id=command.unit_id,
            action=command.action,
            actor_user_id=actor_id,
            command_key=key,
            command_digest=fingerprint,
            evidence={
                "command": command.model_dump(mode="json"),
                "bag_state": bag.state,
                "specification_id": item.specification_id if item else None,
                "unit_lane": item.lane if item else None,
                "dtf_ready": item.dtf_ready if item else None,
                "dtf_inserted": item.dtf_inserted if item else None,
            },
            occurred_at=now,
        )
        session.add(event)
        await session.flush()
        receipt = CommandReceipt(project_id=project_id, version=bag.version, event_id=event.id)
        await session.commit()
        return receipt

    async def _plan(self, session, unit, work, payload, actor_id, now):
        source = await session.get(OrderItem, unit.order_item_id)
        if (
            source is None
            or not source.title_snapshot
            or not source.size_snapshot
            or not source.color_snapshot
        ):
            raise ProductionConflict("В заказе отсутствует название, размер или цвет изделия")
        decorations = (source.customization_snapshot or {}).get("decorations", [])
        if (
            isinstance(decorations, list)
            and any(
                isinstance(x, dict) and (x.get("categoryId") == "prints" or x.get("text"))
                for x in decorations
            )
            and not payload.print_file_ids
        ):
            raise ProductionConflict(
                "В заказе есть печать: закрепите оригиналы DTF и этап нанесения"
            )
        files = await validate_files(
            session,
            unit_id=unit.id,
            card_id=payload.tech_card_revision_id,
            pattern_ids=payload.pattern_file_ids,
            print_ids=payload.print_file_ids,
        )
        plan = await self.units.plan_unit(
            session,
            production_unit_id=unit.id,
            expected_version=unit.version,
            garment_size_id=payload.garment_size_id,
            tech_card_revision_id=payload.tech_card_revision_id,
            actor_user_id=actor_id,
            from_terminal=True,
        )
        number = await session.scalar(
            select(func.coalesce(func.max(ProductionSpecification.revision), 0)).where(
                ProductionSpecification.unit_id == unit.id
            )
        )
        evidence = order_evidence(source)
        specification = payload.model_dump(mode="json") | {"files": files}
        spec = ProductionSpecification(
            unit_id=unit.id,
            revision=number + 1,
            plan_id=plan.id,
            order_evidence=evidence,
            order_digest=digest(evidence),
            specification=specification,
            specification_digest=digest(specification),
            actor_user_id=actor_id,
            created_at=now,
        )
        session.add(spec)
        await session.flush()
        session.add_all(
            ProductionSpecificationFile(
                specification_id=spec.id,
                attachment_id=x["id"],
                role="pattern" if x["id"] in payload.pattern_file_ids else "print",
            )
            for x in files
        )
        work.specification_id = spec.id
        work.documents_confirmed = False
        work.component_checks = {}
        work.issue = None

    async def _apply(
        self, session, bag, work, specs, units, unit, item, project, order, command, stations, actor
    ):
        action = command.action
        if bag.flow_version == 2 and await apply_unit_flow(
            self, session, bag, work, specs, units, unit, item, project, command, stations, actor
        ):
            return
        active_spec = specs.get(item.specification_id) if item else None
        spec = active_spec.specification if active_spec else None
        if action == "confirm_documents":
            require_station(stations, "tech")
            self._state(bag, "inbox")
            item.documents_confirmed = True
        elif action == "release":
            require_station(stations, "tech")
            self._state(bag, "inbox")
            if any(not x.documents_confirmed or x.issue for x in work):
                raise ProductionConflict("Подтвердите лекала, QR и спецификации всех вещей")
            bag.state = "kitting"
        elif action == "check_component":
            require_station(stations, "kit")
            self._state(bag, "kitting")
            if (
                command.component_key not in {x["key"] for x in spec["components"]}
                or command.checked is None
            ):
                raise ProductionConflict("Неизвестная комплектующая")
            item.component_checks = item.component_checks | {command.component_key: command.checked}
        elif action == "send_bag":
            require_station(stations, "kit")
            self._state(bag, "kitting", "waiting_dtf")
            if any(x.issue for x in work):
                raise ProductionConflict("В мешке есть вещи с проблемой")
            if bag.state == "kitting":
                if any(
                    not all(
                        x.component_checks.get(c["key"])
                        for c in specs[x.specification_id].specification["components"]
                    )
                    for x in work
                ):
                    raise ProductionConflict("Не все комплектующие вложены в мешок")
                await self.projects.transition(
                    session,
                    project_id=project.id,
                    expected_version=project.version,
                    to_status=CrmProjectStatus.IN_PROGRESS,
                    reason_code="terminal_bag_released",
                    actor_user_id=actor,
                    from_terminal=True,
                )
                for row in units:
                    await self._unit_status(
                        session, row, CrmProductionUnitStatus.IN_PROGRESS, actor
                    )
            elif any(
                "application" in specs[x.specification_id].specification["route"]
                and not x.dtf_inserted
                for x in work
            ):
                raise ProductionConflict("Подтвердите вложение всех ожидаемых DTF")
            bag.state = "workshop"
        elif action == "dtf_ready":
            require_station(stations, "dtf")
            self._state(bag, "kitting", "workshop", "waiting_dtf")
            if not spec["print_file_ids"] or item.issue:
                raise ProductionConflict("Нет готовых файлов печати или есть проблема")
            item.dtf_ready = True
        elif action == "insert_dtf":
            require_station(stations, "kit")
            self._state(bag, "kitting", "waiting_dtf")
            if not item.dtf_ready:
                raise ProductionConflict("DTF ещё не готов у печатника")
            item.dtf_inserted = True
        elif action == "complete_stage":
            self._state(bag, "workshop")
            route = spec["route"]
            if item.stage_index >= len(route) or command.stage != route[item.stage_index]:
                raise ProductionConflict("Нельзя пропустить участок или повторить завершённый этап")
            stage = route[item.stage_index]
            require_station(stations, stage)
            if item.issue:
                raise ProductionConflict("Сначала устраните проблему")
            if stage == "application" and not item.dtf_inserted:
                raise ProductionConflict("Нельзя наносить DTF до подтверждения вложения")
            if stage == "qc":
                if set(command.quality_confirmed) != set(range(len(spec["quality_checks"]))):
                    raise ProductionConflict("Подтвердите все проверки ОТК")
                if unit.status == "in_progress":
                    await self._unit_status(
                        session, unit, CrmProductionUnitStatus.QUALITY_CONTROL, actor
                    )
            if stage == "cut" and not command.note:
                raise ProductionConflict(
                    "Подтвердите, что крой завёрнут в подготовленный лист с QR"
                )
            item.stage_index += 1
            if item.stage_index == len(route):
                await self._unit_status(session, unit, CrmProductionUnitStatus.COMPLETED, actor)
        elif action == "return_to_dtf":
            require_station(stations, "kit")
            self._state(bag, "workshop")
            waiting = False
            for row in work:
                route = specs[row.specification_id].specification["route"]
                stage = route[row.stage_index] if row.stage_index < len(route) else None
                if stage == "application" and not row.dtf_inserted:
                    waiting = True
                elif stage in {"cut", "application", "sewing"}:
                    raise ProductionConflict(
                        "Сначала закончите доступный раскрой и пошив вещей в мешке"
                    )
            if not waiting:
                raise ProductionConflict("Нет вещей, ожидающих DTF")
            bag.state = "waiting_dtf"
        elif action == "report_issue":
            self._state(bag, "inbox", "kitting", "workshop", "waiting_dtf")
            if not command.note:
                raise ProductionConflict("Опишите проблему")
            allowed = (
                {"tech", "kit"}
                if bag.state != "workshop"
                else {"tech", "dtf", spec["route"][min(item.stage_index, len(spec["route"]) - 1)]}
            )
            if bag.flow_version == 2:
                allowed = {
                    "tech",
                    "dtf",
                    item.lane,
                    "kit" if item.lane == "waiting_dtf" else item.lane,
                }
            if not set(stations) & allowed:
                require_station(stations, "tech")
            item.issue = command.note
        elif action in {"resolve_issue", "rework"}:
            require_station(stations, "tech")
            self._state(bag, "inbox", "kitting", "workshop", "waiting_dtf")
            if not command.note or not item.issue:
                raise ProductionConflict("Нужны открытая проблема и описание решения")
            if action == "rework":
                if (
                    command.stage not in spec["route"]
                    or spec["route"].index(command.stage) > item.stage_index
                    or unit.status == "completed"
                ):
                    raise ProductionConflict(
                        "Некорректный этап переделки; закрытую вещь нельзя менять"
                    )
                item.stage_index = spec["route"].index(command.stage)
                if bag.flow_version == 2:
                    item.lane = "cut" if command.stage == "cut" else "kit"
                if command.stage in {"cut", "application"} and spec["print_file_ids"]:
                    item.dtf_ready = False
                    item.dtf_inserted = False
                if unit.status == "quality_control":
                    await self._unit_status(
                        session, unit, CrmProductionUnitStatus.IN_PROGRESS, actor
                    )
            item.issue = None
        elif action == "pack_bag":
            require_station(stations, "packing")
            self._state(bag, "workshop")
            if any(
                x.issue or x.stage_index != len(specs[x.specification_id].specification["route"])
                for x in work
            ):
                raise ProductionConflict("Все вещи должны пройти ОТК и упаковку")
            await self.projects.transition(
                session,
                project_id=project.id,
                expected_version=project.version,
                to_status=CrmProjectStatus.COMPLETED,
                reason_code="terminal_bag_packed",
                actor_user_id=actor,
                from_terminal=True,
            )
            bag.state = "packed"
        elif action == "dispatch":
            require_station(stations, "shipping")
            self._state(bag, "packed")
            if not command.tracking_number or not command.note:
                raise ProductionConflict("Укажите трек-номер и подтверждение передачи перевозчику")
            flow = await workflow_for_order(session, order.id)
            if flow is not None:
                shipment = await session.scalar(
                    select(CdekShipment).where(CdekShipment.order_id == order.id)
                )
                if (
                    shipment is None
                    or shipment.provider_uuid is None
                    or shipment.provider_cdek_number != command.tracking_number
                ):
                    raise ProductionConflict(
                        "Трек-номер должен совпадать с подтверждённым отправлением СДЭК этого заказа"
                    )
            if (
                not order.first_name
                or not order.phone
                or not order.delivery_city
                or not (order.delivery_address or order.cdek_point_code)
            ):
                raise ProductionConflict("Не заполнены данные получателя или доставки в заказе")
            if order.is_demo:
                if not command.tracking_number.startswith("DEMO-"):
                    raise ProductionConflict("Для учебной отгрузки используйте трек DEMO-…")
                previous = order.status
                order.status = "shipped"
                order.version += 1
                session.add(
                    OrderStatusHistory(
                        order_id=order.id,
                        version=order.version,
                        from_status=previous,
                        to_status="shipped",
                        reason_code="production.demo_dispatch",
                        actor_user_id=actor,
                    )
                )
            else:
                await OrderLifecycleService(self.settings).mark_shipped(
                    session, order_id=order.id, actor_user_id=actor
                )
            bag.tracking_number = command.tracking_number
            bag.state = "dispatched"

    async def _unit_status(self, session, unit, status, actor):
        await self.units.transition_unit(
            session,
            production_unit_id=unit.id,
            expected_version=unit.version,
            to_status=status,
            reason_code="terminal_stage_changed",
            actor_user_id=actor,
            from_terminal=True,
        )

    @staticmethod
    def _state(bag, *states):
        if bag.state not in states:
            raise ProductionConflict("Действие недоступно в текущем состоянии мешка")
