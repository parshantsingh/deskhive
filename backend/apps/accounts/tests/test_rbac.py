import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.accounts.permissions import IsSameOrganization


def _login(client, username, password):
    response = client.post(
        "/api/v1/auth/token/", {"username": username, "password": password}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


@pytest.mark.django_db
@pytest.mark.parametrize("role", [User.Role.OWNER, User.Role.ADMIN])
def test_owner_and_admin_can_invite_member(role):
    org = Organization.objects.create(name="Acme Support", slug="acme-support")
    User.objects.create_user(
        username="inviter", password="whatever123", organization=org, role=role
    )

    client = APIClient()
    _login(client, "inviter", "whatever123")
    response = client.post(
        "/api/v1/auth/invite/",
        {
            "username": "new_agent",
            "email": "new_agent@acme.test",
            "password": "agentpass123",
            "role": "agent",
        },
        format="json",
    )

    assert response.status_code == 201
    invited = User.objects.get(username="new_agent")
    assert invited.organization == org


@pytest.mark.django_db
@pytest.mark.parametrize("role", [User.Role.AGENT, User.Role.CUSTOMER])
def test_agent_and_customer_cannot_invite_member(role):
    org = Organization.objects.create(name="Acme Support", slug="acme-support")
    User.objects.create_user(
        username="inviter", password="whatever123", organization=org, role=role
    )

    client = APIClient()
    _login(client, "inviter", "whatever123")
    response = client.post(
        "/api/v1/auth/invite/",
        {
            "username": "new_agent",
            "email": "new_agent@acme.test",
            "password": "agentpass123",
            "role": "agent",
        },
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_is_same_organization_permission_allows_matching_org():
    org = Organization.objects.create(name="Acme Support", slug="acme-support")
    requester = User(organization=org)
    obj_in_same_org = User(organization=org)

    request = type("FakeRequest", (), {"user": requester})()
    assert IsSameOrganization().has_object_permission(request, None, obj_in_same_org) is True


@pytest.mark.django_db
def test_is_same_organization_permission_rejects_different_org():
    org_a = Organization.objects.create(name="Acme Support", slug="acme-support")
    org_b = Organization.objects.create(name="Beta Inc", slug="beta-inc")
    requester = User(organization=org_a)
    obj_in_other_org = User(organization=org_b)

    request = type("FakeRequest", (), {"user": requester})()
    assert IsSameOrganization().has_object_permission(request, None, obj_in_other_org) is False
