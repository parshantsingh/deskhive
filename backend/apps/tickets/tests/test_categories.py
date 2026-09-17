import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.tickets.models import Category


def _login(client, username, password):
    response = client.post(
        "/api/v1/auth/token/", {"username": username, "password": password}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


@pytest.mark.django_db
def test_owner_can_create_category():
    org = Organization.objects.create(name="Acme", slug="acme")
    User.objects.create_user(
        username="owner1", password="whatever123", organization=org, role=User.Role.OWNER
    )

    client = APIClient()
    _login(client, "owner1", "whatever123")
    response = client.post("/api/v1/categories/", {"name": "Billing"}, format="json")

    assert response.status_code == 201
    assert Category.objects.get().organization == org


@pytest.mark.django_db
def test_customer_cannot_create_category():
    org = Organization.objects.create(name="Acme", slug="acme")
    User.objects.create_user(
        username="cust1", password="whatever123", organization=org, role=User.Role.CUSTOMER
    )

    client = APIClient()
    _login(client, "cust1", "whatever123")
    response = client.post("/api/v1/categories/", {"name": "Billing"}, format="json")

    assert response.status_code == 403


@pytest.mark.django_db
def test_client_supplied_organization_field_is_ignored():
    org = Organization.objects.create(name="Acme", slug="acme")
    other_org = Organization.objects.create(name="Other", slug="other")
    User.objects.create_user(
        username="owner1", password="whatever123", organization=org, role=User.Role.OWNER
    )

    client = APIClient()
    _login(client, "owner1", "whatever123")
    response = client.post(
        "/api/v1/categories/",
        {"name": "Billing", "organization": str(other_org.id)},
        format="json",
    )

    assert response.status_code == 201
    category = Category.objects.get()
    assert category.organization == org
    assert category.organization != other_org


@pytest.mark.django_db
def test_organizations_cannot_see_each_others_categories():
    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")
    User.objects.create_user(
        username="owner_a", password="whatever123", organization=org_a, role=User.Role.OWNER
    )
    User.objects.create_user(
        username="owner_b", password="whatever123", organization=org_b, role=User.Role.OWNER
    )
    category_a = Category.objects.create(organization=org_a, name="Billing")

    client = APIClient()
    _login(client, "owner_b", "whatever123")

    list_response = client.get("/api/v1/categories/")
    assert list_response.data["count"] == 0

    detail_response = client.get(f"/api/v1/categories/{category_a.id}/")
    assert detail_response.status_code == 404
