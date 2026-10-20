from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.factory import create_app
from tests.favorites_scenario import favorite_settings, seed_favorites
from tests.projects_scenario import project_edit, project_payload, seed_project_media

PROJECTS = "/api/profile/projects"


@pytest.fixture
def projects_setup(tmp_path: Path):
    settings = favorite_settings(f"sqlite+aiosqlite:///{tmp_path / 'projects.db'}")
    products, tokens, users = asyncio.run(seed_favorites(settings))
    media = asyncio.run(seed_project_media(settings, products, users))
    return settings, products, tokens, media


def create_project(client, owner, payload):
    response = client.post(PROJECTS, headers=owner, json=payload)
    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


@pytest.mark.parametrize("size", ["M", ""])
def test_projects_are_durable_documents_shared_by_independent_clients(projects_setup, size):
    settings, products, (owner, other), media = projects_setup
    payload = project_payload(products[0], media[0])
    payload["snapshot"]["customization"]["selectedColor"] = "green"
    payload["snapshot"]["customization"]["selectedSize"] = size
    payload["snapshot"]["customization"]["fit"] = {
        "selectedSize": size,
        "sleeveMode": "standard",
        "lengthCm": 176,
        "widthCm": 80,
        "lengthRange": {"min": 162, "max": 188},
        "widthRange": {"min": 72, "max": 88},
    }
    with TestClient(create_app(settings=settings)) as client:
        created = create_project(client, owner, payload)
        assert created["version"] == 1
        assert created["snapshot"] == payload["snapshot"]
        assert created["snapshot"]["customization"]["selectedColor"] == "green"
        assert created["created_at"].endswith("Z")
        with TestClient(create_app(settings=settings)) as second:
            read = second.get(f"{PROJECTS}/{created['id']}", headers=owner)
            assert read.status_code == 200
            assert read.headers["cache-control"] == "no-store"
            assert read.json() == created
            assert second.get(PROJECTS, headers=other).json()["items"] == []
            assert second.get(f"{PROJECTS}/{created['id']}", headers=other).status_code == 404
    with TestClient(create_app(settings=settings)) as restarted:
        assert restarted.get(f"{PROJECTS}/{created['id']}", headers=owner).json() == created


def test_create_retries_do_not_duplicate_overwrite_or_resurrect_a_project(projects_setup):
    settings, products, (owner, _), media = projects_setup
    payload = project_payload(products[0], media[0])
    with TestClient(create_app(settings=settings)) as client:
        created = create_project(client, owner, payload)
        replay = client.post(PROJECTS, headers=owner, json=payload)
        assert replay.status_code == 200
        assert replay.json()["id"] == created["id"]
        changed = deepcopy(payload)
        changed["title"] = "Другой документ с тем же ключом"
        assert client.post(PROJECTS, headers=owner, json=changed).status_code == 409
        updated = client.put(
            f"{PROJECTS}/{created['id']}", headers=owner, json=project_edit(created)
        ).json()
        replay = client.post(PROJECTS, headers=owner, json=payload)
        assert replay.status_code == 200
        assert replay.json() == updated
        assert len(client.get(PROJECTS, headers=owner).json()["items"]) == 1
        assert (
            client.delete(
                f"{PROJECTS}/{created['id']}",
                headers=owner,
                params={"expected_version": updated["version"]},
            ).status_code
            == 204
        )
        assert client.post(PROJECTS, headers=owner, json=payload).status_code == 410
        assert client.get(PROJECTS, headers=owner).json()["items"] == []


def test_changes_require_owner_and_matching_version(projects_setup):
    settings, products, (owner, other), media = projects_setup
    with TestClient(create_app(settings=settings)) as client:
        created = create_project(client, owner, project_payload(products[0], media[0]))
        url = f"{PROJECTS}/{created['id']}"
        edit = project_edit(created)
        assert client.put(url, headers=other, json=edit).status_code == 404
        assert client.delete(url, headers=other, params={"expected_version": 1}).status_code == 404
        saved = client.put(url, headers=owner, json=edit)
        assert saved.status_code == 200
        assert saved.json()["version"] == 2
        assert saved.json()["title"] == "Изменённое имя"
        assert client.put(url, headers=owner, json=edit).status_code == 409
        assert client.delete(url, headers=owner, params={"expected_version": 1}).status_code == 409
        assert client.get(url, headers=owner).json() == saved.json()


