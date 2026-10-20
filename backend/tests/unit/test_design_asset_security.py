import pytest

from app.modules.design_assets.security import (
    DesignAssetUnavailableError,
    create_design_asset_token,
    design_asset_path,
    digest_design_asset_token,
    token_from_design_asset_path,
)


def test_asset_capability_is_random_and_digest_and_url_are_scoped_to_one_image():
    first, second = create_design_asset_token(), create_design_asset_token()
    assert first != second
    assert len(first) == 43
    assert len(digest_design_asset_token(first)) == 64
    assert first not in digest_design_asset_token(first)
    path = design_asset_path(first)
    assert token_from_design_asset_path(path) == first
    for other in [
        "https://foreign.test" + path,
        "//foreign.test" + path,
        path + "?token=x",
        path + "/",
        path.replace("content", "../content"),
    ]:
        assert token_from_design_asset_path(other) is None


@pytest.mark.parametrize("token", ["", "x" * 42, "x" * 44, " " + "x" * 43, "/" * 43, "я" * 43])
def test_invalid_capabilities_are_rejected(token):
    with pytest.raises(DesignAssetUnavailableError):
        digest_design_asset_token(token)
