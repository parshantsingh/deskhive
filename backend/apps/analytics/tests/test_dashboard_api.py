import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.tickets.models import Ticket

pytestmark = pytest.mark.django_db

URL = "/api/v1/dashboard/summary/"


def _client(user=None):
    client = APIClient()
    if user:
        client.force_authenticate(user=user)
    return client


def test_agents_and_owners_can_read_the_summary(owner, agent):
    for user in (owner, agent):
        response = _client(user).get(URL)

        assert response.status_code == 200
        assert set(response.data) == {"generated_at", "by_status", "open_work", "last_7_days"}


def test_customers_cannot_read_organization_wide_numbers(customer):
    assert _client(customer).get(URL).status_code == 403


def test_anonymous_users_get_401():
    assert _client().get(URL).status_code == 401


def test_the_header_reports_a_miss_then_a_hit(agent):
    client = _client(agent)

    first = client.get(URL)
    second = client.get(URL)

    assert (first["X-Cache"], second["X-Cache"]) == ("MISS", "HIT")
    assert first.data == second.data


def test_each_organization_sees_only_its_own_numbers(org, agent, customer):
    Ticket.objects.create(
        organization=org, requester=customer, subject="s", description="d", status="open"
    )
    other_org = Organization.objects.create(name="Other", slug="other")
    outsider = User.objects.create_user(
        username="outsider", password="whatever123", organization=other_org, role="agent"
    )

    mine = _client(agent).get(URL)
    theirs = _client(outsider).get(URL)

    assert mine.data["by_status"]["open"] == 1
    assert theirs.data["by_status"]["open"] == 0


def test_a_ticket_filed_through_the_api_shows_up_on_the_next_read(
    agent, customer, django_capture_on_commit_callbacks
):
    agent_client = _client(agent)
    agent_client.get(URL)  # warm the cache with zero tickets

    with django_capture_on_commit_callbacks(execute=True):
        response = _client(customer).post(
            "/api/v1/tickets/", {"subject": "Down", "description": "Help"}, format="json"
        )
    after = agent_client.get(URL)

    assert response.status_code == 201
    assert after["X-Cache"] == "MISS"
    assert after.data["by_status"]["open"] == 1
