"""RED/GREEN tests for cargo create + list (SPEC-core §5.2, §7.2, §9)."""

from __future__ import annotations

import uuid

import pytest

from app.database import engine
from tests.support import client_for, make_cargo, make_user

pytestmark = pytest.mark.skipif(
    engine.dialect.name != "postgresql",
    reason="Cargo tests require PostgreSQL (set DATABASE_URL to a test URL).",
)

CARGO_KEYS = {
    "id",
    "shipper_id",
    "title",
    "origin",
    "destination",
    "weight_kg",
    "price",
    "status",
}


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


def _payload(**overrides) -> dict:
    suffix = _suffix()
    values = {
        "title": f"بار {suffix}",
        "origin": f"مبدأ-{suffix}",
        "destination": f"مقصد-{suffix}",
        "weight_kg": 1200,
        "price": 7_500_000,
    }
    values.update(overrides)
    return values


def _create(client, **overrides):
    return client.post("/api/cargos", json=_payload(**overrides))


def _code(response):
    return response.json()["detail"]["code"]


# --------------------------------------------------------------------------- #
# Create
# --------------------------------------------------------------------------- #


def test_shipper_creates_cargo_from_session():
    shipper = make_user("shipper")
    other = make_user("shipper")
    payload = _payload()

    response = client_for(shipper).post(
        "/api/cargos",
        json={**payload, "shipper_id": other.id, "status": "booked"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert set(body) == CARGO_KEYS
    assert body["shipper_id"] == shipper.id
    assert body["status"] == "available"
    assert body["title"] == payload["title"]
    assert float(body["weight_kg"]) == float(payload["weight_kg"])
    assert response.headers["location"] == f"/api/cargos/{body['id']}"


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": "ab"},
        {"title": "x" * 201},
        {"origin": "a"},
        {"origin": "x" * 201},
        {"destination": "a"},
        {"destination": "x" * 201},
        {"weight_kg": 0},
        {"weight_kg": -5},
        {"weight_kg": 40_001},
        {"price": 0},
        {"price": -1},
        {"price": 1_000_000_000_001},
    ],
)
def test_cargo_validation(overrides):
    shipper = make_user("shipper")
    response = _create(client_for(shipper), **overrides)
    assert response.status_code == 422, response.text