def test_creation_receipt_is_owned_durable_current_and_distinguishes_deleted(projects_setup):
    settings, products, (owner, other), media = projects_setup
    payload = project_payload(products[0], media[0], key="legacy-v1-example")
    receipt_url = f"{PROJECTS}/by-client-key/{payload['client_key']}"
    with TestClient(create_app(settings=settings)) as client:
        assert client.get(receipt_url, headers=owner).status_code == 404
        created = create_project(client, owner, payload)
        updated = client.put(
            f"{PROJECTS}/{created['id']}", headers=owner, json=project_edit(created)
        ).json()
    with TestClient(create_app(settings=settings)) as restarted:
        receipt = restarted.get(receipt_url, headers=owner)
        assert receipt.status_code == 200, receipt.text
        assert receipt.headers["cache-control"] == "no-store"
        assert receipt.json() == {key: value for key, value in updated.items() if key != "snapshot"}
        assert restarted.get(receipt_url, headers=other).status_code == 404
        assert restarted.get(receipt_url).status_code == 401
        restarted.delete(
            f"{PROJECTS}/{created['id']}",
            headers=owner,
            params={"expected_version": updated["version"]},
        )
        deleted = restarted.get(receipt_url, headers=owner)
        assert deleted.status_code == 410
        assert deleted.headers["cache-control"] == "no-store"
        assert restarted.get(receipt_url, headers=other).status_code == 404


@pytest.mark.parametrize("key", ["bad.key", "bad%20key", "a" * 101])
def test_creation_receipt_validates_the_creation_key(projects_setup, key):
    settings, _, (owner, _), _ = projects_setup
    with TestClient(create_app(settings=settings)) as client:
        assert client.get(f"{PROJECTS}/by-client-key/{key}", headers=owner).status_code == 422


def test_lists_are_bounded_summaries_with_stable_keyset_pagination(projects_setup):
    settings, products, (owner, _), media = projects_setup
    with TestClient(create_app(settings=settings)) as client:
        ids = [
            create_project(client, owner, project_payload(products[0], media[0], key=f"draft-{i}"))[
                "id"
            ]
            for i in range(3)
        ]
        collection = project_payload(products[0], media[0], key="collection")
        collection["kind"] = "collection"
        create_project(client, owner, collection)
        page = client.get(PROJECTS, headers=owner, params={"limit": 2}).json()
        assert [item["id"] for item in page["items"]] == [ids[2], ids[1]]
        assert "snapshot" not in page["items"][0]
        page = client.get(
            PROJECTS, headers=owner, params={"limit": 2, "cursor": page["next_cursor"]}
        ).json()
        assert [item["id"] for item in page["items"]] == [ids[0]]
        assert page["next_cursor"] is None
        assert (
            len(client.get(PROJECTS, headers=owner, params={"kind": "collection"}).json()["items"])
            == 1
        )
        for query in (
            {"limit": 0},
            {"limit": 51},
            {"cursor": -1},
            {"cursor": 2**31},
            {"kind": "unknown"},
        ):
            assert client.get(PROJECTS, headers=owner, params=query).status_code == 422


def test_project_documents_reject_unversioned_unbounded_and_inline_images(projects_setup):
    settings, products, (owner, _), media = projects_setup
    valid = project_payload(products[0], media[0])
    invalid = []
    for key, value in (("schemaVersion", 2), ("activeView", "side"), ("unknown", 1)):
        payload = deepcopy(valid)
        payload["snapshot"][key] = value
        invalid.append(payload)
    for image in (
        "data:image/png;base64,AAAA",
        "https://external.test/image.png",
        {"mediaId": -1},
        {"mediaId": True},
    ):
        payload = deepcopy(valid)
        payload["snapshot"]["customization"]["modelImages"]["front"] = image
        invalid.append(payload)
    payload = deepcopy(valid)
    payload["snapshot"]["modelBounds"]["width"] = -1
    invalid.append(payload)
    payload = deepcopy(valid)
    payload["snapshot"]["customization"]["comment"] = "x" * 4001
    invalid.append(payload)
    payload = deepcopy(valid)
    payload["snapshot"]["customization"]["selectedColor"] = "x" * 65
    invalid.append(payload)
    payload = deepcopy(valid)
    payload["user_id"] = 123
    invalid.append(payload)
    payload = deepcopy(valid)
    payload["title"] = " "
    invalid.append(payload)
    with TestClient(create_app(settings=settings)) as client:
        for payload in invalid:
            response = client.post(PROJECTS, headers=owner, json=payload)
            assert response.status_code == 422, response.text
        assert client.get(PROJECTS, headers=owner).json()["items"] == []


