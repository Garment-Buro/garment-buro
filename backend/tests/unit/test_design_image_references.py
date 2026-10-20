from types import SimpleNamespace

import pytest

from app.modules.design_assets.references import design_image_tokens
from app.modules.design_assets.security import DesignAssetUnavailableError, design_asset_path


def line(image="", customization=None):
    return SimpleNamespace(image=image, customization=customization)


def test_only_image_slots_retain_deduplicated_capabilities():
    a, b, c = [character * 43 for character in "abc"]
    assert design_image_tokens(
        [
            line(
                design_asset_path(a),
                {
                    "modelImages": {"front": design_asset_path(b), "back": design_asset_path(a)},
                    "decorations": [
                        {"image": design_asset_path(c)},
                        {"image": design_asset_path(b)},
                    ],
                    "comment": design_asset_path("d" * 43),
                },
            ),
            line(
                "https://cdn.test/model.webp",
                {
                    "modelImages": {"front": "data:image/png;base64,AA=="},
                    "decorations": [{"text": {"content": design_asset_path("e" * 43)}}, None],
                },
            ),
        ]
    ) == [a, b, c]


@pytest.mark.parametrize(
    "alias",
    [
        "https://shop.test/api/design-media/" + "a" * 43 + "/content",
        "//shop.test/api/design-media/" + "a" * 43 + "/content",
        "/api/design-media/" + "a" * 43 + "/content?x=1",
        "/api/design-media/" + "a" * 43 + "/content#image",
        "/api/design-media/invalid/content",
        "/api/%64esign-media/" + "a" * 43 + "/content",
        "/api/old/../design-media/" + "a" * 43 + "/content",
        "/api\\design-media\\" + "a" * 43 + "\\content",
    ],
)
def test_noncanonical_design_urls_cannot_bypass_retention(alias):
    with pytest.raises(DesignAssetUnavailableError):
        design_image_tokens([line(customization={"decorations": [{"image": alias}]})])
