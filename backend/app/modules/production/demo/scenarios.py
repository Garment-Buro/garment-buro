from sqlalchemy import select

from app.modules.crm.file_models import CrmFileRole
from app.modules.identity.models import SecurityAuditEvent
from app.modules.production.models import ProductionBag
from app.modules.production.schemas import ProductionCommand
from app.modules.production.service import ProductionService


async def prepare_scenario(
    database, files, project_id, unit_ids, station, actor, size, card, image, station_actors
):
    marker = f"production.demo_ready.{project_id}"
    unit_ids = [unit_ids] if isinstance(unit_ids, int) else list(unit_ids)
    async with database.session() as session:
        if await session.scalar(
            select(SecurityAuditEvent.id).where(SecurityAuditEvent.event_type == marker)
        ):
            return  # Never reset a scenario that people have already used.
        specifications = {}
        for unit_id in unit_ids:
            attachment_ids = []
            for slot, label in enumerate(
                ("DEMO-photo-NOT-cutting-pattern.png", "DEMO-photo-NOT-print-original.png")
            ):
                upload = await files.upload(
                    session,
                    data=image,
                    original_filename=label,
                    role=CrmFileRole.PRODUCTION_EVIDENCE,
                    production_unit_id=unit_id,
                    sort_order=slot,
                    actor_user_id=actor,
                )
                attachment_ids.append(upload.attachment_id)
            specifications[unit_id] = dict(
                tech_card_revision_id=card,
                garment_size_id=size,
                route=["cut", "application", "sewing", "press", "qc", "packing"],
                components=[
                    dict(
                        key="fabric",
                        name="Учебный футер",
                        quantity="2",
                        unit="м",
                        location="DEMO-01",
                    ),
                    dict(
                        key="thread",
                        name="Учебная нить",
                        quantity="1",
                        unit="шт",
                        location="DEMO-02",
                    ),
                ],
                pattern_file_ids=attachment_ids[:1],
                print_file_ids=attachment_ids[1:],
                instructions=(
                    "ТЕСТ. Не производить и не отправлять. Файлы — фото для "
                    "проверки интерфейса, не лекала и не печатные оригиналы."
                ),
                quality_checks=["Учебная проверка швов", "Учебная проверка нанесения"],
            )
        commands = [
            dict(action="plan", unit_id=unit_id, specification=specifications[unit_id])
            for unit_id in unit_ids
        ]
        if station != "tech":
            commands += [dict(action="confirm_documents", unit_id=unit_id) for unit_id in unit_ids]
            commands += [dict(action="release")]
        if station not in {"tech", "kit"}:
            commands += [
                dict(action="check_component", unit_id=unit_id, component_key=key, checked=True)
                for unit_id in unit_ids
                for key in ("fabric", "thread")
            ]
            commands += [dict(action="send_bag")]
        if station not in {"tech", "kit", "cut"}:
            commands += [
                dict(
                    action="complete_stage",
                    unit_id=unit_id,
                    stage="cut",
                    note="Учебный крой и QR проверены",
                )
                for unit_id in unit_ids
            ]
            commands += [dict(action="return_to_dtf")]
        if station not in {"tech", "kit", "cut", "dtf", "workshop"}:
            commands += [
                dict(action=action, unit_id=unit_id)
                for unit_id in unit_ids
                for action in ("dtf_ready", "insert_dtf")
            ]
            commands += [dict(action="send_bag")]
            remaining = ["application", "sewing", "press", "qc", "packing", "shipping"]
            for stage in remaining[: remaining.index(station)]:
                commands += [
                    dict(
                        action="complete_stage",
                        unit_id=unit_id,
                        stage=stage,
                        quality_confirmed=[0, 1] if stage == "qc" else [],
                    )
                    for unit_id in unit_ids
                ]
            if station == "shipping":
                commands.append(dict(action="pack_bag"))
        service = ProductionService(database.settings)
        legacy = station in {"application", "sewing", "press", "qc"}
        if not legacy:
            commands = [
                dict(action="plan", unit_id=unit_id, specification=specifications[unit_id])
                for unit_id in unit_ids
            ]
            if station != "tech":
                commands += [
                    dict(action="confirm_documents", unit_id=unit_id) for unit_id in unit_ids
                ]
                commands += [
                    dict(action="approve_order", actor_station="tech"),
                    dict(action="approve_order", actor_station="dtf"),
                    dict(action="release"),
                ]
            if station not in {"tech", "cut"}:
                commands += [
                    dict(
                        action="complete_stage",
                        unit_id=unit_id,
                        stage="cut",
                        note="Учебный мешок изделия с QR",
                    )
                    for unit_id in unit_ids
                ]
            if station not in {"tech", "cut", "kit", "dtf"}:
                commands += [
                    dict(action=action, unit_id=unit_id)
                    for unit_id in unit_ids
                    for action in ("start_dtf", "dtf_ready", "insert_dtf")
                ]
                commands += [
                    dict(action="check_component", unit_id=unit_id, component_key=key, checked=True)
                    for unit_id in unit_ids
                    for key in ("fabric", "thread")
                ]
                commands += [dict(action="send_unit", unit_id=unit_id) for unit_id in unit_ids]
            if station in {"packing", "shipping"}:
                commands += [
                    dict(action="complete_workshop", unit_id=unit_id, quality_confirmed=[0, 1])
                    for unit_id in unit_ids
                ]
            if station == "shipping":
                commands += [
                    dict(action="complete_stage", unit_id=unit_id, stage="packing")
                    for unit_id in unit_ids
                ]
                commands += [dict(action="pack_bag")]
        for version, payload in enumerate(commands):
            action_station = payload.get("actor_station") or {
                "plan": "tech",
                "confirm_documents": "tech",
                "release": "tech",
                "check_component": "kit",
                "send_bag": "kit",
                "send_unit": "kit",
                "return_to_dtf": "kit",
                "insert_dtf": "kit",
                "dtf_ready": "dtf",
                "start_dtf": "dtf",
                "issue_unit_label": "cut",
                "complete_workshop": "workshop",
                "pack_bag": "packing",
            }.get(payload["action"], payload.get("stage"))
            command_actor = station_actors[action_station]
            await service.execute(
                session,
                project_id=project_id,
                actor_id=command_actor,
                key=f"demo-v1:{project_id}:{version}",
                command=ProductionCommand(
                    expected_version=version,
                    **{key: value for key, value in payload.items() if key != "actor_station"},
                ),
            )
            if legacy and version == 0:
                bag = await session.scalar(
                    select(ProductionBag).where(ProductionBag.project_id == project_id)
                )
                bag.flow_version = 1
                await session.commit()
        session.add(
            SecurityAuditEvent(
                event_type=marker,
                actor_user_id=actor,
                details={"project_id": project_id, "initial_station": station},
            )
        )
        await session.commit()