def test_projects_only_reference_available_product_and_authorized_media(projects_setup):
    settings, products, (owner, _), media = projects_setup
    with TestClient(create_app(settings=settings)) as client:
        for product in [*products[3:], 99999]:
            assert (
                client.post(
                    PROJECTS, headers=owner, json=project_payload(product, media[0])
                ).status_code
                == 404
            )
        for unavailable in (media[1], media[3], media[4], 99999):
            assert (
                client.post(
                    PROJECTS, headers=owner, json=project_payload(products[0], unavailable)
                ).status_code
                == 422
            )
        create_project(client, owner, project_payload(products[0], media[2]))


def test_projects_require_real_session_for_all_operations(projects_setup):
    settings, products, (owner, _), media = projects_setup
    with TestClient(create_app(settings=settings)) as client:
        created = create_project(client, owner, project_payload(products[0], media[0]))
        url = f"{PROJECTS}/{created['id']}"
        for response in (
            client.get(PROJECTS),
            client.get(url),
            client.post(PROJECTS, json=project_payload(products[0], media[0])),
            client.put(url, json=project_edit(created)),
            client.delete(url, params={"expected_version": 1}),
        ):
            assert response.status_code == 401


def test_project_preserves_both_views_text_fit_and_edit_geometry(projects_setup):
    settings, products, (owner, _), media = projects_setup
    payload = project_payload(products[0], media[0])
    customization = payload["snapshot"]["customization"]
    customization["fit"] = {
        "selectedSize": "M",
        "sleeveMode": "height",
        "lengthCm": 75,
        "widthCm": 60,
        "lengthRange": {"min": 60, "max": 80},
        "widthRange": {"min": 50, "max": 70},
    }
    decoration = {
        "categoryId": "prints",
        "text": {"content": "Мой принт", "fontId": "manrope", "fontSize": 32, "color": "#ff3300"},
        "originalWidth": 900,
        "originalHeight": 600,
        "view": "back",
        "uid": "text-one",
        "variantId": "custom-text-one",
        "name": "Текст",
        "price": 250,
        "image": {"mediaId": media[2]},
        "widthCm": 18,
        "heightCm": 12,
        "x": -10.25,
        "y": 80.5,
        "scale": 1.25,
        "rotation": -32,
    }
    customization["decorations"] = [
        decoration,
        {**deepcopy(decoration), "uid": "text-two", "view": "front"},
    ]
    with TestClient(create_app(settings=settings)) as client:
        created = create_project(client, owner, payload)
        url = f"{PROJECTS}/{created['id']}"
        assert client.get(url, headers=owner).json()["snapshot"] == payload["snapshot"]
        edit = project_edit(created)
        edit["snapshot"]["customization"]["decorations"][0]["x"] = 90.75
        saved = client.put(url, headers=owner, json=edit)
        assert saved.status_code == 200
        assert saved.json()["snapshot"] == edit["snapshot"]
        invalid = project_edit(saved.json())
        invalid["snapshot"]["customization"]["decorations"][1]["uid"] = "text-one"
        assert client.put(url, headers=owner, json=invalid).status_code == 422
        invalid = project_edit(saved.json())
        invalid["snapshot"]["customization"]["fit"]["lengthCm"] = 95
        assert client.put(url, headers=owner, json=invalid).status_code == 422
        assert client.get(url, headers=owner).json() == saved.json()


def test_invalid_project_numbers_return_422_without_echoing_document(projects_setup):
    settings, products, (owner, _), media = projects_setup
    with TestClient(create_app(settings=settings), raise_server_exceptions=False) as client:
        for number in (float("nan"), float("inf"), float("-inf")):
            payload = project_payload(products[0], media[0])
            payload["snapshot"]["modelBounds"]["x"] = number
            response = client.post(
                PROJECTS,
                headers={**owner, "Content-Type": "application/json"},
                content=json.dumps(payload),
            )
            assert response.status_code == 422, response.text
            assert response.headers["cache-control"] == "no-store"
            assert response.json()["detail"][0]["loc"] == ["body", "snapshot", "modelBounds", "x"]
            assert "input" not in response.json()["detail"][0]
        payload = project_payload(products[0], media[0])
        payload["snapshot"]["customization"]["comment"] = "private-document-value" * 300
        response = client.post(PROJECTS, headers=owner, json=payload)
        assert response.status_code == 422
        assert "private-document-value" not in response.text
        assert len(response.content) < 2000
