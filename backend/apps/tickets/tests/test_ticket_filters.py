import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.tickets.models import Category, Ticket

pytestmark = pytest.mark.django_db


def _list(user, **params):
    client = APIClient()
    client.force_authenticate(user=user)
    return client.get("/api/v1/tickets/", params)


def _subjects(response):
    return {ticket["subject"] for ticket in response.data["results"]}


@pytest.fixture
def tickets(org, agent, customer):
    billing = Category.objects.create(organization=org, name="Billing")

    def make(subject, **fields):
        return Ticket.objects.create(
            organization=org, requester=customer, subject=subject, description="...", **fields
        )

    make("open-urgent-mine", status="open", priority="urgent", assignee=agent, category=billing)
    make("open-low-unassigned", status="open", priority="low")
    make("pending-high-mine", status="pending", priority="high", assignee=agent)
    make("closed-low", status="closed", priority="low")


def test_filter_by_status(agent, tickets):
    response = _list(agent, status="open")

    assert _subjects(response) == {"open-urgent-mine", "open-low-unassigned"}


def test_filter_by_priority(agent, tickets):
    response = _list(agent, priority="low")

    assert _subjects(response) == {"open-low-unassigned", "closed-low"}


def test_filter_by_assignee(agent, tickets):
    response = _list(agent, assignee=agent.id)

    assert _subjects(response) == {"open-urgent-mine", "pending-high-mine"}


def test_filter_by_category(agent, tickets):
    category = Category.objects.get(name="Billing")

    response = _list(agent, category=category.id)

    assert _subjects(response) == {"open-urgent-mine"}


def test_filters_combine(agent, tickets):
    response = _list(agent, status="open", assignee=agent.id)

    assert _subjects(response) == {"open-urgent-mine"}


def test_an_invalid_choice_is_a_400(agent, tickets):
    response = _list(agent, status="on-fire")

    assert response.status_code == 400
    assert "status" in response.data


def test_another_organizations_assignee_looks_like_an_unknown_one(agent, tickets):
    outsider = User.objects.create_user(
        username="outsider",
        password="whatever123",
        organization=Organization.objects.create(name="Other", slug="other"),
        role=User.Role.AGENT,
    )

    foreign = _list(agent, assignee=outsider.id)
    unknown = _list(agent, assignee=999_999)

    # Same status and same body: a caller can't probe which ids exist elsewhere.
    assert foreign.status_code == unknown.status_code == 200
    assert foreign.data["results"] == unknown.data["results"] == []


def test_a_foreign_category_id_is_an_empty_page_not_a_400(agent, tickets):
    other_org = Organization.objects.create(name="Other", slug="other")
    foreign = Category.objects.create(organization=other_org, name="Secret")

    for category_id in (foreign.id, uuid.uuid4()):
        response = _list(agent, category=category_id)

        assert response.status_code == 200
        assert response.data["results"] == []


def test_filters_never_widen_what_a_customer_may_see(org, customer, tickets):
    other_customer = User.objects.create_user(
        username="cust2", password="whatever123", organization=org, role=User.Role.CUSTOMER
    )
    Ticket.objects.create(
        organization=org,
        requester=other_customer,
        subject="someone-elses",
        description="...",
        status="open",
    )

    response = _list(customer, status="open")

    assert "someone-elses" not in _subjects(response)
    assert _subjects(response) == {"open-urgent-mine", "open-low-unassigned"}
