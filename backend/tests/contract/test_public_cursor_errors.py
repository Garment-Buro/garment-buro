import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db.session import get_database_session
from app.modules.catalog.storefront_router import get_storefront_service
from app.modules.catalog.storefront_router import router as storefront_router
from app.modules.catalog.storefront_service import InvalidStorefrontCursor
from app.modules.partners.directory_router import get_directory_service
from app.modules.partners.directory_router import router as community_router
from app.modules.partners.directory_service import InvalidCommunityCursor
from app.modules.public_profiles.router import get_profile_service
from app.modules.public_profiles.router import router as people_router
from app.modules.public_profiles.service import InvalidPeopleCursor


@pytest.mark.parametrize(
    "router,dependency,error_type,path",
    [
        (
            storefront_router,
            get_storefront_service,
            InvalidStorefrontCursor,
            "/api/catalog/products",
        ),
        (community_router, get_directory_service, InvalidCommunityCursor, "/api/communities"),
        (people_router, get_profile_service, InvalidPeopleCursor, "/api/people"),
    ],
)
def test_public_cursor_error_is_machine_readable_and_not_confused_with_input_validation(
    router, dependency, error_type, path
):
    class Service:
        async def list_page(self, *args, **kwargs):
            raise error_type("Invalid cursor for these filters")

    async def session():
        yield None

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_database_session] = session
    app.dependency_overrides[dependency] = Service
    with TestClient(app) as client:
        response = client.get(path, params={"cursor": "old"})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "invalid_cursor"
        assert response.headers["Cache-Control"] == "no-store"
        invalid = client.get(path, params={"limit": 0})
        assert invalid.status_code == 422
        assert isinstance(invalid.json()["detail"], list)
