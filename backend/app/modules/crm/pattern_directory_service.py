from app.modules.crm.directory_service import continuation, position
from app.modules.crm.pattern_directory_repository import PatternDirectoryRepository
from app.modules.crm.pattern_directory_schemas import (
    PatternContext,
    PatternCoverage,
    PatternFilePage,
    PatternModelPage,
    PatternSizePage,
)
from app.modules.crm.pattern_grid import GRID_STEP_CM, axis


class PatternGridChanged(ValueError):
    pass


class PatternDirectoryService:
    repository = PatternDirectoryRepository()

    async def page(self, session, kind, query):
        after_id, after_value = position(query, kind)
        read, schema = {
            "pattern-models": (self.repository.models, PatternModelPage),
            "patterns": (self.repository.files, PatternFilePage),
            "pattern-sizes": (self.repository.sizes, PatternSizePage),
        }[kind]
        rows = await read(session, query, after_id=after_id, after_value=after_value)
        return schema(items=rows[: query.limit], next_cursor=continuation(rows, query, kind))

    async def context(self, session, model_id, size_id):
        row = await self.repository.context(session, model_id, size_id)
        return PatternContext.model_validate(row) if row is not None else None

    async def editor(self, session, pattern_id):
        pattern = await self.repository.pattern(session, pattern_id)
        if pattern is None:
            return None
        row = await self.context(session, pattern["garment_model_id"], pattern["garment_size_id"])
        return (
            PatternContext.model_validate({**row.model_dump(), "pattern": pattern})
            if row is not None
            else None
        )

    async def coverage(self, session, model_id, query):
        context = await self.context(session, model_id, query.size_id)
        if context is None:
            return None
        size = context.size
        if query.expected_size_version is not None and (
            size is None or size.version != query.expected_size_version
        ):
            raise PatternGridChanged("Размер изменился. Обновите сетку.")
        widths, width_count, width_pages = axis(
            size.min_width_cm if size else None,
            size.max_width_cm if size else None,
            query.width_page,
        )
        lengths, length_count, length_pages = axis(
            size.min_length_cm if size else None,
            size.max_length_cm if size else None,
            query.length_page,
        )
        records, count = (
            await self.repository.window(session, model_id, size, widths, lengths)
            if size
            else ([], 0)
        )
        variants = int(size.allow_standard_sleeve) + int(size.allow_height_sleeve) if size else 0
        if len(
            {(row["width_cm"], row["length_cm"], row["sleeve_variant"]) for row in records}
        ) != len(records):
            raise ValueError("Pattern grid contains duplicate slots")
        return PatternCoverage.model_validate(
            {
                **context.model_dump(),
                "step_cm": GRID_STEP_CM,
                "width_values": widths,
                "length_values": lengths,
                "width_count": width_count,
                "length_count": length_count,
                "width_pages": width_pages,
                "length_pages": length_pages,
                "width_page": query.width_page,
                "length_page": query.length_page,
                "required_count": str(width_count * length_count * variants),
                "uploaded_count": count,
                "items": records,
            }
        )
