"""Document manually streamed JSON bodies without unresolved model references."""

from pydantic import BaseModel


def json_request_schema(model: type[BaseModel], *, path: str) -> dict[str, object]:
    # JSON References resolve from the OpenAPI document root, not from the
    # schema's nested $defs. Keep definitions local to their request body.
    pointer = path.replace("~", "~0").replace("/", "~1")
    return model.model_json_schema(
        ref_template=(
            f"#/paths/{pointer}/post/requestBody/content/application~1json/schema/$defs/{{model}}"
        )
    )
