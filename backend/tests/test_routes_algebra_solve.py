from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes_algebra_solve import router
from app.main import app


def test_algebra_solve_route_registered():
    paths = {route.path for route in app.routes}
    assert "/api/algebra/solve" in paths


def test_algebra_solve_route_returns_solution():
    test_app = FastAPI()
    test_app.include_router(router)
    with TestClient(test_app) as client:
        response = client.post("/api/algebra/solve", json={"input": "x^2 - 5*x + 6 = 0"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "solved"
    assert payload["verification"]["status"] == "verified"
