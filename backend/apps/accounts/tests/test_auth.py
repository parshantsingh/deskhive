import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Organization

User = get_user_model()


@pytest.mark.django_db
def test_register_creates_organization_and_owner_user():
    client = APIClient()
    response = client.post(
        "/api/v1/auth/register/",
        {
            "organization_name": "Acme Support",
            "username": "jane",
            "email": "jane@acme.test",
            "password": "supersecret123",
        },
        format="json",
    )

    assert response.status_code == 201
    assert "access" in response.data
    assert "refresh" in response.data
    assert response.data["user"]["role"] == "owner"

    user = User.objects.get(username="jane")
    assert user.organization.name == "Acme Support"
    assert user.role == User.Role.OWNER


@pytest.mark.django_db
def test_register_rejects_duplicate_username():
    Organization.objects.create(name="Existing Org", slug="existing-org")
    User.objects.create_user(username="jane", password="whatever123")

    client = APIClient()
    response = client.post(
        "/api/v1/auth/register/",
        {
            "organization_name": "Another Org",
            "username": "jane",
            "email": "jane2@acme.test",
            "password": "supersecret123",
        },
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_login_returns_access_and_refresh_tokens():
    org = Organization.objects.create(name="Acme Support", slug="acme-support")
    User.objects.create_user(username="jane", password="supersecret123", organization=org)

    client = APIClient()
    response = client.post(
        "/api/v1/auth/token/",
        {"username": "jane", "password": "supersecret123"},
        format="json",
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_me_endpoint_requires_authentication():
    client = APIClient()
    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_me_endpoint_returns_current_user_with_valid_token():
    client = APIClient()
    register_response = client.post(
        "/api/v1/auth/register/",
        {
            "organization_name": "Acme Support",
            "username": "jane",
            "email": "jane@acme.test",
            "password": "supersecret123",
        },
        format="json",
    )
    access_token = register_response.data["access"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 200
    assert response.data["username"] == "jane"
    assert response.data["role"] == "owner"
