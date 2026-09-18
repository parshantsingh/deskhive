import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.tickets.models import Comment, Ticket


def _login(client, username, password):
    response = client.post(
        "/api/v1/auth/token/", {"username": username, "password": password}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


@pytest.fixture
def ticket(org, customer):
    return Ticket.objects.create(
        organization=org, requester=customer, subject="Help", description="..."
    )


@pytest.mark.django_db
def test_customer_can_comment_on_own_ticket(ticket, customer):
    client = APIClient()
    _login(client, "cust1", "whatever123")

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/comments/", {"body": "Any update?"}, format="json"
    )

    assert response.status_code == 201
    comment = Comment.objects.get()
    assert comment.author == customer
    assert comment.organization == ticket.organization


@pytest.mark.django_db
def test_customer_cannot_comment_on_someone_elses_ticket(org, customer):
    other_customer = User.objects.create_user(
        username="cust2", password="whatever123", organization=org, role=User.Role.CUSTOMER
    )
    other_ticket = Ticket.objects.create(
        organization=org, requester=other_customer, subject="Not yours", description="..."
    )

    client = APIClient()
    _login(client, "cust1", "whatever123")
    response = client.post(
        f"/api/v1/tickets/{other_ticket.id}/comments/", {"body": "Sneaky"}, format="json"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_customer_cannot_create_internal_note(ticket):
    client = APIClient()
    _login(client, "cust1", "whatever123")

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/comments/",
        {"body": "sneaky", "is_internal_note": True},
        format="json",
    )

    assert response.status_code == 403
    assert Comment.objects.count() == 0


@pytest.mark.django_db
def test_customer_cannot_see_internal_notes(ticket, owner):
    Comment.objects.create(
        organization=ticket.organization,
        ticket=ticket,
        author=owner,
        body="visible to customer",
        is_internal_note=False,
    )
    Comment.objects.create(
        organization=ticket.organization,
        ticket=ticket,
        author=owner,
        body="internal only",
        is_internal_note=True,
    )

    client = APIClient()
    _login(client, "cust1", "whatever123")
    response = client.get(f"/api/v1/tickets/{ticket.id}/comments/")

    assert response.data["count"] == 1
    assert response.data["results"][0]["body"] == "visible to customer"


@pytest.mark.django_db
def test_agent_sees_both_public_and_internal_comments(ticket, owner):
    Comment.objects.create(
        organization=ticket.organization, ticket=ticket, author=owner, body="public"
    )
    Comment.objects.create(
        organization=ticket.organization,
        ticket=ticket,
        author=owner,
        body="internal",
        is_internal_note=True,
    )

    client = APIClient()
    _login(client, "owner1", "whatever123")
    response = client.get(f"/api/v1/tickets/{ticket.id}/comments/")

    assert response.data["count"] == 2


@pytest.mark.django_db
def test_comments_are_returned_in_chronological_order(ticket, owner):
    first = Comment.objects.create(
        organization=ticket.organization, ticket=ticket, author=owner, body="first"
    )
    second = Comment.objects.create(
        organization=ticket.organization, ticket=ticket, author=owner, body="second"
    )

    client = APIClient()
    _login(client, "owner1", "whatever123")
    response = client.get(f"/api/v1/tickets/{ticket.id}/comments/")

    ids = [item["id"] for item in response.data["results"]]
    assert ids == [str(first.id), str(second.id)]


@pytest.mark.django_db
def test_cannot_access_comments_for_a_ticket_in_another_organization(org, owner):
    other_org = Organization.objects.create(name="Other", slug="other")
    other_owner = User.objects.create_user(
        username="other_owner",
        password="whatever123",
        organization=other_org,
        role=User.Role.OWNER,
    )
    other_ticket = Ticket.objects.create(
        organization=other_org, requester=other_owner, subject="Theirs", description="..."
    )

    client = APIClient()
    _login(client, "owner1", "whatever123")
    response = client.get(f"/api/v1/tickets/{other_ticket.id}/comments/")

    assert response.status_code == 404
