import datetime

import pytest
from django.core import mail
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.notifications.tasks import send_weekly_digest
from apps.tickets.models import Ticket


@pytest.fixture
def org():
    return Organization.objects.create(name="Acme", slug="acme")


@pytest.fixture
def owner(org):
    return User.objects.create_user(
        username="owner1",
        password="whatever123",
        organization=org,
        role=User.Role.OWNER,
        email="owner1@acme.test",
    )


@pytest.mark.django_db
def test_digest_counts_this_weeks_activity(org, owner):
    now = timezone.now()

    Ticket.objects.create(
        organization=org, requester=owner, subject="New this week", description="..."
    )
    old_ticket = Ticket.objects.create(
        organization=org, requester=owner, subject="Old", description="..."
    )
    Ticket.objects.filter(id=old_ticket.id).update(created_at=now - datetime.timedelta(days=30))

    resolved = Ticket.objects.create(
        organization=org,
        requester=owner,
        subject="Resolved",
        description="...",
        status=Ticket.Status.RESOLVED,
        resolved_at=now - datetime.timedelta(days=1),
    )
    Ticket.objects.filter(id=resolved.id).update(created_at=now - datetime.timedelta(days=30))

    send_weekly_digest()

    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["owner1@acme.test"]
    assert "New tickets: 1" in message.body
    assert "Resolved tickets: 1" in message.body


@pytest.mark.django_db
def test_organization_with_no_owner_email_is_skipped(org):
    User.objects.create_user(
        username="owner_no_email",
        password="whatever123",
        organization=org,
        role=User.Role.OWNER,
        email="",
    )

    send_weekly_digest()

    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_each_organization_gets_its_own_digest(org, owner):
    other_org = Organization.objects.create(name="Other", slug="other")
    User.objects.create_user(
        username="other_owner",
        password="whatever123",
        organization=other_org,
        role=User.Role.OWNER,
        email="other_owner@test.test",
    )

    send_weekly_digest()

    recipients = {email for message in mail.outbox for email in message.to}
    assert recipients == {"owner1@acme.test", "other_owner@test.test"}
