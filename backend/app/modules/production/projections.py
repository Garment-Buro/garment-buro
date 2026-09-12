"""Explicit floor projections. Never serialize order/payment/customer objects to QR viewers."""

CUSTOM_FIELDS = frozenset(
    "decorations side front back left right text fontFamily fontSize color width height position rotation size measurements type name fit modelImages selectedSize view widthCm heightCm lengthCm image content fontId canvas garment scale x y id src url points fontWeight letterSpacing lineHeight align modelId modelName selectedColor".split()
)
CUSTOM_FIELDS |= frozenset(
    "kind uid variantId categoryId originalWidth originalHeight sleeveMode lengthRange widthRange min max defaultValue comment".split()
)


def floor_customization(value):
    if isinstance(value, list):
        return [floor_customization(x) for x in value]
    if isinstance(value, dict):
        return {
            key: floor_customization(item) for key, item in value.items() if key in CUSTOM_FIELDS
        }
    return value


def bag_display_state(bag, lanes):
    if bag is None:
        return "inbox"
    if bag.flow_version != 2 or bag.state != "workshop":
        return bag.state
    states = {lane for lane in lanes if lane}
    return next(iter(states)) if len(states) == 1 else "in_production"


def project_unit(data, stations):
    result = dict(data)
    spec = data["specification"]
    roles = set(stations)
    result["source"] = dict(data["source"])
    if "tech" not in roles and result["source"].get("customization"):
        result["source"]["customization"] = {
            key: value
            for key, value in result["source"]["customization"].items()
            if key != "comment"
        }
    if "tech" not in roles:
        result["sizes"], result["cards"] = [], []
    if spec:
        # Storage digests and arbitrary extension fields are never floor data.
        result["specification"] = {
            key: spec[key]
            for key in (
                "tech_card_revision_id",
                "garment_size_id",
                "route",
                "components",
                "pattern_file_ids",
                "print_file_ids",
                "instructions",
                "quality_checks",
            )
        }
        visible = result["specification"]
        if not roles & {"tech", "kit"}:
            visible["components"] = []
            result["checks"] = {}
        if not roles & {"tech", "cut", "workshop", "sewing", "press", "qc"}:
            visible["pattern_file_ids"] = []
        if not roles & {"tech", "dtf", "workshop", "application"}:
            visible["print_file_ids"] = []
        allowed_files = set(visible["pattern_file_ids"] + visible["print_file_ids"])
        if "tech" not in roles:
            result["files"] = [f for f in data["files"] if f["id"] in allowed_files]
    elif "tech" not in roles:
        result["files"] = []
    return result
