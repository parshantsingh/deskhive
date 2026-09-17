import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        "/api/docs/",
        "/api/redoc/",
    ],
)
def test_api_docs_are_public(url):
    client = APIClient()
    response = client.get(url)

    assert response.status_code == 200


@pytest.mark.django_db
def test_openapi_schema_lists_real_endpoints():
    client = APIClient()
    response = client.get("/api/docs/", {"format": "openapi"})

    assert response.status_code == 200
    paths = response.data["paths"]
    assert "/auth/register/" in paths
    assert "/auth/token/" in paths
    assert "/health/" in paths
