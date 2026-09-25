"""
Unit tests for Web UI router and static file serving.
"""

import pytest
from fastapi.testclient import TestClient
from src.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_ui_index_route(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "MRPL Sovereign AI" in res.text


def test_ui_static_assets(client):
    # CSS asset test
    res_css = client.get("/static/css/app.css")
    assert res_css.status_code == 200
    assert "text/css" in res_css.headers["content-type"]

    # JS asset test
    res_js = client.get("/static/js/api.js")
    assert res_js.status_code == 200

    # Logo SVG test
    res_logo = client.get("/static/assets/logo.svg")
    assert res_logo.status_code == 200


def test_swagger_and_openapi_routes(client):
    res_docs = client.get("/docs")
    assert res_docs.status_code == 200

    res_openapi = client.get("/openapi.json")
    assert res_openapi.status_code == 200