def test_cargo_title_and_text_are_trimmed():
    shipper = make_user("shipper")
    response = _create(
        client_for(shipper),
        title="  بار تازه  ",
        origin="  تهران  ",
        destination="  مشهد  ",
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["title"] == "بار تازه"
    assert body["origin"] == "تهران"
    assert body["destination"] == "مشهد"


def test_cargo_create_is_shipper_only():
    assert _create(client_for(None)).status_code == 401
    for role in ("driver", "carrier", "admin"):
        response = _create(client_for(make_user(role)))
        assert response.status_code == 403, (role, response.text)
        assert _code(response) == "forbidden"


# --------------------------------------------------------------------------- #
# List
# --------------------------------------------------------------------------- #


def test_list_requires_authentication():
    response = client_for(None).get("/api/cargos")
    assert response.status_code == 401
    assert _code(response) == "unauthorized"


def test_list_defaults_to_available_newest_first():
    shipper = make_user("shipper")
    marker = _suffix()
    first = make_cargo(shipper=shipper, origin=f"مبدأ-{marker}")
    second = make_cargo(shipper=shipper, origin=f"مبدأ-{marker}")
    make_cargo(
        shipper=shipper, origin=f"مبدأ-{marker}", status="booked"
    )

    response = client_for(make_user("driver")).get(
        "/api/cargos", params={"origin": marker}
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] == 2
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert [item["id"] for item in body["items"]] == [second.id, first.id]
    assert all(item["status"] == "available" for item in body["items"])


def test_list_is_readable_by_every_role():
    make_cargo()
    for role in ("driver", "shipper", "carrier", "admin"):
        response = client_for(make_user(role)).get("/api/cargos")
        assert response.status_code == 200, role


def test_list_filters_are_case_insensitive_substrings():
    shipper = make_user("shipper")
    marker = _suffix()
    match = make_cargo(
        shipper=shipper,
        origin=f"Bandar Abbas {marker}",
        destination=f"Tehran {marker}",
        weight_kg=1500,
        price=9_000_000,
    )
    make_cargo(
        shipper=shipper,
        origin=f"Shiraz {marker}",
        destination=f"Tabriz {marker}",
        weight_kg=3000,
        price=20_000_000,
    )

    client = client_for(make_user("driver"))

    by_origin = client.get(
        "/api/cargos", params={"origin": f"bandar abbas {marker.lower()}"}
    )
    assert [item["id"] for item in by_origin.json()["items"]] == [match.id]

    by_destination = client.get(
        "/api/cargos", params={"destination": f"TEHRAN {marker}"}
    )
    assert [item["id"] for item in by_destination.json()["items"]] == [match.id]

    ranged = client.get(
        "/api/cargos",
        params={
            "origin": marker,
            "min_weight": 1000,
            "max_weight": 2000,
            "min_price": 8_000_000,
            "max_price": 10_000_000,
        },
    )
    assert [item["id"] for item in ranged.json()["items"]] == [match.id]


def test_list_filters_are_inclusive():
    shipper = make_user("shipper")
    marker = _suffix()
    cargo = make_cargo(
        shipper=shipper,
        origin=f"مبدأ-{marker}",
        weight_kg=2500,
        price=12_000_000,
    )

    client = client_for(make_user("driver"))
    exact = client.get(
        "/api/cargos",
        params={
            "origin": marker,
            "min_weight": 2500,
            "max_weight": 2500,
            "min_price": 12_000_000,
            "max_price": 12_000_000,
        },
    )
    assert [item["id"] for item in exact.json()["items"]] == [cargo.id]


def test_list_pagination():
    shipper = make_user("shipper")
    marker = _suffix()
    cargos = [
        make_cargo(shipper=shipper, origin=f"مبدأ-{marker}") for _ in range(3)
    ]

    client = client_for(make_user("driver"))
    page = client.get(
        "/api/cargos", params={"origin": marker, "limit": 2, "offset": 0}
    ).json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    assert [item["id"] for item in page["items"]] == [
        cargos[2].id,
        cargos[1].id,
    ]

    next_page = client.get(
        "/api/cargos", params={"origin": marker, "limit": 2, "offset": 2}
    ).json()
    assert [item["id"] for item in next_page["items"]] == [cargos[0].id]


@pytest.mark.parametrize(
    "params",
    [
        {"limit": 0},
        {"limit": 101},
        {"offset": -1},
        {"min_weight": 10, "max_weight": 5},
        {"min_price": 10, "max_price": 5},
    ],
)
def test_list_rejects_invalid_query(params):
    response = client_for(make_user("driver")).get("/api/cargos", params=params)
    assert response.status_code == 422, response.text


def test_booked_and_all_status_are_admin_only():
    shipper = make_user("shipper")
    marker = _suffix()
    make_cargo(shipper=shipper, origin=f"مبدأ-{marker}", status="booked")

    driver = client_for(make_user("driver"))
    for status in ("booked", "all"):
        response = driver.get(
            "/api/cargos", params={"origin": marker, "status": status}
        )
        assert response.status_code == 403, (status, response.text)
        assert _code(response) == "forbidden"

    admin = client_for(make_user("admin"))
    booked = admin.get(
        "/api/cargos", params={"origin": marker, "status": "booked"}
    )
    assert booked.status_code == 200
    assert booked.json()["total"] == 1

    everything = admin.get(
        "/api/cargos", params={"origin": marker, "status": "all"}
    )
    assert everything.status_code == 200
    assert everything.json()["total"] >= 1


def test_unknown_status_filter_is_422():
    response = client_for(make_user("admin")).get(
        "/api/cargos", params={"status": "deleted"}
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------- #
# Detail
# --------------------------------------------------------------------------- #


def test_detail_returns_cargo_for_any_authenticated_role():
    cargo = make_cargo()
    for role in ("driver", "shipper", "carrier", "admin"):
        response = client_for(make_user(role)).get(f"/api/cargos/{cargo.id}")
        assert response.status_code == 200, role
        assert response.json()["id"] == cargo.id


def test_booked_cargo_is_still_readable_by_id():
    cargo = make_cargo(status="booked")
    response = client_for(make_user("driver")).get(f"/api/cargos/{cargo.id}")
    assert response.status_code == 200
    assert response.json()["status"] == "booked"


def test_detail_missing_cargo_is_404():
    response = client_for(make_user("driver")).get("/api/cargos/2147483647")
    assert response.status_code == 404
    assert _code(response) == "cargo_not_found"


def test_detail_requires_authentication():
    response = client_for(None).get("/api/cargos/1")
    assert response.status_code == 401
