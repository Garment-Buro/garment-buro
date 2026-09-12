"""Physical handoffs per garment; caller owns order/project locks and event transaction."""

import secrets
from datetime import datetime, timedelta, timezone

from app.modules.crm.models import CrmProductionUnitStatus, CrmProjectStatus
from app.modules.identity.security import ensure_utc
from app.modules.production.evidence import ProductionConflict
from app.modules.production.security import require_station


def require_lane(item, *lanes):
    if item.lane not in lanes:
        raise ProductionConflict("Вещь уже передана на другой участок. Обновите мешок")
    if item.issue:
        raise ProductionConflict("Сначала устраните проблему вещи")


async def apply_unit_flow(
    service, session, bag, work, specs, units, unit, item, project, command, stations, actor
):
    action = command.action
    saved = specs.get(item.specification_id) if item else None
    spec = saved.specification if saved else None
    now = datetime.now(timezone.utc)
    if action == "release":
        require_station(stations, "tech")
        service._state(bag, "inbox")
        if any(not x.documents_confirmed or x.issue for x in work):
            raise ProductionConflict("Подтвердите техкарты всех вещей")
        await service.projects.transition(
            session,
            project_id=project.id,
            expected_version=project.version,
            to_status=CrmProjectStatus.IN_PROGRESS,
            reason_code="terminal_bag_released",
            actor_user_id=actor,
            from_terminal=True,
        )
        bag.public_token = secrets.token_urlsafe(32)
        bag.state = "workshop"
        for row in work:
            garment = next(u for u in units if u.id == row.unit_id)
            row.lane = "cut"
            if specs[row.specification_id].specification["print_file_ids"]:
                row.dtf_due_at = now + timedelta(hours=24)
            await service._unit_status(session, garment, CrmProductionUnitStatus.IN_PROGRESS, actor)
        return True
    if action in {"send_bag", "return_to_dtf"}:
        raise ProductionConflict("Передавайте каждый мешок изделия отдельно")
    if action in {
        "issue_unit_label",
        "set_dtf_deadline",
        "dtf_ready",
        "check_component",
        "insert_dtf",
        "send_unit",
        "complete_workshop",
        "complete_stage",
    }:
        service._state(bag, "workshop")
    if action == "issue_unit_label":
        require_station(stations, "cut")
        require_lane(item, "cut", "kit", "waiting_dtf")
        if item.public_token is None:
            item.public_token = secrets.token_urlsafe(32)
        return True
    if action == "set_dtf_deadline":
        if not set(stations) & {"tech", "dtf"}:
            require_station(stations, "dtf")
        if not spec["print_file_ids"] or item.dtf_ready:
            raise ProductionConflict("Нет ожидающего задания DTF")
        try:
            due = datetime.fromisoformat(command.due_at or "")
        except ValueError as error:
            raise ProductionConflict("Укажите срок DTF") from error
        if due.tzinfo is None or not now < ensure_utc(due) <= now + timedelta(days=30):
            raise ProductionConflict("Срок DTF должен быть в будущем, не далее 30 дней")
        item.dtf_due_at = due
        return True
    if action == "dtf_ready":
        require_station(stations, "dtf")
        require_lane(item, "kit", "waiting_dtf")
        if not spec["print_file_ids"] or item.dtf_ready:
            raise ProductionConflict("Нет ожидающей доставки DTF")
        item.dtf_ready = True
        item.lane = "kit"
        return True
    if action in {"check_component", "insert_dtf", "send_unit"}:
        require_station(stations, "kit")
        require_lane(item, "kit", "waiting_dtf")
        if action == "check_component":
            if (
                command.component_key not in {c["key"] for c in spec["components"]}
                or command.checked is None
            ):
                raise ProductionConflict("Неизвестная комплектующая")
            item.component_checks = item.component_checks | {command.component_key: command.checked}
        elif action == "insert_dtf":
            if not spec["print_file_ids"] or not item.dtf_ready:
                raise ProductionConflict("DTF ещё не доставлен")
            item.dtf_inserted = True
        else:
            if not item.public_token:
                raise ProductionConflict("Закройщик должен выпустить QR мешка изделия")
            if not all(item.component_checks.get(c["key"]) for c in spec["components"]):
                raise ProductionConflict("Не все комплектующие вложены в мешок изделия")
            if spec["print_file_ids"] and not item.dtf_inserted:
                raise ProductionConflict("Дождитесь DTF и подтвердите вложение")
            item.lane = "workshop"
        return True
    if action == "complete_workshop":
        require_station(stations, "workshop")
        require_lane(item, "workshop")
        if set(command.quality_confirmed) != set(range(len(spec["quality_checks"]))):
            raise ProductionConflict("Подтвердите качество и завершение ВТО")
        await service._unit_status(session, unit, CrmProductionUnitStatus.QUALITY_CONTROL, actor)
        item.stage_index = spec["route"].index("packing")
        item.lane = "packing"
        return True
    if action == "complete_stage":
        if command.stage == "cut":
            require_station(stations, "cut")
            require_lane(item, "cut")
            if not command.note or not item.public_token:
                raise ProductionConflict("Напечатайте QR и подтвердите мешок изделия")
            item.stage_index = spec["route"].index("cut") + 1 if "cut" in spec["route"] else 0
            item.lane = "waiting_dtf" if spec["print_file_ids"] and not item.dtf_ready else "kit"
        elif command.stage == "packing":
            require_station(stations, "packing")
            require_lane(item, "packing")
            await service._unit_status(session, unit, CrmProductionUnitStatus.COMPLETED, actor)
            item.stage_index = len(spec["route"])
            item.lane = "done"
        else:
            raise ProductionConflict("Нанесение, пошив и ВТО завершает общий цех")
        return True
    return False
