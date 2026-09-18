import datetime

import pytest
from django.core import mail
from django.utils import timezone

from apps.accounts.models import Organization, User
from apps.tickets.models import Ticket
from apps.tickets.tasks import check_sla_breaches


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
def test_overdue_open_ticket_gets_flagged(org, owner):
    ticket = Ticket.objects.create(
        organization=org,
        requester=owner,
        subject="Overdue",
        description="...",
        due_at=timezone.now() - datetime.timedelta(minutes=10),
    )

    breached_count = check_sla_breaches()

    ticket.refresh_from_db()
    assert breached_count == 1
    assert ticket.sla_breached_at is not None
    assert len(mail.outbox) == 1
    assert "SLA breached" in mail.outbox[0].subject


@pytest.mark.django_db
def test_ticket_not_yet_due_is_not_flagged(org, owner):
    Ticket.objects.create(
        organization=org,
        requester=owner,
        subject="Not due yet",
        description="...",
        due_at=timezone.now() + datetime.timedelta(hours=1),
    )

    assert check_sla_breaches() == 0
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_resolved_ticket_is_not_flagged_even_if_overdue(org, owner):
    Ticket.objects.create(
        organization=org,
        requester=owner,
        subject="Resolved but overdue",
        description="...",
        status=Ticket.Status.RESOLVED,
        due_at=timezone.now() - datetime.timedelta(minutes=10),
    )

    assert check_sla_breaches() == 0


@pytest.mark.django_db
def test_already_breached_ticket_is_not_re_notified(org, owner):
    ticket = Ticket.objects.create(
        organization=org,
        requester=owner,
        subject="Overdue",
        description="...",
        due_at=timezone.now() - datetime.timedelta(minutes=10),
    )

    first_run = check_sla_breaches()
    mail.outbox.clear()
    second_run = check_sla_breaches()

    assert first_run == 1
    assert second_run == 0
    assert len(mail.outbox) == 0
    ticket.refresh_from_db()
    assert ticket.sla_breached_at is not None


@pytest.mark.django_db
def test_breach_notification_goes_to_assignee_when_assigned(org, owner):
    agent = User.objects.create_user(
        username="agent1",
        password="whatever123",
        organization=org,
        role=User.Role.AGENT,
        email="agent1@acme.test",
    )
    Ticket.objects.create(
        organization=org,
        requester=owner,
        assignee=agent,
        subject="Overdue",
        description="...",
        due_at=timezone.now() - datetime.timedelta(minutes=10),
    )

    check_sla_breaches()

    assert mail.outbox[0].to == ["agent1@acme.test"]
