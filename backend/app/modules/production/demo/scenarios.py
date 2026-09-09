from sqlalchemy import select

from app.modules.crm.file_models import CrmFileRole
from app.modules.identity.models import SecurityAuditEvent
from app.modules.production.schemas import ProductionCommand
from app.modules.production.service import ProductionService


async def prepare_scenario(database, files, project_id, unit_id, station, actor, size, card, image):
    marker = f"production.demo_ready.{project_id}"
    async with database.session() as session:
        if await session.scalar(
            select(SecurityAuditEvent.id).where(SecurityAuditEvent.event_type == marker)
        ):
            return  # Never reset a scenario that people have already used.
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
        spec = dict(
            tech_card_revision_id=card,
            garment_size_id=size,
            route=["cut", "application", "sewing", "press", "qc", "packing"],
            components=[
                dict(
                    key="fabric", name="Учебный футер", quantity="2", unit="м", location="DEMO-01"
                ),
                dict(
                    key="thread", name="Учебная нить", quantity="1", unit="шт", location="DEMO-02"
                ),
            ],
            pattern_file_ids=attachment_ids[:1],
            print_file_ids=attachment_ids[1:],
            instructions="ТЕСТ. Не производить и не отправлять. Файлы — фото для проверки интерфейса, не лекала и не печатные оригиналы.",
            quality_checks=["Учебная проверка швов", "Учебная проверка нанесения"],
        )
        commands = [dict(action="plan", unit_id=unit_id, specification=spec)]
        if station != "tech":
            commands += [dict(action="confirm_documents", unit_id=unit_id), dict(action="release")]
        if station not in {"tech", "kit"}:
            commands += [
                dict(action="check_component", unit_id=unit_id, component_key=key, checked=True)
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
                ),
                dict(action="return_to_dtf"),
            ]
        if station not in {"tech", "kit", "cut", "dtf"}:
            commands += [
                dict(action="dtf_ready", unit_id=unit_id),
                dict(action="insert_dtf", unit_id=unit_id),
                dict(action="send_bag"),
            ]
            remaining = ["application", "sewing", "press", "qc", "packing", "shipping"]
            for stage in remaining[: remaining.index(station)]:
                commands.append(
                    dict(
                        action="complete_stage",
                        unit_id=unit_id,
                        stage=stage,
                        quality_confirmed=[0, 1] if stage == "qc" else [],
                    )
                )
            if station == "shipping":
                commands.append(dict(action="pack_bag"))
        service = ProductionService(database.settings)
        for version, payload in enumerate(commands):
            await service.execute(
                session,
                project_id=project_id,
                actor_id=actor,
                key=f"demo-v1:{project_id}:{version}",
                command=ProductionCommand(expected_version=version, **payload),
            )
        session.add(
            SecurityAuditEvent(
                event_type=marker,
                actor_user_id=actor,
                details={"project_id": project_id, "initial_station": station},
            )
        )
        await session.commit()
