from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from app.api.routes_algebra_solve import router
from app.db.session import get_database
from app.main import app
from app.services.algebra.service import solve_algebra


class _RouteDb:
    backend = "sqlite"

    async def fetch_one(self, *_args, **_kwargs):
        return None

    async def fetch_all(self, *_args, **_kwargs):
        return []

    async def execute(self, *_args, **_kwargs):
        return None

    async def execute_many(self, *_args, **_kwargs):
        return None

    async def close(self):
        return None

    def pool_stats(self):
        return {"backend": self.backend, "pooled": False}


@pytest.fixture()
def route_client(monkeypatch):
    test_app = FastAPI()
    test_app.include_router(router)
    db = _RouteDb()

    async def override_database():
        return db

    async def solve_without_process(request, _settings, load_slot=None):
        return solve_algebra(request)

    test_app.dependency_overrides[get_database] = override_database
    monkeypatch.setattr(
        "app.api.routes_algebra_solve.solve_algebra_with_optional_ai",
        solve_without_process,
    )
    with TestClient(test_app) as client:
        yield client


def _iter_api_routes(routes):
    for route in routes:
        path = getattr(route, "path", None)
        if path is not None:
            yield route
            continue
        original = getattr(route, "original_router", None)
        if original is not None:
            yield from _iter_api_routes(original.routes)
            continue
        nested = getattr(route, "routes", None)
        if nested is not None:
            yield from _iter_api_routes(nested)


def test_algebra_solve_route_registered():
    paths = {route.path for route in _iter_api_routes(app.routes)}
    assert "/api/algebra/solve" in paths


def test_algebra_solve_route_returns_solution(route_client):
    response = route_client.post("/api/algebra/solve", json={"input": "x^2 - 5*x + 6 = 0"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "solved"
    assert payload["verification"]["status"] == "verified"


def test_algebra_solve_route_returns_input_interpretation_for_vietnamese_query(route_client):
    response = route_client.post("/api/algebra/solve", json={"input": "Giải phương trình x bình phương - 5x + 6 bằng 0"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "solved"
    assert payload["input_interpretation"]["detected_format"] == "mixed"
    assert payload["input_interpretation"]["canonical_input"] == "x^2-5*x+6=0"


def test_algebra_solve_route_handles_mixed_integral_without_internal_error(route_client):
    response = route_client.post(
        "/api/algebra/solve",
        json={"input": "tính tích phân của x*2 - 1/x + e**(x-1)"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "solved"
    assert payload["verification"]["status"] == "verified"
    assert [step["title"] for step in payload["steps"][:3]] == [
        "Nhận dạng tích phân",
        "Tách tích phân theo từng hạng tử",
        "Ghép các nguyên hàm thành phần",
    ]
    assert len(payload["steps"][1]["sub_steps"]) == 3


def test_algebra_solve_route_handles_derivative_equation_in_vietnamese_latex(route_client):
    response = route_client.post(
        "/api/algebra/solve",
        json={
            "input": (
                r"Câu 2: Cho hàm số f(x)=\frac{1}{3}x^3-2x^2+3x+8, "
                r"nghiệm của phương trình f'(x)=0 là gì"
            ),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "solved"
    assert payload["problem_type"] == "solve_derivative_equation"
    assert [value["text"] for value in payload["solution_set"]["values"]] == ["1", "3"]
    assert payload["verification"]["status"] == "verified"
