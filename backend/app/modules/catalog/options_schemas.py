from pydantic import BaseModel, ConfigDict, Field, field_validator


class ColorOption(BaseModel):
    model_config = ConfigDict(extra="ignore")

    label: str = Field(min_length=1, max_length=255)
    hex: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class VariantOptions(BaseModel):
    model_config = ConfigDict(extra="ignore")

    colors: list[ColorOption] = Field(max_length=100)
    sizes: list[str] = Field(max_length=100)

    @field_validator("sizes")
    @classmethod
    def validate_sizes(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value or len(value) > 32 for value in normalized):
            raise ValueError("Variant sizes must contain 1-32 characters")
        return normalized
