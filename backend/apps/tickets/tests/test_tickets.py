from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.tickets.models import Category, SLAPolicy, Tag, Ticket


def _login(client, username, password):
    response = client.post(
        "/api/v1/auth/token/", {"username": username, "password": password}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


@pytest.mark.django_db
def test_customer_can_create_ticket_and_becomes_requester(org, customer):
    client = APIClient()
    _login(client, "cust1", "whatever123")

    response = client.post(
        "/api/v1/tickets/",
        {"subject": "Cannot login", "description": "Broken link", "priority": "medium"},
        format="json",
    )

    assert response.status_code == 201
    ticket = Ticket.objects.get()
    assert ticket.requester == customer
    assert ticket.organization == org


@pytest.mark.django_db
def test_ticket_gets_due_at_from_matching_sla_policy(org, customer):
    SLAPolicy.objects.create(
        organization=org,
        name="Urgent SLA",
        priority="urgent",
        response_time_minutes=5,
        resolution_time_minutes=30,
    )
    client = APIClient()
    _login(client, "cust1", "whatever123")

    before = timezone.now()
    client.post(
        "/api/v1/tickets/",
        {"subject": "Down", "description": "Site is down", "priority": "urgent"},
        format="json",
    )
    after = timezone.now()

    due_at = Ticket.objects.get().due_at
    assert due_at is not None
    assert before + timedelta(minutes=30) <= due_at <= after + timedelta(minutes=30)


@pytest.mark.django_db
def test_ticket_has_no_due_at_without_a_matching_sla_policy(org, customer):
    client = APIClient()
    _login(client, "cust1", "whatever123")

    client.post(
        "/api/v1/tickets/",
        {"subject": "Question", "description": "How do I...", "priority": "low"},
        format="json",
    )

    assert Ticket.objects.get().due_at is None


@pytest.mark.django_db
def test_customer_only_sees_their_own_tickets(org, customer):
    other_customer = User.objects.create_user(
        username="cust2", password="whatever123", organization=org, role=User.Role.CUSTOMER
    )
    Ticket.objects.create(organization=org, requester=customer, subject="Mine", description="...")
    Ticket.objects.create(
        organization=org, requester=other_customer, subject="Not mine", description="..."
    )

    client = APIClient()
    _login(client, "cust1", "whatever123")
    response = client.get("/api/v1/tickets/")

    assert response.data["count"] == 1
    assert response.data["results"][0]["subject"] == "Mine"


@pytest.mark.django_db
def test_agent_sees_every_ticket_in_the_organization(org, agent, customer):
    other_customer = User.objects.create_user(
        username="cust2", password="whatever123", organization=org, role=User.Role.CUSTOMER
    )
    Ticket.objects.create(organization=org, requester=customer, subject="A", description="...")
    Ticket.objects.create(
        organization=org, requester=other_customer, subject="B", description="..."
    )

    client = APIClient()
    _login(client, "agent1", "whatever123")
    response = client.get("/api/v1/tickets/")

    assert response.data["count"] == 2


@pytest.mark.django_db
def test_customer_cannot_assign_a_ticket(org, customer, agent):
    client = APIClient()
    _login(client, "cust1", "whatever123")

    response = client.post(
        "/api/v1/tickets/",
        {
            "subject": "Cannot login",
            "description": "Broken link",
            "assignee": agent.id,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "assignee" in response.data


@pytest.mark.django_db
def test_ticket_cannot_be_assigned_to_a_customer(org, owner, customer):
    other_customer = User.objects.create_user(
        username="cust2", password="whatever123", organization=org, role=User.Role.CUSTOMER
    )
    client = APIClient()
    _login(client, "owner1", "whatever123")

    response = client.post(
        "/api/v1/tickets/",
        {
            "subject": "Cannot login",
            "description": "Broken link",
            "assignee": other_customer.id,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "assignee" in response.data


@pytest.mark.django_db
def test_cannot_assign_ticket_to_a_user_in_another_organization(org, owner):
    other_org = Organization.objects.create(name="Other", slug="other")
    other_agent = User.objects.create_user(
        username="other_agent",
        password="whatever123",
        organization=other_org,
        role=User.Role.AGENT,
    )
    client = APIClient()
    _login(client, "owner1", "whatever123")

    response = client.post(
        "/api/v1/tickets/",
        {
            "subject": "Cannot login",
            "description": "Broken link",
            "assignee": other_agent.id,
        },
        format="json",
    )

    assert response.status_code == 400
    assert "assignee" in response.data


@pytest.mark.django_db
def test_cannot_use_category_or_tag_from_another_organization(org, owner):
    other_org = Organization.objects.create(name="Other", slug="other")
    other_category = Category.objects.create(organization=other_org, name="Billing")
    other_tag = Tag.objects.create(organization=other_org, name="vip")

    client = APIClient()
    _login(client, "owner1", "whatever123")

    response = client.post(
        "/api/v1/tickets/",
        {
            "subject": "Cannot login",
            "description": "Broken link",
            "category": str(other_category.id),
            "tags": [str(other_tag.id)],
        },
        format="json",
    )

    assert response.status_code == 400
    assert "category" in response.data or "tags" in response.data


@pytest.mark.django_db
def test_resolving_a_ticket_sets_resolved_at(org, owner, customer):
    ticket = Ticket.objects.create(
        organization=org, requester=customer, subject="Issue", description="..."
    )
    client = APIClient()
    _login(client, "owner1", "whatever123")

    response = client.patch(f"/api/v1/tickets/{ticket.id}/", {"status": "resolved"}, format="json")

    assert response.status_code == 200
    ticket.refresh_from_db()
    assert ticket.status == Ticket.Status.RESOLVED
    assert ticket.resolved_at is not None


@pytest.mark.django_db
def test_organizations_cannot_see_each_others_tickets(org, owner):
    other_org = Organization.objects.create(name="Other", slug="other")
    User.objects.create_user(
        username="other_owner",
        password="whatever123",
        organization=other_org,
        role=User.Role.OWNER,
    )
    ticket = Ticket.objects.create(
        organization=org, requester=owner, subject="Secret", description="..."
    )

    client = APIClient()
    _login(client, "other_owner", "whatever123")

    assert client.get("/api/v1/tickets/").data["count"] == 0
    assert client.get(f"/api/v1/tickets/{ticket.id}/").status_code == 404
