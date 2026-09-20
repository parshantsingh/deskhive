import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db

URL = "/api/v1/analytics/overview/"


def _get(user=None, **params):
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client.get(URL, params)


def test_owners_get_daily_volume_and_agent_figures(org, owner, agent, customer):
    Ticket.objects.create(
        organization=org, requester=customer, assignee=agent, subject="s", description="d"
    )

    response = _get(owner)

    assert response.status_code == 200
    assert response.data["days"] == 30
    assert len(response.data["daily_volume"]) == 30
    assert sum(day["created"] for day in response.data["daily_volume"]) == 1
    assert [row["username"] for row in response.data["agents"]] == [agent.username]


def test_admins_can_read_it_too(org):
    admin = User.objects.create_user(
        username="admin1", password="whatever123", organization=org, role=User.Role.ADMIN
    )

    assert _get(admin).status_code == 200


def test_the_window_is_configurable(owner):
    assert len(_get(owner, days=7).data["daily_volume"]) == 7


@pytest.mark.parametrize("who", ["agent", "customer"])
def test_agents_and_customers_are_refused(who, request):
    assert _get(request.getfixturevalue(who)).status_code == 403


def test_anonymous_users_get_401():
    assert _get().status_code == 401


@pytest.mark.parametrize("days", ["0", "-5", "366", "abc", "7; DROP TABLE tickets_ticket"])
def test_an_invalid_window_is_a_400_and_never_reaches_the_database(owner, days):
    response = _get(owner, days=days)

    assert response.status_code == 400
    assert "days" in response.data
    assert Ticket.objects.count() == 0  # the table is still there to be queried


def test_each_organization_sees_only_its_own_figures(org, owner, agent, customer):
    Ticket.objects.create(
        organization=org, requester=customer, assignee=agent, subject="s", description="d"
    )
    other_org = Organization.objects.create(name="Other", slug="other")
    outsider = User.objects.create_user(
        username="outsider", password="whatever123", organization=other_org, role="owner"
    )

    response = _get(outsider)

    assert response.data["agents"] == []
    assert sum(day["created"] for day in response.data["daily_volume"]) == 0
