import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.models import Organization, User
from apps.tickets.models import Attachment, Ticket


def _login(client, username, password):
    response = client.post(
        "/api/v1/auth/token/", {"username": username, "password": password}, format="json"
    )
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {response.data['access']}")


@pytest.fixture
def org():
    return Organization.objects.create(name="Acme", slug="acme")


@pytest.fixture
def owner(org):
    return User.objects.create_user(
        username="owner1", password="whatever123", organization=org, role=User.Role.OWNER
    )


@pytest.fixture
def customer(org):
    return User.objects.create_user(
        username="cust1", password="whatever123", organization=org, role=User.Role.CUSTOMER
    )


@pytest.fixture
def ticket(org, customer):
    return Ticket.objects.create(
        organization=org, requester=customer, subject="Help", description="..."
    )


@pytest.mark.django_db
def test_customer_can_upload_attachment_to_own_ticket(ticket, customer):
    client = APIClient()
    _login(client, "cust1", "whatever123")
    upload = SimpleUploadedFile("screenshot.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/attachments/", {"file": upload}, format="multipart"
    )

    assert response.status_code == 201
    attachment = Attachment.objects.get()
    assert attachment.uploaded_by == customer
    assert attachment.original_filename == "screenshot.png"
    assert attachment.content_type == "image/png"
    assert attachment.size_bytes == len(b"\x89PNG\r\n\x1a\n")
    assert attachment.organization == ticket.organization


@pytest.mark.django_db
def test_disallowed_content_type_is_rejected(ticket, customer):
    client = APIClient()
    _login(client, "cust1", "whatever123")
    upload = SimpleUploadedFile(
        "virus.exe", b"MZ fake exe content", content_type="application/x-msdownload"
    )

    response = client.post(
        f"/api/v1/tickets/{ticket.id}/attachments/", {"file": upload}, format="multipart"
    )

    assert response.status_code == 400
    assert "file" in response.data
    assert Attachment.objects.count() == 0


@pytest.mark.django_db
def test_oversized_file_is_rejected(ticket, customer):
    from apps.tickets import serializers as ticket_serializers

    original_max = ticket_serializers.MAX_ATTACHMENT_SIZE_BYTES
    ticket_serializers.MAX_ATTACHMENT_SIZE_BYTES = 10
    try:
        client = APIClient()
        _login(client, "cust1", "whatever123")
        upload = SimpleUploadedFile("big.png", b"\x89PNG\r\n\x1a\n" * 10, content_type="image/png")

        response = client.post(
            f"/api/v1/tickets/{ticket.id}/attachments/", {"file": upload}, format="multipart"
        )

        assert response.status_code == 400
        assert "file" in response.data
    finally:
        ticket_serializers.MAX_ATTACHMENT_SIZE_BYTES = original_max


@pytest.mark.django_db
def test_customer_cannot_upload_to_someone_elses_ticket(org, customer):
    other_customer = User.objects.create_user(
        username="cust2", password="whatever123", organization=org, role=User.Role.CUSTOMER
    )
    other_ticket = Ticket.objects.create(
        organization=org, requester=other_customer, subject="Not yours", description="..."
    )

    client = APIClient()
    _login(client, "cust1", "whatever123")
    upload = SimpleUploadedFile("sneaky.png", b"\x89PNG\r\n\x1a\n", content_type="image/png")

    response = client.post(
        f"/api/v1/tickets/{other_ticket.id}/attachments/", {"file": upload}, format="multipart"
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_agent_sees_attachments_uploaded_by_customer(ticket, owner, customer):
    Attachment.objects.create(
        organization=ticket.organization,
        ticket=ticket,
        uploaded_by=customer,
        file=SimpleUploadedFile("a.png", b"data", content_type="image/png"),
        original_filename="a.png",
        content_type="image/png",
        size_bytes=4,
    )

    client = APIClient()
    _login(client, "owner1", "whatever123")
    response = client.get(f"/api/v1/tickets/{ticket.id}/attachments/")

    assert response.data["count"] == 1
