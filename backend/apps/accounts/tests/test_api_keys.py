import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import APIKey, Organization, User


@pytest.mark.django_db
def test_create_api_key_returns_raw_key_once_and_never_stores_it():
    client = APIClient()
    register_response = client.post(
        "/api/v1/auth/register/",
        {
            "organization_name": "Acme Support",
            "username": "owner1",
            "email": "owner1@acme.test",
            "password": "supersecret123",
        },
        format="json",
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {register_response.data['access']}")

    response = client.post("/api/v1/auth/api-keys/", {"name": "Zapier"}, format="json")

    assert response.status_code == 201
    raw_key = response.data["key"]

    api_key = APIKey.objects.get(prefix=response.data["prefix"])
    assert api_key.hashed_key != raw_key
    assert api_key.hashed_key == APIKey.hash_key(raw_key)


@pytest.mark.django_db
def test_api_key_authenticates_as_the_organization_owner():
    org = Organization.objects.create(name="Acme Support", slug="acme-support")
    owner = User.objects.create_user(
        username="owner1", password="whatever123", organization=org, role=User.Role.OWNER
    )
    api_key, raw_key = APIKey.create_for_organization(org, "Zapier")

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 200
    assert response.data["username"] == owner.username


@pytest.mark.django_db
def test_invalid_api_key_is_rejected():
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Api-Key totally-fake-key-value")
    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_revoked_api_key_is_rejected():
    org = Organization.objects.create(name="Acme Support", slug="acme-support")
    User.objects.create_user(
        username="owner1", password="whatever123", organization=org, role=User.Role.OWNER
    )
    api_key, raw_key = APIKey.create_for_organization(org, "Zapier")
    api_key.revoked_at = timezone.now()
    api_key.save(update_fields=["revoked_at"])

    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Api-Key {raw_key}")
    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 401


@pytest.mark.django_db
def test_non_owner_cannot_create_api_key():
    org = Organization.objects.create(name="Acme Support", slug="acme-support")
    User.objects.create_user(
        username="owner1", password="whatever123", organization=org, role=User.Role.OWNER
    )
    User.objects.create_user(
        username="agent1", password="whatever123", organization=org, role=User.Role.AGENT
    )

    client = APIClient()
    login = client.post(
        "/api/v1/auth/token/", {"username": "agent1", "password": "whatever123"}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.data['access']}")
    response = client.post("/api/v1/auth/api-keys/", {"name": "Zapier"}, format="json")

    assert response.status_code == 403
